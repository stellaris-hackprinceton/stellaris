import Link from "next/link";
import styles from "./ui.module.css";

export type ArtifactLinkProps = {
  /** Resolved by the caller (route or C's artifactContentUrl). A never builds URLs itself. */
  href: string;
  name: string;
  kind?: string;
  size_bytes?: number | null;
  download?: boolean;
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB"];
  let v = n / 1024, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
}

export function ArtifactLink({ href, name, kind, size_bytes, download }: ArtifactLinkProps) {
  const meta = [kind, size_bytes != null && formatBytes(size_bytes)].filter(Boolean).join(" · ");
  return (
    <span className={styles.artifactLink}>
      {download ? <a href={href} download>{name}</a> : <Link href={href}>{name}</Link>}
      {meta && <span className={styles.meta}>{meta}</span>}
    </span>
  );
}

/** Renders an ISO-8601 timestamp. Absolute time is in the title and machine-readable dateTime. */
export function TimestampLabel({ iso, locale }: { iso: string | null | undefined; locale?: string }) {
  if (!iso) return <span className={styles.meta}>Unknown time</span>;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return <span className={styles.meta}>Invalid time</span>;
  return (
    // Server and browser time zones differ; the browser's local rendering wins.
    <time dateTime={iso} title={d.toISOString()} className={styles.meta} suppressHydrationWarning>
      {d.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" })}
    </time>
  );
}
