"use client";
import Link from "next/link";
import type { ID } from "@/contracts/api";
import { artifactContentUrl } from "@/lib/api";
import { useArtifact } from "@/lib/queries";
import { Skeleton } from "@/components/ui";
import { hrefs } from "@/components/shell";
import styles from "./results.module.css";

/** Backend-authored charts and annotated media only. Nothing is plotted in the browser. */
export function ChartGallery({ project_id, chart_ids, media_ids }: { project_id: ID; chart_ids: ID[]; media_ids: ID[] }) {
  if (chart_ids.length === 0 && media_ids.length === 0) return null;
  return (
    <div className={styles.gallery}>
      {chart_ids.map((id) => <MediaTile key={id} project_id={project_id} id={id} />)}
      {media_ids.map((id) => <MediaTile key={id} project_id={project_id} id={id} />)}
    </div>
  );
}

function MediaTile({ project_id, id }: { project_id: ID; id: ID }) {
  const q = useArtifact(project_id, id);
  const a = q.data;
  if (q.error != null && !a) return <p className={styles.unavailable}>Output unavailable.</p>;
  if (!a) return <Skeleton height="12rem" />;
  const src = artifactContentUrl(project_id, a.id, "inline");
  return (
    <figure className={styles.tile}>
      {a.kind === "video"
        ? <video src={src} controls playsInline preload="metadata" className={styles.media} aria-label={a.filename} />
        : a.mime_type.startsWith("image/") && a.mime_type !== "image/svg+xml"
          // eslint-disable-next-line @next/next/no-img-element -- authenticated API content
          ? <img src={src} alt={a.filename} className={styles.media} loading="lazy" />
          : null}
      <figcaption className={styles.caption}>
        <Link href={hrefs.artifact(project_id, a.id)}>{a.filename}</Link>
        {a.origin === "simulated" && <span className={styles.muted}>simulated</span>}
      </figcaption>
    </figure>
  );
}
