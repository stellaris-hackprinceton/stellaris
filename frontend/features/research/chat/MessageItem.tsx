import Link from "next/link";
import type { Artifact, Claim, ID, Message } from "@/contracts/api";
import { MarkdownView, StatusBadge, TimestampLabel } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import { CitationLink } from "./CitationLink";
import styles from "./chat.module.css";

type Props = {
  message: Message;
  claims: Map<ID, Claim>;
  artifacts: Map<ID, Artifact>;
};

export function MessageItem({ message, claims, artifacts }: Props) {
  const p = message.project_id;
  const isUser = message.role === "user";
  return (
    <article className={styles.message} data-role={message.role} aria-label={isUser ? "You" : "Stellaris"}>
      <header className={styles.messageMeta}>
        <span className={styles.author}>{isUser ? "You" : "Stellaris"}</span>
        <TimestampLabel iso={message.created_at} />
        {message.status === "streaming" && <StatusBadge tone="info">Responding</StatusBadge>}
        {message.status === "interrupted" && <StatusBadge tone="warning">Interrupted</StatusBadge>}
      </header>

      {message.content_markdown ? (
        <MarkdownView markdown={message.content_markdown} />
      ) : message.status === "streaming" ? (
        <p className={styles.muted}>Working on it…</p>
      ) : null}

      {message.status === "interrupted" && (
        <p className={styles.muted}>This response stopped early. Text and evidence saved before it stopped are kept.</p>
      )}

      {message.attachment_ids.length > 0 && (
        <ul className={styles.chips} aria-label="Attachments">
          {message.attachment_ids.map((id) => {
            const a = artifacts.get(id);
            return (
              <li key={id}>
                <Link href={hrefs.artifact(p, id)} className={styles.chip} title={a ? undefined : id}>
                  {a ? a.filename : "Attachment"}
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      {message.claim_ids.length > 0 && (
        <ul className={styles.citations} aria-label="Claims">
          {message.claim_ids.map((id) => (
            <li key={id}><CitationLink project_id={p} claim_id={id} claim={claims.get(id)} /></li>
          ))}
        </ul>
      )}

      {message.run_id && !isUser && (
        <Link href={hrefs.run(p, message.run_id)} className={styles.runLink}>View this run</Link>
      )}
    </article>
  );
}
