"use client";
import { useId, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import type { Artifact, ID } from "@/contracts/api";
import { useSubmitMessage } from "@/lib/queries";
import { Button, ErrorNotice, IconButton, SendIcon, CloseIcon, describeError, errorCode, newCommandKey } from "@/components/ui";
import { AttachmentPicker } from "./AttachmentPicker";
import styles from "./chat.module.css";

type Props = {
  project_id: ID;
  archived: boolean;
  artifacts: Map<ID, Artifact>;
  draft: ReturnType<typeof useChatDraft>;
};

export function useChatDraft() {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<ID[]>([]);
  const keyRef = useRef<{ key: string; body: string } | null>(null);
  const [failed, setFailed] = useState<unknown>(null);
  return { text, setText, attachments, setAttachments, keyRef, failed, setFailed };
}

const ERROR_TEXT: Record<string, string> = {
  PROJECT_ARCHIVED: "This project is archived. Restore it to send messages.",
  COMMAND_IN_PROGRESS: "The previous send is still being processed. Retry in a moment; it will not be sent twice.",
  IDEMPOTENCY_CONFLICT: "This message changed after an earlier attempt. Send it again as a new message.",
};

/**
 * Text stays in the box until the server accepts it. One idempotency key per send attempt:
 * a retry of the same text reuses it; editing the text after a failure starts a new action.
 */
export function ChatComposer({ project_id, archived, artifacts, draft }: Props) {
  const submit = useSubmitMessage(project_id);
  const id = useId();
  const { text, setText, attachments, setAttachments, keyRef, failed, setFailed } = draft;

  const body = JSON.stringify([text.trim(), attachments]);
  const canSend = !archived && text.trim().length > 0 && !submit.isPending;

  async function send(e?: FormEvent) {
    e?.preventDefault();
    if (!canSend) return;
    if (!keyRef.current || keyRef.current.body !== body) keyRef.current = { key: newCommandKey(), body };
    setFailed(null);
    try {
      await submit.mutateAsync({
        body: { content_markdown: text.trim(), attachment_ids: attachments },
        idempotency_key: keyRef.current.key,
      });
      keyRef.current = null;
      setText("");
      setAttachments([]);
    } catch (err) {
      if (errorCode(err) === "IDEMPOTENCY_CONFLICT") keyRef.current = null;
      setFailed(err);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void send(); }
  }

  const code = errorCode(failed);
  return (
    <form className={styles.composer} onSubmit={send}>
      {archived && <p className={styles.muted}>This project is archived. Chat is read-only until it is restored.</p>}
      {failed != null && (
        <ErrorNotice
          {...describeError(failed, "Message not sent")}
          message={(code && ERROR_TEXT[code]) || describeError(failed).message}
          action={code !== "PROJECT_ARCHIVED" && code !== "IDEMPOTENCY_CONFLICT"
            ? <Button onClick={() => void send()} pending={submit.isPending}>Retry submission</Button>
            : undefined}
        />
      )}
      {attachments.length > 0 && (
        <ul className={styles.chips} aria-label="Selected attachments">
          {attachments.map((id) => (
            <li key={id} className={styles.chip}>
              <span>{artifacts.get(id)?.filename ?? "Attachment"}</span>
              <IconButton label="Remove attachment" icon={<CloseIcon />} className={styles.chipRemove}
                onClick={() => setAttachments((a) => a.filter((x) => x !== id))} />
            </li>
          ))}
        </ul>
      )}
      <label htmlFor={id} className="sr-only">Message</label>
      <textarea
        id={id}
        className={styles.input}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={archived ? "Project archived" : "Ask a question or plan an experiment…"}
        disabled={archived}
        rows={2}
        aria-describedby={`${id}-hint`}
      />
      <div className={styles.composerBar}>
        <AttachmentPicker project_id={project_id} selected={attachments} onChange={setAttachments} disabled={archived} />
        <span id={`${id}-hint`} className={styles.hint}>Ctrl/⌘ + Enter to send</span>
        <Button type="submit" variant="primary" disabled={!canSend} pending={submit.isPending}>
          <SendIcon /> Send
        </Button>
      </div>
    </form>
  );
}
