"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ID, PaperMetadata, Run, Source } from "@/contracts/api";
import type { PaperIngestRequest } from "@/contracts/requests";
import { ApiError, api } from "@/lib/api";
import { terminal, useCancelRun, useCapabilities, useRun, useStartRun } from "@/lib/queries";
import { Button, Dialog, ErrorNotice, Field, StatusBadge, TextArea, TextInput, describeError, newCommandKey } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
// Reuses Studio's upload controller: create → content PUT → complete with stable command keys.
import { useArtifactUpload } from "@/features/studio/upload/useArtifactUpload";
import { RUN_STATUS_LABEL, runTone } from "./ActiveWork";
import styles from "./desk.module.css";

const INGEST_CEILING = 50 * 1024 * 1024;
// Mirrors the backend's accepted arXiv identifier syntax; the backend remains authoritative.
const ARXIV_ID = /^(?:\d{4}\.\d{4,5}|[a-z][a-z.-]{0,30}(?:\.[A-Z]{2})?\/\d{7})(?:v\d{1,3})?$/;
const PUBLISHED = /^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$/;

export type IngestMode = "pdf" | "arxiv";
/** A reviewed retry after a definitive failure: reuses a completed upload or an arXiv ID. */
export type IngestRetry = { mode: "pdf"; artifact_id: ID; metadata: PaperMetadata | null } | { mode: "arxiv"; arxiv_id: string };

