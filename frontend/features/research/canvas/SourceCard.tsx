import type { Source } from "@/contracts/api";
import { StatusBadge } from "@/components/ui";
import { PROVIDER_LABEL, RETRIEVAL_LABEL, authorLine } from "./labels";
import styles from "./canvas.module.css";

export function SourceCard({ source, selected, onSelect }: { source: Source; selected: boolean; onSelect: () => void }) {
  const r = RETRIEVAL_LABEL[source.retrieval_status];
  return (
    <button type="button" className={styles.card} aria-pressed={selected} onClick={onSelect}>
      <span className={styles.cardTitle}>{source.title}</span>
      <span className={styles.muted}>{authorLine(source.authors)}{source.published_at ? ` · ${source.published_at}` : ""}</span>
      <span className={styles.row}>
        <span className={styles.muted}>{PROVIDER_LABEL[source.provider]}</span>
        <StatusBadge tone={r.tone}>{r.text}</StatusBadge>
      </span>
    </button>
  );
}
