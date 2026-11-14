"use client";
import { Button, StatusBadge } from "@/components/ui";
import { formatBytes, formatDuration } from "../format";
import type { Recording } from "./useCamera";
import styles from "../studio.module.css";

const STOP_NOTE: Record<Recording["stop_reason"], string | null> = {
  user: null,
  duration_limit: "Recording stopped at the server's maximum video length.",
  size_limit: "Recording stopped near the server's maximum file size.",
  device_lost: "The camera disconnected; this is what was captured before that.",
};

/** Reviews the recorded Blob (not the live stream). Upload is a separate, explicit action. */
export function RecordingReview({ recording, onUpload, onDiscard, uploadDisabled, uploaded }: {
  recording: Recording; onUpload: () => void; onDiscard: () => void; uploadDisabled?: boolean; uploaded: boolean;
}) {
  if (uploaded) {
    return (
      <div className={styles.stack}>
        <video src={recording.url} className={styles.media} controls playsInline aria-label="Uploaded recording" />
        <div className={styles.row}>
          <StatusBadge tone="success">Uploaded</StatusBadge>
          <Button onClick={onDiscard}>Record another</Button>
        </div>
      </div>
    );
  }
  const note = STOP_NOTE[recording.stop_reason];
  return (
    <div className={styles.stack}>
      <video src={recording.url} className={styles.media} controls playsInline aria-label="Recorded video" />
      <div className={styles.row}>
        <StatusBadge tone="neutral">Not uploaded</StatusBadge>
        <span className={styles.muted}>{formatDuration(recording.duration_ms)} · {formatBytes(recording.blob.size)} · {recording.mime_type}</span>
      </div>
      {note && <p className={styles.note}>{note}</p>}
      <p className={styles.muted}>This recording exists only in this tab. Leaving or reloading the page discards it unless you upload it.</p>
      <div className={styles.row}>
        <Button variant="primary" onClick={onUpload} disabled={uploadDisabled}>Upload recording</Button>
        <Button onClick={onDiscard}>Discard</Button>
      </div>
    </div>
  );
}