function definitive(error: unknown) {
  return error instanceof ApiError && error.status >= 400 && error.status < 500 && ![408, 429].includes(error.status) && error.code !== "COMMAND_IN_PROGRESS";
}
const formatBytes = (n: number) => n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MiB` : `${Math.ceil(n / 1024)} KiB`;

/** Extract command with a locked body and key while acceptance is uncertain. */
function useIngestCommand(project_id: ID, onAccepted: (run: Run) => void) {
  const start = useStartRun(project_id);
  const command = useRef<{ body: PaperIngestRequest; key: string } | null>(null);
  const [failure, setFailure] = useState<{ error: unknown; definitive: boolean } | null>(null);
  async function submit(body?: PaperIngestRequest) {
    if (!command.current) { if (!body) return; command.current = { body, key: newCommandKey() }; }
    setFailure(null);
    try {
      const response = await start.mutateAsync({ body: command.current.body, idempotency_key: command.current.key });
      command.current = null;
      onAccepted(response.data);
    } catch (error) { setFailure({ error, definitive: definitive(error) }); }
  }
  function edit() { command.current = null; setFailure(null); start.reset(); }
  const uncertain = !!failure && !failure.definitive;
  const notice = failure && (failure.definitive
    ? <ErrorNotice {...describeError(failure.error, "Extraction request rejected")} action={<Button onClick={edit}>Edit request</Button>} />
    : <ErrorNotice {...describeError(failure.error, "Submission outcome unknown")} message="The request may have been accepted. Retrying sends the identical request and command key, so it cannot start a duplicate run." action={<Button onClick={() => void submit()} pending={start.isPending}>Retry the same submission</Button>} />);
  return { submit, pending: start.isPending, locked: start.isPending || uncertain, notice, reset: edit };
}

function MetadataFields({ value, onChange, disabled, touched }: { value: MetaDraft; onChange: (v: MetaDraft) => void; disabled: boolean; touched: boolean }) {
  const set = (k: keyof MetaDraft) => (e: { target: { value: string } }) => onChange({ ...value, [k]: e.target.value });
  return (
    <fieldset className={styles.form} disabled={disabled} style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className={styles.meta}>Optional document metadata. Leave blank to omit; nothing is guessed.</legend>
      <Field label="Title"><TextInput value={value.title} maxLength={1000} onChange={set("title")} /></Field>
      <Field label="Authors" hint="One per line."><TextArea rows={2} value={value.authors} onChange={set("authors")} /></Field>
      <Field label="DOI"><TextInput value={value.doi} onChange={set("doi")} /></Field>
      <Field label="Published" hint="YYYY, YYYY-MM, or YYYY-MM-DD." error={touched && value.published_at.trim() && !PUBLISHED.test(value.published_at.trim()) ? "Use YYYY, YYYY-MM, or YYYY-MM-DD." : null}><TextInput value={value.published_at} onChange={set("published_at")} /></Field>
      <Field label="Link"><TextInput type="url" value={value.url} onChange={set("url")} placeholder="https://" /></Field>
    </fieldset>
  );
}
type MetaDraft = { title: string; authors: string; doi: string; published_at: string; url: string };
const EMPTY_META: MetaDraft = { title: "", authors: "", doi: "", published_at: "", url: "" };
function toMetadata(m: MetaDraft): PaperMetadata | null {
  const out: PaperMetadata = {};
  if (m.title.trim()) out.title = m.title.trim();
  const authors = m.authors.split("\n").map((a) => a.trim()).filter(Boolean);
  if (authors.length) out.authors = authors;
  if (m.doi.trim()) out.doi = m.doi.trim();
  if (m.published_at.trim()) out.published_at = m.published_at.trim();
  if (m.url.trim()) out.url = m.url.trim();
  return Object.keys(out).length ? out : null;
}
function fromMetadata(m: PaperMetadata | null | undefined): MetaDraft {
  return { title: m?.title ?? "", authors: (m?.authors ?? []).join("\n"), doi: m?.doi ?? "", published_at: m?.published_at ?? "", url: m?.url ?? "" };
}

/** Upload PDF: transfer first, then an explicit Extract paper command. Upload alone creates no Source. */
export function PdfIngestDialog({ project_id, open, onClose, onAccepted, retry }: {
  project_id: ID; open: boolean; onClose: () => void; onAccepted: (run: Run) => void; retry?: Extract<IngestRetry, { mode: "pdf" }> | null;
}) {
  const capabilities = useCapabilities();
  const upload = useArtifactUpload(project_id);
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState<MetaDraft>(fromMetadata(retry?.metadata));
  const [touched, setTouched] = useState(false);
  const command = useIngestCommand(project_id, (run) => { upload.reset(); setFile(null); setMeta(EMPTY_META); setTouched(false); onAccepted(run); });
  const uploads = capabilities.data?.uploads;
  const limit = Math.min(uploads?.max_file_bytes ?? INGEST_CEILING, INGEST_CEILING);
  const pdfAccepted = !uploads || uploads.accepted_mime_types.includes("application/pdf");
  const isPdf = !!file && (file.type === "application/pdf" || (!file.type && file.name.toLowerCase().endsWith(".pdf")));
  const fileError = !file ? null : !isPdf ? "Choose a PDF file." : file.size > limit ? `This file is ${formatBytes(file.size)}; the limit is ${formatBytes(limit)}.` : file.size === 0 ? "This file is empty." : null;
  const metaError = meta.published_at.trim() && !PUBLISHED.test(meta.published_at.trim());
  const artifactId = retry?.artifact_id ?? upload.artifact?.id ?? null;
  const transferred = upload.phase === "ready" || !!retry;
  const close = () => { if (!command.locked && !upload.busy) onClose(); };

  function startUpload() {
    if (!file || fileError) return;
    upload.start({ blob: file, request: { filename: file.name, mime_type: "application/pdf", size_bytes: file.size, kind: "document", origin: "reference" } });
  }
  function extract() {
    setTouched(true);
    if (!artifactId || metaError) return;
    const metadata = toMetadata(meta);
    void command.submit({ kind: "paper_ingest", document: { artifact_id: artifactId }, ...(metadata ? { metadata } : {}) });
  }
  return (
    <Dialog open={open} onClose={close} title={retry ? "Try extraction again" : "Upload PDF"} keepMounted>
      <div className={styles.form}>
        {!pdfAccepted ? <p role="note">This backend does not accept PDF uploads.</p> : !transferred ? <>
          <p className={styles.meta}>Uploading saves the original document. Text extraction is a separate step you start after the upload completes. Extraction has no OCR and may be partial.</p>
          <Field label="PDF file" hint={`Up to ${formatBytes(limit)}.`} error={fileError}>
            <input type="file" accept="application/pdf,.pdf" disabled={upload.busy} onChange={(e) => { setFile(e.target.files?.[0] ?? null); }} />
          </Field>
          {upload.phase !== "idle" && <p role="status" className={styles.meta}>
            {upload.phase === "creating" ? "Preparing upload…" : upload.phase === "transferring" ? `Transferring${upload.progress?.total_bytes ? ` ${Math.round((upload.progress.loaded_bytes / upload.progress.total_bytes) * 100)}%` : "…"}` : upload.phase === "finalizing" ? "Finalizing upload…" : upload.phase === "cancelled" ? "Upload cancelled. The file is still selected." : upload.phase === "failed" ? "Upload failed." : ""}
          </p>}
          {upload.phase === "failed" && <ErrorNotice {...describeError(upload.error, upload.expired ? "Upload session expired" : "Upload failed")} action={!upload.terminal ? <Button onClick={upload.retry}>Retry upload</Button> : undefined} />}
          <div className={styles.row}>
            <Button variant="primary" onClick={startUpload} disabled={!file || !!fileError || upload.busy} pending={upload.busy}>Upload PDF</Button>
            {upload.busy && <Button onClick={upload.cancel}>Cancel upload</Button>}
          </div>
        </> : <>
          <p role="status">{retry ? "The completed upload will be reused; its bytes are not uploaded again." : `Upload complete: ${upload.artifact?.filename ?? "document"}. No text has been extracted yet.`}</p>
          <MetadataFields value={meta} onChange={setMeta} disabled={command.locked} touched={touched} />
          {command.notice}
          <div className={styles.row}>
            <Button variant="primary" onClick={extract} pending={command.pending} disabled={command.locked}>Extract paper</Button>
            <Button onClick={close} disabled={command.locked}>Close</Button>
          </div>
          <p className={styles.meta}>The original upload stays available in All materials regardless of the extraction outcome.</p>
        </>}
      </div>
    </Dialog>
  );
}

export function ArxivIngestDialog({ project_id, open, onClose, onAccepted, initialId }: {
  project_id: ID; open: boolean; onClose: () => void; onAccepted: (run: Run) => void; initialId?: string;
}) {
  const [id, setId] = useState(initialId ?? "");
  const [touched, setTouched] = useState(false);
  const command = useIngestCommand(project_id, (run) => { setId(""); setTouched(false); onAccepted(run); });
  const close = () => { if (!command.locked) onClose(); };
  const value = id.trim().replace(/^arxiv:/i, "");
  const error = !value ? "Enter an arXiv identifier." : !ARXIV_ID.test(value) ? "Use an arXiv identifier such as 2401.01234 or 2401.01234v2." : null;
  return (
    <Dialog open={open} onClose={close} title="Retrieve arXiv full text" keepMounted>
      <form className={styles.form} onSubmit={(e) => { e.preventDefault(); setTouched(true); if (!error) void command.submit({ kind: "paper_ingest", document: { arxiv_id: value } }); }} noValidate>
        <p className={styles.meta}>Retrieves the paper&apos;s public e-print from arXiv and extracts its text in an isolated worker. Extraction is best-effort; figures and equations may be omitted.</p>
        <Field label="arXiv identifier" error={touched ? error : null}><TextInput value={id} disabled={command.locked} onChange={(e) => setId(e.target.value)} placeholder="2401.01234" /></Field>
        {command.notice}
        <div className={styles.row}>
          <Button type="submit" variant="primary" pending={command.pending} disabled={command.locked}>Retrieve and extract</Button>
          <Button onClick={close} disabled={command.locked}>Close</Button>
        </div>
      </form>
    </Dialog>
  );
}

/** Finds the immutable Source published by an ingestion run. Refetched by `source.created` invalidation. */
function usePublishedSource(project_id: ID, run_id: ID, enabled: boolean) {
  return useQuery({
    queryKey: ["project", project_id, "sources", "ingest-lookup", run_id],
    enabled,
    retry: false,
    queryFn: async ({ signal }) => {
      let cursor: string | undefined;
      for (let page = 0; page < 10; page++) {
        const result = (await api.sources.list(project_id, { cursor }, signal)).data;
        const match = result.items.find((s: Source) => s.full_text?.ingest_run_id === run_id);
        if (match) return match;
        if (!result.next_cursor) return null;
        cursor = result.next_cursor;
      }
      return null;
    },
  });
}

/** Actual ingestion run status with cancel and outcome handling. Never labelled as a report. */
export function IngestRunStatus({ project_id, run_id, onOpenSource, onRetry, onDismiss }: {
  project_id: ID; run_id: ID; onOpenSource: (source_id: ID) => void; onRetry: (retry: IngestRetry) => void; onDismiss: () => void;
}) {
  const query = useRun(project_id, run_id);
  const run = query.data;
  const cancel = useCancelRun();
  const cancelKey = useRef<string | null>(null);
  const published = usePublishedSource(project_id, run_id, run?.status === "succeeded");
  if (query.error && !run) return <li>
    <span className={styles.unavailable}>Paper ingestion status could not be loaded.</span>
    <Button onClick={() => void query.refetch()}>Retry status</Button>
    <Link href={hrefs.run(project_id, run_id)}>Run details</Link>
  </li>;
  if (!run) return <li><span role="status" className={styles.meta}>Loading paper ingestion status…</span> <Link href={hrefs.run(project_id, run_id)}>Run details</Link></li>;
  const input = run.input.kind === "paper_ingest" ? run.input : null;
  const label = input && "arxiv_id" in input.document ? `arXiv ${input.document.arxiv_id}` : "Uploaded PDF";
  const done = terminal(run);
  return (
    <li>
      <StatusBadge tone={runTone(run.status)}>{RUN_STATUS_LABEL[run.status]}</StatusBadge>
      <strong>Paper ingestion · {label}</strong>
      {!done && (run.progress.message || run.phase) && <span>{run.progress.message || run.phase}</span>}
      {!done && run.progress.fraction != null && <span className={styles.meta}>{Math.round(run.progress.fraction * 100)}%</span>}
      {run.error && <span>{run.error.message}</span>}
      <Link href={hrefs.run(project_id, run.id)}>Run details</Link>
      {!done && <Button disabled={cancel.isPending || run.status === "cancelling"} onClick={() => { cancelKey.current ??= newCommandKey(); void cancel.mutateAsync({ project_id, run_id: run.id, command: { idempotency_key: cancelKey.current } }).catch(() => undefined); }}>{run.status === "cancelling" ? "Cancellation pending" : "Cancel"}</Button>}
      {cancel.error != null && <span className={styles.meta}>Cancellation could not be confirmed. {describeError(cancel.error).message}</span>}
      {run.status === "succeeded" && (published.data
        ? <Button variant="primary" onClick={() => onOpenSource(published.data!.id)}>Open extracted paper</Button>
        : published.isPending ? <span className={styles.meta}>Locating the published source…</span>
          : published.error ? <Button onClick={() => void published.refetch()}>Retry finding the extracted paper</Button>
            : <span className={styles.meta}>The run succeeded but no published source was found. Inspect the run details.</span>)}
      {(run.status === "failed" || run.status === "cancelled") && input && <Button onClick={() => onRetry("arxiv_id" in input.document ? { mode: "arxiv", arxiv_id: input.document.arxiv_id } : { mode: "pdf", artifact_id: input.document.artifact_id, metadata: input.metadata ?? null })}>Try extraction again</Button>}
      {done && <Button onClick={onDismiss}>Dismiss</Button>}
    </li>
  );
}
