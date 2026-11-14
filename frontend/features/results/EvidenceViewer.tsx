"use client";
import Link from "next/link";
import { useEffect, useRef } from "react";
import type { EvidenceRef, ID } from "@/contracts/api";
import { artifactContentUrl } from "@/lib/api";
import { useArtifact } from "@/lib/queries";
import { Skeleton, StatusBadge } from "@/components/ui";
import { hrefs } from "@/components/shell";
import styles from "./results.module.css";

function locator(ev: EvidenceRef): string {
  return [
    ev.frame_index != null && `frame ${ev.frame_index}`,
    ev.time_s != null && `t = ${ev.time_s} s`,
    ev.row_index != null && `row ${ev.row_index}`,
  ].filter(Boolean).join(" · ") || "whole file";
}

/**
 * Opens one piece of evidence. Video seeks to time_s, which is approximate in browsers: the frame
 * index reported by the analysis is shown, but this view does not claim exact frame navigation.
 */
export function EvidenceViewer({ project_id, evidence }: { project_id: ID; evidence: EvidenceRef }) {
  const q = useArtifact(project_id, evidence.artifact_id);
  const a = q.data;
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const v = videoRef.current;
    if (!v || evidence.time_s == null) return;
    const seek = () => { v.currentTime = evidence.time_s ?? 0; };
    if (v.readyState >= 1) seek(); else v.addEventListener("loadedmetadata", seek, { once: true });
    return () => v.removeEventListener("loadedmetadata", seek);
  }, [evidence.time_s, a?.id]);

  if (q.error != null && !a) return <p className={styles.unavailable}>Evidence file unavailable.</p>;
  if (!a) return <Skeleton height="8rem" />;
  const inline = artifactContentUrl(project_id, a.id, "inline");

  return (
    <figure className={styles.evidence}>
      {a.kind === "image" || a.kind === "chart" ? (
        // eslint-disable-next-line @next/next/no-img-element -- authenticated API content
        <img src={inline} alt={`${a.filename}, ${locator(evidence)}`} className={styles.media} />
      ) : a.kind === "video" ? (
        <video ref={videoRef} src={inline} controls playsInline preload="metadata" className={styles.media}
          aria-label={`${a.filename}, ${locator(evidence)}`} />
      ) : null}
      <figcaption className={styles.caption}>
        <Link href={hrefs.artifact(project_id, a.id)}>{a.filename}</Link>
        <span className={styles.muted}>{locator(evidence)}</span>
        {a.origin === "simulated" && <StatusBadge tone="warning">Simulated</StatusBadge>}
        {a.kind === "video" && evidence.time_s != null && (
          <span className={styles.muted}>Seek is approximate; it may not land on the exact analysed frame.</span>
        )}
        {a.kind === "dataset" && evidence.row_index != null && (
          <span className={styles.muted}>Open the dataset in Workspace and go to row {evidence.row_index}.</span>
        )}
      </figcaption>
    </figure>
  );
}
