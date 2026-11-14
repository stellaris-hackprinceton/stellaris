"use client";
import { useEffect, useState } from "react";
import type { ID } from "@/contracts/api";
import { useMessages, useProject } from "@/lib/queries";
import { Button, EmptyState, ErrorNotice, Skeleton, describeError } from "@/components/ui";
import { ChatComposer } from "./ChatComposer";
import { MessageList } from "./MessageList";
import { useArtifactMap, useClaimMap } from "./lookups";
import styles from "./chat.module.css";

export type ResearchChatProps = {
  project_id: ID;
  /** The rail shows its own heading; the sheet already has a title. */
  showHeading?: boolean;
};

/** The project's single chat. Mounted only by ProjectShell. */
export function ResearchChat({ project_id, showHeading = false }: ResearchChatProps) {
  const project = useProject(project_id);
  const messages = useMessages(project_id);
  const claims = useClaimMap(project_id);
  const artifacts = useArtifactMap(project_id);

  // Messages are oldest-first: keep loading pages until the newest persisted message is present.
  const { has_next_page, is_fetching_next_page, load_next_page } = messages;
  useEffect(() => {
    if (has_next_page && !is_fetching_next_page) load_next_page();
  }, [has_next_page, is_fetching_next_page, load_next_page]);

  // Announce assistant status changes (not tokens) to assistive tech.
  const announcement = useStatusAnnouncement(messages.items);

  return (
    <section className={styles.chat} aria-label="Research chat">
      {showHeading && <h2 className={styles.heading}>Research chat</h2>}
      <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
      {messages.error != null && messages.items.length === 0 ? (
        <div className={styles.pad}>
          <ErrorNotice {...describeError(messages.error, "Chat history could not be loaded")}
            action={<Button onClick={messages.refetch}>Try again</Button>} />
        </div>
      ) : messages.is_loading ? (
        <div className={styles.pad}><Skeleton height="4rem" /><Skeleton height="4rem" /></div>
      ) : messages.items.length === 0 ? (
        <div className={styles.pad}>
          <EmptyState title="Start the research conversation">
            Ask a question, request a literature search, or ask Stellaris to design an experiment.
          </EmptyState>
        </div>
      ) : (
        <MessageList messages={messages.items} claims={claims} artifacts={artifacts} loadingNewer={has_next_page} />
      )}
      <ChatComposer project_id={project_id} archived={project.data?.status === "archived"} artifacts={artifacts} />
    </section>
  );
}

/**
 * Announces assistant status changes (never tokens). Uses the "adjust state during render" pattern:
 * the first loaded state is a baseline, so opening the chat does not announce old messages.
 */
function useStatusAnnouncement(items: { id: string; role: string; status: string }[]): string {
  const last = [...items].reverse().find((m) => m.role === "assistant");
  const key = last ? `${last.id}:${last.status}` : "";
  const [prev, setPrev] = useState(key);
  const [text, setText] = useState("");
  if (key !== prev) {
    setPrev(key);
    const [prevId] = prev.split(":");
    if (prev && last) {
      if (last.id === prevId && last.status === "complete") setText("Stellaris finished responding.");
      else if (last.id === prevId && last.status === "interrupted") setText("Stellaris's response was interrupted.");
      else if (last.id !== prevId && last.status === "streaming") setText("Stellaris is responding.");
    }
  }
  return text;
}
