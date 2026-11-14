"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ID, PaperDocument, SourceFullText } from "@/contracts/api";
import { artifactContentUrl, responseError } from "@/lib/api";
import { useArtifact, useRun, useRunResults, useSource } from "@/lib/queries";
import { Button, ErrorNotice, Skeleton, StatusBadge, describeError } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import { PROVIDER_LABEL, RETRIEVAL_LABEL, safeHref } from "../canvas/labels";
import styles from "./desk.module.css";

const MAX_PAPER_JSON = 16 * 1024 * 1024;

export type CitationFocus = { locator: string | null; excerpt: string | null };

export function SourceInspector({ project_id, source_id, citation }: { project_id: ID; source_id: ID; citation?: CitationFocus | null }) {
  const query = useSource(project_id, source_id);
  const s = query.data;
  const [showReader, setShowReader] = useState(false);
  const reading = showReader || !!citation?.locator;
  if (query.error && !s) return <ErrorNotice {...describeError(query.error, "Source unavailable")} message="This saved source could not be loaded. A missing record is not evidence against any claim." action={<Button onClick={() => void query.refetch()}>Retry</Button>} />;
  if (!s) return <div className={styles.stack}><Skeleton height="1.5rem" /><Skeleton /><Skeleton width="60%" /></div>;
  if (s.project_id !== project_id) return <p role="alert">This source is unavailable in this project.</p>;
  const retrieval = RETRIEVAL_LABEL[s.retrieval_status];
  const url = safeHref(s.url);
  const ft = s.full_text ?? null;
  return (
    <div className={styles.stack}>
      <h3 style={{ margin: 0, fontSize: 18, overflowWrap: "anywhere" }}>{s.title}</h3>
      <div className={styles.badges}>
        <StatusBadge tone={retrieval.tone}>{retrieval.text}</StatusBadge>
        {ft?.truncated && <StatusBadge tone="warning">Partial extraction</StatusBadge>}
      </div>
      {citation && (citation.excerpt || citation.locator) && <div>
        <p className={styles.meta}>Recorded citation{citation.locator ? ` · ${citation.locator}` : ""}</p>
        {citation.excerpt && <blockquote className={styles.quote}>{citation.excerpt}</blockquote>}
      </div>}
      <dl className={styles.dl}>
        <dt>Authors</dt><dd>{s.authors.length ? s.authors.join(", ") : "Not recorded"}</dd>
        {s.published_at && <><dt>Published</dt><dd>{s.published_at}</dd></>}
        <dt>Provider</dt><dd>{PROVIDER_LABEL[s.provider]}{s.external_id ? ` · ${s.external_id}` : ""}</dd>
        <dt>Retrieved</dt><dd>{new Date(s.retrieved_at).toLocaleString()}</dd>
        <dt>Added</dt><dd>{new Date(s.created_at).toLocaleString()}</dd>
        {s.doi && <><dt>DOI</dt><dd>{s.doi}</dd></>}
        {url && <><dt>Source</dt><dd><a href={url} target="_blank" rel="noopener noreferrer">{url}</a></dd></>}
      </dl>
      <div>
        <h4 style={{ margin: "0 0 4px" }}>Abstract</h4>
        <p style={{ margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{s.abstract || "No abstract saved."}</p>
      </div>
      <div className={styles.links}>
        {s.document_artifact_id && <a href={artifactContentUrl(project_id, s.document_artifact_id, "attachment")} download>Download original document</a>}
        {s.document_artifact_id && <Link href={hrefs.artifact(project_id, s.document_artifact_id)}>Original document details</Link>}
      </div>
      {ft && <FullTextDetails project_id={project_id} ft={ft} />}
      {ft && (reading
        ? <PaperReader project_id={project_id} source_id={s.id} artifact_id={ft.text_artifact_id} locator={citation?.locator ?? null} />
        : <div><Button onClick={() => setShowReader(true)}>Read extracted paper</Button></div>)}
      {!ft && (s.retrieval_status === "full_text_retrieved"
        ? <p className={styles.unavailable}>Full-text metadata is unavailable for this source.</p>
        : <p className={styles.meta}>Only the material shown above was retrieved. This is not the full paper.</p>)}
    </div>
  );
}

function FullTextDetails({ project_id, ft }: { project_id: ID; ft: SourceFullText }) {
  const run = useRun(project_id, ft.ingest_run_id);
  const results = useRunResults(project_id, ft.ingest_run_id);
  const license = safeHref(ft.license_url);
  return (
    <div className={styles.stack}>
      <h4 style={{ margin: 0 }}>Extracted full text</h4>
      <dl className={styles.dl}>
        <dt>Format</dt><dd>{ft.format === "latex_source" ? "LaTeX source (not compiled)" : "PDF text layer"}</dd>
        {ft.section_count != null && <><dt>Sections</dt><dd>{ft.section_count}</dd></>}
        {ft.page_count != null && <><dt>Pages</dt><dd>{ft.page_count}</dd></>}
        {license && <><dt>License</dt><dd><a href={license} target="_blank" rel="noopener noreferrer">{license}</a></dd></>}
        <dt>Ingestion run</dt><dd><Link href={hrefs.run(project_id, ft.ingest_run_id)}>Run …{ft.ingest_run_id.slice(-8)}</Link></dd>
      </dl>
      {ft.truncated && <p role="note">Partial extraction: the extracted text was truncated at its size limit.</p>}
      <p className={styles.meta}>Extraction is best-effort with no OCR. It does not establish that figures or the whole paper were read.</p>
      {results.data?.warnings.length ? <ul className={styles.meta}>{results.data.warnings.map((w, i) => <li key={`${w.code}:${i}`}>{w.message}</li>)}</ul> : null}
      <div className={styles.links}>
        <a href={artifactContentUrl(project_id, ft.text_artifact_id, "attachment")} download>Download structured paper.json</a>
        {run.data ? <FlatTextLink project_id={project_id} ids={run.data.output_artifact_ids} /> : run.error ? <span className={styles.unavailable}>Flat text unavailable: the ingestion run could not be loaded.</span> : null}
      </div>
    </div>
  );
}

/** Resolves paper.txt through the ingestion run's outputs. Never guesses IDs or paths. */
function FlatTextLink({ project_id, ids }: { project_id: ID; ids: ID[] }) {
  if (!ids.length) return <span className={styles.unavailable}>Flat text unavailable.</span>;
  return <>{ids.map((id) => <FlatTextCandidate key={id} project_id={project_id} id={id} />)}</>;
}
function FlatTextCandidate({ project_id, id }: { project_id: ID; id: ID }) {
  const a = useArtifact(project_id, id).data;
  if (!a || a.filename !== "paper.txt" || !a.mime_type.startsWith("text/plain")) return null;
  return <a href={artifactContentUrl(project_id, a.id, "attachment")} download="paper.txt">Download flat text (paper.txt)</a>;
}

function isPaper(value: unknown): value is PaperDocument {
  const v = value as PaperDocument;
  return !!v && typeof v === "object" && Array.isArray(v.sections) && v.sections.every((s) => s && typeof s.id === "string" && typeof s.title === "string" && Array.isArray(s.paragraphs) && s.paragraphs.every((p) => p && typeof p.id === "string" && typeof p.text === "string"));
}

/** Renders paper.json as escaped text, one section at a time, with stable locator anchors. */
export function PaperReader({ project_id, source_id, artifact_id, locator }: { project_id: ID; source_id: ID; artifact_id: ID; locator: string | null }) {
  const artifact = useArtifact(project_id, artifact_id);
  const tooLarge = !!artifact.data && artifact.data.size_bytes > MAX_PAPER_JSON;
  const paper = useQuery({
    queryKey: ["project", project_id, "paper-json", artifact_id, artifact.data?.sha256],
    enabled: !!artifact.data && artifact.data.project_id === project_id && !tooLarge,
    retry: false, staleTime: Infinity,
    queryFn: async ({ signal }) => {
      const response = await fetch(artifactContentUrl(project_id, artifact_id, "attachment"), { credentials: "same-origin", cache: "no-store", signal });
      if (!response.ok) throw await responseError(response);
      const parsed: unknown = JSON.parse(await response.text());
      if (!isPaper(parsed)) throw new Error("The extracted paper has an unsupported structure.");
      return parsed;
    },
  });
  const target = paper.data && locator ? paper.data.sections.find((s) => s.locator === locator || s.paragraphs.some((p) => p.locator === locator)) : undefined;
  const [sectionId, setSectionId] = useState<string | null>(null);
  const section = paper.data?.sections.find((s) => s.id === (sectionId ?? target?.id)) ?? paper.data?.sections[0];
  const anchor = (id: string) => `paper-${source_id}-${id}`;
  const highlighted = target && locator ? (target.locator === locator ? target.paragraphs[0]?.id : target.paragraphs.find((p) => p.locator === locator)?.id) : undefined;
  useEffect(() => {
    if (highlighted && !sectionId) document.getElementById(anchor(highlighted))?.scrollIntoView({ block: "center" });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- scroll once when the cited paragraph first renders
  }, [highlighted]);
  if (artifact.error && !artifact.data) return <ErrorNotice {...describeError(artifact.error, "Extracted paper unavailable")} action={<Button onClick={() => void artifact.refetch()}>Retry</Button>} />;
  if (tooLarge) return <p className={styles.unavailable}>The extracted paper exceeds the in-app reader limit. Download paper.json instead.</p>;
  if (paper.error) return <ErrorNotice {...describeError(paper.error, "Extracted paper could not be read")} message={paper.error instanceof SyntaxError ? "The saved paper.json is not valid JSON." : describeError(paper.error).message} action={<Button onClick={() => void paper.refetch()}>Retry</Button>} />;
  if (!paper.data || !section) return <p role="status">Loading extracted paper…</p>;
  const p = paper.data;
  return (
    <section className={styles.reader} aria-label="Extracted paper reader">
      {p.truncated && <p role="note">This extraction was truncated; later text is missing.</p>}
      {p.extraction_notes.length > 0 && <details className={styles.details}><summary>Extraction notes ({p.extraction_notes.length})</summary><ul>{p.extraction_notes.map((n, i) => <li key={i}>{n}</li>)}</ul></details>}
      {locator && !target && <p role="note">The cited locator “{locator}” was not found in the extracted text.</p>}
      <nav aria-label="Sections">
        <ol>{p.sections.map((s) => <li key={s.id} style={{ marginLeft: (s.level - 1) * 12 }}>
          <button type="button" className={styles.linkButton} style={{ minHeight: 32 }} aria-current={s.id === section.id ? "true" : undefined} onClick={() => setSectionId(s.id)}>{s.number ? `${s.number} ` : ""}{s.title}</button>
        </li>)}</ol>
      </nav>
      <article>
        <h4 id={anchor(section.id)} style={{ margin: "0 0 8px" }}>{section.number ? `${section.number} ` : ""}{section.title} <span className={styles.meta}>· {section.locator}</span></h4>
        {section.paragraphs.map((para) => (
          <p key={para.id} id={anchor(para.id)} data-kind={para.kind} data-highlight={para.id === highlighted} title={para.locator}>{para.text}</p>
        ))}
      </article>
    </section>
  );
}
