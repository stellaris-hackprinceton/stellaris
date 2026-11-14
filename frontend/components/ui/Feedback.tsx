import type { ReactNode } from "react";
import styles from "./ui.module.css";
import { cx } from "./cx";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "error";
const toneClass: Record<StatusTone, string> = {
  neutral: styles.neutral, info: styles.info, success: styles.success, warning: styles.warning, error: styles.errorTone,
};
const toneGlyph: Record<StatusTone, string> = { neutral: "○", info: "●", success: "✓", warning: "!", error: "✕" };

/** Color is never the only signal: a glyph and text always accompany it. Use "success" only for confirmed server state. */
export function StatusBadge({ tone = "neutral", children }: { tone?: StatusTone; children: ReactNode }) {
  return (
    <span className={cx(styles.badge, toneClass[tone])}>
      <span aria-hidden="true">{toneGlyph[tone]}</span>
      {children}
    </span>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>{title}</p>
      {children && <div className={styles.emptyBody}>{children}</div>}
      {action}
    </div>
  );
}

export type ErrorNoticeProps = {
  title: string;
  message?: string;
  /** Server error code, e.g. EVENT_CURSOR_EXPIRED. */
  code?: string;
  request_id?: string | null;
  action?: ReactNode;
};

export function ErrorNotice({ title, message, code, request_id, action }: ErrorNoticeProps) {
  return (
    <div role="alert" className={styles.notice}>
      <p className={styles.noticeTitle}>{title}</p>
      {message && <p>{message}</p>}
      {(code || request_id) && (
        <p className={styles.noticeMeta}>{[code, request_id && `request ${request_id}`].filter(Boolean).join(" · ")}</p>
      )}
      {action}
    </div>
  );
}

export function Skeleton({ width = "100%", height }: { width?: string; height?: string }) {
  return <span aria-hidden="true" className={styles.skeleton} style={{ width, height }} />;
}
