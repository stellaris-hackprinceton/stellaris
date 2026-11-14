"use client";
import { useEffect, useId, useMemo, useState } from "react";
import type { Capabilities, UploadRequest } from "@/contracts/api";
import { Button, Field, Select, StatusBadge } from "@/components/ui";
import { formatBytes, formatDuration } from "../format";
import { mimeForFile } from "./fileTypes";
import styles from "../studio.module.css";

type Kind = UploadRequest["kind"];
type Origin = UploadRequest["origin"];

export function kindForMime(mime: string, filename: string): Kind {
  const m = mime.toLowerCase();
  if (m.startsWith("video/")) return "video";
  if (m.startsWith("image/")) return "image";
  if (m.startsWith("audio/")) return "audio";
  if (m === "text/csv" || m === "application/json" || /\.(csv|tsv|json|parquet)$/i.test(filename)) return "dataset";
  if (m === "text/x-python" || /\.py$/i.test(filename)) return "code";
  return "document";
}

const ORIGINS: { id: Origin; label: string; hint: string }[] = [
  { id: "observed", label: "Observed", hint: "Raw data from a real experiment (your declaration)." },
  { id: "simulated", label: "Simulated", hint: "Synthetic data. Results will be labelled simulated throughout." },
  { id: "reference", label: "Reference", hint: "Reference material such as a paper or datasheet." },
  { id: "generated", label: "Generated", hint: "Authored code or documents." },
];

type Props = {
  uploads: Capabilities["uploads"] | undefined;
  disabled: boolean;
  onUpload: (file: File, kind: Kind, origin: Origin) => void;
};

/** Pick a file, check it locally against published limits, preview it, then upload explicitly. */
export function FileImport({ uploads, disabled, onUpload }: Props) {
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [origin, setOrigin] = useState<Origin>("observed");
  const [measured, setMeasured] = useState<{ file: File; ms: number } | null>(null);
  const durationMs = measured && measured.file === file ? measured.ms : null;

  // One managed object URL per selected file, revoked when the file changes or on unmount.
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  const baseMime = file ? mimeForFile(file.type, file.name) : "";
  const kind = file ? kindForMime(baseMime, file.name) : null;
  const accepted = uploads?.accepted_mime_types ?? [];
  const problems: string[] = [];
  if (file && uploads) {
    if (!baseMime) problems.push("The browser could not determine this file's type.");
    else if (!accepted.map((m) => m.toLowerCase()).includes(baseMime)) problems.push(`The server does not accept ${baseMime} files.`);
    if (file.size > uploads.max_file_bytes) problems.push(`The file is ${formatBytes(file.size)}; the limit is ${formatBytes(uploads.max_file_bytes)}.`);
    if (kind === "video" && durationMs != null && durationMs > uploads.max_video_duration_ms) {
      problems.push(`The video is ${formatDuration(durationMs)}; the limit is ${formatDuration(uploads.max_video_duration_ms)}.`);
    }
  }

  return (
    <div className={styles.stack}>
      <div className={styles.varField}>
        <label htmlFor={`${id}-file`} className={styles.smallLabel}>File</label>
        <input id={`${id}-file`} type="file" className={styles.fileInput} disabled={disabled || !uploads}
          accept={[...accepted, ...(accepted.includes("text/x-python") ? [".py"] : [])].join(",")} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        {uploads && <p className={styles.muted}>Up to {formatBytes(uploads.max_file_bytes)}; videos up to {formatDuration(uploads.max_video_duration_ms)}.</p>}
      </div>

      {file && (
        <>
          <div className={styles.row}>
            <strong className={styles.inputName}>{file.name}</strong>
            <span className={styles.muted}>{kind} · {formatBytes(file.size)}{durationMs != null ? ` · ${formatDuration(durationMs)}` : ""}</span>
            <StatusBadge tone="neutral">Not uploaded</StatusBadge>
          </div>
          {url && kind === "video" && (
            <video src={url} className={styles.media} controls playsInline aria-label={`Preview of ${file.name}`}
              onLoadedMetadata={(e) => { const d = e.currentTarget.duration; if (Number.isFinite(d)) setMeasured({ file, ms: d * 1000 }); }} />
          )}
          {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview */}
          {url && kind === "image" && <img src={url} alt={`Preview of ${file.name}`} className={styles.media} />}
          {url && kind === "audio" && <audio src={url} controls aria-label={`Preview of ${file.name}`} />}

          <Field label="What is this data?" hint={ORIGINS.find((o) => o.id === origin)?.hint}>
            <Select value={origin} onChange={(e) => setOrigin(e.target.value as Origin)} disabled={disabled}>
              {ORIGINS.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
            </Select>
          </Field>
          {problems.length > 0 && (
            <ul className={styles.problems} role="alert">{problems.map((p, i) => <li key={i}>{p}</li>)}</ul>
          )}
          <div className={styles.row}>
            <Button variant="primary" disabled={disabled || problems.length > 0 || !kind}
              onClick={() => kind && onUpload(file, kind, origin)}>Upload file</Button>
            <Button onClick={() => setFile(null)}>Clear</Button>
          </div>
        </>
      )}
    </div>
  );
}
