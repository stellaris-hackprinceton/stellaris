"use client";
import { useEffect, useRef } from "react";
import styles from "../studio.module.css";

/** Live preview only. Never mirrored, so what you see matches what is recorded and analysed. */
export function CameraPreview({ stream }: { stream: MediaStream | null }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    v.srcObject = stream;
    if (stream) void v.play().catch(() => { /* autoplay blocked: user can still record */ });
    return () => { v.srcObject = null; };
  }, [stream]);
  return <video ref={ref} className={styles.media} muted playsInline aria-label="Live camera preview" />;
}
