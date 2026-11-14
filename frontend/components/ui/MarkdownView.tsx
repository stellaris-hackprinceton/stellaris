import styles from "./ui.module.css";
import { cx } from "./cx";

export type MarkdownViewProps = {
  markdown: string;
  className?: string;
};

/**
 * Safe Markdown display. Until Agent C pins a renderer (HTML disabled, protocol-limited links),
 * this shows the source text verbatim: React escapes it, so nothing executes and no link is live.
 * The public props stay the same when the renderer arrives.
 */
export function MarkdownView({ markdown, className }: MarkdownViewProps) {
  return <div className={cx(styles.markdown, className)}>{markdown}</div>;
}
