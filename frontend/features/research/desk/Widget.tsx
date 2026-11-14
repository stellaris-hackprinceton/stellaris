"use client";
/* eslint-disable @next/next/no-img-element -- authenticated artifact content cannot use the image optimizer. */
import Link from "next/link";
import { useState } from "react";
import type { ReactNode } from "react";
import type { ID } from "@/contracts/api";
import { artifactContentUrl } from "@/lib/api";
import { useArtifact } from "@/lib/queries";
import type { CatalogViewUnsupported } from "@/lib/queries/views";
import { Button, ErrorNotice, Skeleton, describeError } from "@/components/ui";
import { PlusIcon } from "@/components/ui/icons";
import { hrefs } from "@/components/shell/hrefs";
import styles from "./desk.module.css";

export const ARCHIVED_NOTE = "Restore project to add or generate material.";

export function Widget({ id, title, wide = false, action, children, footer }: {
  id: string; title: string; wide?: boolean; action?: ReactNode; children: ReactNode; footer?: ReactNode;
}) {
  return (
    <section className={`${styles.widget} ${wide ? styles.full : styles.half}`} aria-labelledby={id}>
      <div className={styles.widgetHead}><h2 id={id}>{title}</h2>{action}</div>
      {children}
      {footer}
    </section>
  );
}

/** Expand reveals the bounded preview; View all navigates. The toggle keeps focus because it stays mounted. */
export function WidgetFooter({ canExpand, expanded, onToggle, viewAll, label }: {
  canExpand: boolean; expanded: boolean; onToggle: () => void; viewAll: string; label: string;
}) {
  return (
    <div className={styles.footer}>
      {canExpand || expanded
        ? <Button aria-expanded={expanded} onClick={onToggle}>{expanded ? `Collapse ${label}` : `Expand ${label}`}</Button>
        : <span />}
      <Link href={viewAll}>View all {label}</Link>
    </div>
  );
}

/** Disclosure state local to the mounted overview. */
export function useDisclosure(preview: number, max: number) {
  const [expanded, setExpanded] = useState(false);
  return { expanded, toggle: () => setExpanded((v) => !v), limit: (expanded ? max : preview) + 1, shown: expanded ? max : preview, preview };
}

export function AddTile({ label, onClick, href, disabled, expanded, controls }: {
  label: string; onClick?: () => void; href?: string; disabled?: boolean; expanded?: boolean; controls?: string;
}) {
  const body = <><PlusIcon /><span>{label}</span></>;
  if (href && !disabled) return <Link className={styles.tile} href={href}>{body}</Link>;
  return <button type="button" className={styles.tile} onClick={onClick} disabled={disabled} aria-expanded={expanded} aria-controls={controls}>{body}</button>;
}

export function CardSkeleton() {
  return <div className={styles.card} aria-hidden="true"><Skeleton height="1.25rem" /><Skeleton width="70%" /><Skeleton width="45%" /></div>;
}
export function CardSkeletons({ count }: { count: number }) {
  return <>{Array.from({ length: count }, (_, i) => <li key={i}><CardSkeleton /></li>)}</>;
}

/** Distinct messages for unsupported capability, list failure, and pagination failure. */
export function ListState({ list, what, skeletons }: {
  list: { unsupported: CatalogViewUnsupported; is_loading: boolean; capability_pending: boolean; capability_error: unknown; error: unknown; items: unknown[]; refetch: () => unknown };
  what: string; skeletons: number;
}) {
  if (list.unsupported === "catalog") return <p className={styles.empty}>Richer views are unavailable: this backend does not provide the project catalog. Existing tools in Materials and Experiments remain available.</p>;
  if (list.unsupported === "views") return <p className={styles.empty}>Richer views are unavailable: this backend does not advertise the workspace views extension.</p>;
  if (list.capability_error) return <ErrorNotice {...describeError(list.capability_error, "Backend capabilities could not be loaded")} />;
  if (list.is_loading || list.capability_pending) return <ul className={styles.cards} aria-busy="true"><CardSkeletons count={skeletons} /></ul>;
  if (list.error && list.items.length === 0) return <ErrorNotice {...describeError(list.error, `${what} could not be loaded`)} action={<Button onClick={() => void list.refetch()}>Retry</Button>} />;
  return null;
}

/** Whether ListState will replace the list body (pagination errors with loaded rows stay local). */
export function listHasBlockingState(list: { unsupported: CatalogViewUnsupported; is_loading: boolean; capability_pending: boolean; capability_error: unknown; error: unknown; items: unknown[] }) {
  return !!list.unsupported || !!list.capability_error || list.is_loading || list.capability_pending || (!!list.error && list.items.length === 0);
}

export function CardError({ what, error, retry }: { what: string; error: unknown; retry: () => unknown }) {
  return <div className={styles.card}><ErrorNotice {...describeError(error, `${what} could not be loaded`)} action={<Button onClick={() => void retry()}>Retry</Button>} /></div>;
}

/** Saved chart or media preview: contain sizing, 200px maximum, title and Open stay usable on failure. */
export function MediaPreview({ project_id, artifact_id }: { project_id: ID; artifact_id: ID }) {
  const query = useArtifact(project_id, artifact_id);
  const [failed, setFailed] = useState(false);
  const a = query.data;
  if (query.error && !a) return <p className={styles.unavailable}>Saved output unavailable. <Button onClick={() => void query.refetch()}>Retry</Button></p>;
  if (!a) return <Skeleton height="120px" />;
  if (a.project_id !== project_id) return <p className={styles.unavailable}>Saved output unavailable in this project.</p>;
  const src = artifactContentUrl(project_id, a.id, "inline");
  const image = a.mime_type.startsWith("image/") && a.mime_type !== "image/svg+xml";
  return (
    <figure className={styles.media}>
      {failed ? <p className={styles.unavailable}>Preview could not be displayed.</p>
        : image ? <img src={src} alt={a.filename} loading="lazy" onError={() => setFailed(true)} />
          : a.kind === "video" ? <video src={src} controls preload="metadata" aria-label={a.filename} onError={() => setFailed(true)} />
            : null}
      <figcaption className={styles.links}>
        <span className={styles.meta}>{a.filename}{a.origin === "simulated" ? " · simulated" : ""}</span>
        <Link href={hrefs.artifact(project_id, a.id)}>Open</Link>
      </figcaption>
    </figure>
  );
}

export const dateLabel = (iso: string) => new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
