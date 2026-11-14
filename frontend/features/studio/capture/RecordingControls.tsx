"use client";
import { Button } from "@/components/ui";
import { formatElapsed } from "../format";
import type { CameraPhase } from "./useCamera";
import styles from "../studio.module.css";

type Props = {
  phase: CameraPhase;
  elapsed: number;
  maxMs: number;
  canRecord: boolean;
  onStart: () => void;
  onStop: () => void;
  onClose: () => void;
};

export function RecordingControls({ phase, elapsed, maxMs, canRecord, onStart, onStop, onClose }: Props) {
  const recording = phase === "recording";
  return (
    <div className={styles.recordBar}>
      {recording ? (
        <span className={styles.recIndicator} role="status">
          <span className={styles.recDot} aria-hidden="true" /> Recording <span className="num">{formatElapsed(elapsed)}</span>
          <span className={styles.muted}> / {formatElapsed(maxMs)} max</span>
        </span>
      ) : (
        <span className={styles.muted}>Camera on · not recording</span>
      )}
      <div className={styles.row}>
        {recording
          ? <Button variant="danger" onClick={onStop}>Stop recording</Button>
          : <Button variant="primary" onClick={onStart} disabled={phase !== "previewing" || !canRecord}>Start recording</Button>}
        <Button onClick={onClose} disabled={recording}>Turn off camera</Button>
      </div>
    </div>
  );
}
