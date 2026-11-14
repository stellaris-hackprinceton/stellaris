"use client";
import { useEffect, useSyncExternalStore } from "react";
import type { Capabilities } from "@/contracts/api";
import { Button, ErrorNotice } from "@/components/ui";
import { CameraPreview } from "./CameraPreview";
import { RecordingControls } from "./RecordingControls";
import { RecordingReview } from "./RecordingReview";
import { cameraSupported, pickRecorderMime, useCamera } from "./useCamera";
import type { CameraError, Recording } from "./useCamera";
import styles from "../studio.module.css";

const ERROR_TEXT: Record<CameraError, { title: string; message: string }> = {
  denied: { title: "Camera permission was denied", message: "Allow camera access in your browser's site settings and try again, or import a video file instead." },
  unavailable: { title: "No camera is available", message: "This browser or device does not provide a camera. Import a video file instead." },
  device_lost: { title: "The camera stopped", message: "Permission was revoked or the device was disconnected. Any recording in progress was discarded." },
  no_supported_format: { title: "This browser can't record a format the server accepts", message: "Record with your device's camera app and import the file instead." },
  recorder_failed: { title: "Recording failed", message: "The browser's recorder stopped unexpectedly. Try again or import a video file." },
};

type Props = {
  uploads: Capabilities["uploads"] | undefined;
  disabled: boolean;
  /** Hand the reviewed recording to the shared upload controller. */
  onUpload: (r: Recording) => void;
  uploadBusy: boolean;
  /** The Blob the upload controller has committed, if any. */
  uploadedBlob: Blob | null;
  /** Keep route-level discard prompts in sync with an active or unuploaded capture. */
  onUnsavedChange?: (unsaved: boolean) => void;
};

const noopSubscribe = () => () => {};

export function CapturePanel({ uploads, disabled, onUpload, uploadBusy, uploadedBlob, onUnsavedChange }: Props) {
  const cam = useCamera(uploads);
  // Browser capability is only knowable on the client; null during server render.
  const supported = useSyncExternalStore<boolean | null>(noopSubscribe, cameraSupported, () => null);
  const canRecord = Boolean(uploads && pickRecorderMime(uploads.accepted_mime_types));

  // Warn before leaving while an unuploaded recording or live capture exists.
  const uploaded = Boolean(cam.recording && uploadedBlob === cam.recording.blob);
  const unsaved = cam.phase === "recording" || (cam.phase === "reviewing" && !uploaded);
  useEffect(() => {
    onUnsavedChange?.(unsaved);
    return () => onUnsavedChange?.(false);
  }, [onUnsavedChange, unsaved]);
  useEffect(() => {
    if (!unsaved) return;
    const h = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [unsaved]);

  if (supported === false) {
    return <p className={styles.muted}>This browser can’t record from a camera here. Use “Import a file”.</p>;
  }

  switch (cam.phase) {
    case "idle":
      return (
        <div className={styles.stack}>
          <p className={styles.muted}>The camera turns on only when you press the button. Video only; no microphone.</p>
          <div><Button variant="primary" onClick={() => void cam.enable()} disabled={disabled || !uploads || supported === null}>Enable camera</Button></div>
          {uploads && !canRecord && supported && (
            <p className={styles.note}>This browser can preview but can’t record a format the server accepts. Import a file instead.</p>
          )}
        </div>
      );
    case "requesting_permission":
      return <p className={styles.muted} role="status">Waiting for camera permission…</p>;
    case "previewing":
    case "recording":
      return (
        <div className={styles.stack}>
          <CameraPreview stream={cam.stream} />
          <RecordingControls phase={cam.phase} elapsed={cam.elapsed} maxMs={uploads?.max_video_duration_ms ?? 0}
            canRecord={canRecord} onStart={cam.start} onStop={cam.stop} onClose={cam.discard} />
        </div>
      );
    case "reviewing":
      return cam.recording ? (
        <RecordingReview recording={cam.recording} uploadDisabled={disabled || uploadBusy} uploaded={uploaded}
          onUpload={() => cam.recording && onUpload(cam.recording)} onDiscard={cam.discard} />
      ) : null;
    case "error": {
      const t = ERROR_TEXT[cam.error ?? "unavailable"];
      return <ErrorNotice title={t.title} message={t.message} action={<Button onClick={cam.discard}>OK</Button>} />;
    }
  }
}
