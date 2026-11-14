"use client";
import { useEffect, useRef, useState } from "react";
import type { ID } from "@/contracts/api";
import { useMessages, useProject } from "@/lib/queries";
import { Button, ErrorNotice, Skeleton, describeError } from "@/components/ui";
import { ResearchIcon, ExperimentIcon, GraphIcon, ExternalIcon } from "@/components/ui/icons";
import { ChatComposer, useChatDraft } from "./ChatComposer";
import { MessageList } from "./MessageList";
import { useArtifactMap, useClaimMap } from "./lookups";
import styles from "./chat.module.css";

export type ResearchChatProps = {
  project_id: ID;
  draft: ReturnType<typeof useChatDraft>;
  /** The rail shows its own heading; the sheet already has a title. */
  showHeading?: boolean;
};

/** The project's single chat. Mounted only by ProjectShell. */
export function ResearchChat({ project_id, draft, showHeading = false }: ResearchChatProps) {
  const surface = useRef<HTMLElement>(null);
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
    <section ref={surface} className={styles.chat} aria-label="Research chat">
      {showHeading && <header className={styles.heading}><ChatHeading /></header>}
      <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
      {messages.error != null && messages.items.length === 0 ? (
        <div className={styles.pad}>
          <ErrorNotice {...describeError(messages.error, "Chat history could not be loaded")}
            action={<Button onClick={messages.refetch}>Try again</Button>} />
        </div>
      ) : messages.is_loading ? (
        <div className={styles.pad}><Skeleton height="4rem" /><Skeleton height="4rem" /></div>
      ) : messages.items.length === 0 ? (
        <div className={styles.welcome}>
          <div className={styles.welcomeMark}><ResearchIcon /></div>
          <h3>Work through your next question.</h3>
          <p>Direct the research here. Sources, experiments, and results stay connected in your workspace.</p>
          <div className={styles.suggestions}>
            {[
              { icon: ResearchIcon, label: "Explore the literature", prompt: "Find relevant public arXiv literature for this project's research question and explain what the retrieved abstracts support." },
              { icon: ExperimentIcon, label: "Design an experiment", prompt: "Help me design a bouncing-ball experiment for this project, including the protocol, calibration, and sources of uncertainty." },
              { icon: GraphIcon, label: "Review the evidence", prompt: "Review the saved evidence in this project. What can we conclude, and what still needs investigation?" },
            ].map(({ icon: Icon, label, prompt }) => <button key={label} disabled={project.data?.status === "archived"} onClick={() => {
              draft.setText(previous => previous.trim() ? `${previous}\n\n${prompt}` : prompt);
              surface.current?.querySelector("textarea")?.focus();
            }}><Icon /><span>{label}</span><ExternalIcon /></button>)}
          </div>
        </div>
      ) : (
        <MessageList messages={messages.items} claims={claims} artifacts={artifacts} loadingNewer={has_next_page} />
      )}
      <ChatComposer draft={draft} project_id={project_id} archived={project.data?.status === "archived"} artifacts={artifacts} />
    </section>
  );
}

function ChatHeading() {
  return <><h2>Research chat</h2><span>Project conversation</span></>;
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
