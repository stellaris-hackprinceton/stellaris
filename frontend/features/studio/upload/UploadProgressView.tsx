"use client";
import { Button, ErrorNotice, StatusBadge, describeError, errorCode } from "@/components/ui";
import { formatBytes } from "../format";
import type { ArtifactUploadController } from "./useArtifactUpload";
import styles from "../studio.module.css";

const LABEL = {
  selected: "Preparing upload…", creating: "Starting upload…", transferring: "Uploading…", finalizing: "Checking the file on the server…",
};

const ERROR_TEXT: Record<string, string> = {
  UPLOAD_TOO_LARGE: "The file is larger than the server allows.",
  PROJECT_QUOTA_EXCEEDED: "This project has reached its storage limit.",
  UNSUPPORTED_MEDIA_TYPE: "The server does not accept this file type.",
  MEDIA_DECODE_FAILED: "The server could not decode this media file.",
  UPLOAD_EXPIRED: "The upload session expired. Retrying starts a new session with the same file.",
  UPLOAD_IN_PROGRESS: "Another transfer of this upload is still running. Retry in a moment.",
  PROJECT_ARCHIVED: "This project is archived. Restore it to upload files.",
};

/** Progress for the shared upload controller. Byte progress only when the transport reports it. */
export function UploadProgressView({ up, children }: { up: ArtifactUploadController; children?: React.ReactNode }) {
  if (up.phase === "idle" || !up.input) return null;
  const name = up.input.request.filename;
  const p = up.progress;
  const pct = p && p.total_bytes ? Math.min(100, Math.round((p.loaded_bytes / p.total_bytes) * 100)) : null;

  return (
    <div className={styles.uploadBox} aria-live="polite">
      <div className={styles.row}>
        <strong className={styles.inputName}>{name}</strong>
        <span className={styles.muted}>{formatBytes(up.input.blob.size)}</span>
        {up.input.request.origin === "simulated" && <StatusBadge tone="warning">Simulated</StatusBadge>}
      </div>

      {up.busy && (
        <>
          <p className={styles.muted} role="status">
            {LABEL[up.phase as keyof typeof LABEL]}{up.phase === "transferring" && pct != null ? ` ${pct}%` : ""}
          </p>
          {up.phase === "transferring" && (pct != null
            ? <progress className={styles.progress} max={100} value={pct} aria-label="Upload progress" />
            : <progress className={styles.progress} aria-label="Upload in progress" />)}
          {up.phase === "transferring" && <div><Button onClick={up.cancel}>Cancel upload</Button></div>}
        </>
      )}

      {up.phase === "cancelled" && (
        <div className={styles.row}>
          <StatusBadge tone="neutral">Upload cancelled</StatusBadge>
          <Button onClick={up.retry}>Resume upload</Button>
          <Button onClick={up.reset}>Dismiss</Button>
        </div>
      )}

      {up.phase === "failed" && (
        <ErrorNotice
          {...describeError(up.error, "Upload failed")}
          message={ERROR_TEXT[up.expired ? "UPLOAD_EXPIRED" : errorCode(up.error) ?? ""] ?? describeError(up.error).message}
          action={
            <div className={styles.row}>
              {!up.terminal && <Button onClick={up.retry}>Retry upload</Button>}
              <Button onClick={up.reset}>Dismiss</Button>
            </div>
          }
        />
      )}

      {up.phase === "ready" && up.artifact && (
        <div className={styles.stack}>
          <StatusBadge tone="success">Saved to project</StatusBadge>
          {children}
        </div>
      )}
    </div>
  );
}
