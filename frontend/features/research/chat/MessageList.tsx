"use client";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Artifact, Claim, ID, Message } from "@/contracts/api";
import { ArrowDownIcon, Button } from "@/components/ui";
import { MessageItem } from "./MessageItem";
import styles from "./chat.module.css";

const NEAR_END_PX = 96;

type Props = {
  messages: Message[];
  claims: Map<ID, Claim>;
  artifacts: Map<ID, Artifact>;
  loadingNewer: boolean;
};

/**
 * Oldest-first list. Follows new content only while the reader is near the end; otherwise
 * offers "New activity" instead of yanking the scroll position.
 */
export function MessageList({ messages, claims, artifacts, loadingNewer }: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const nearEnd = useRef(true);
  const [hasUnseen, setHasUnseen] = useState(false);

  // A signature that changes when a message is added, grows, or changes status.
  const last = messages[messages.length - 1];
  const signature = `${messages.length}:${last?.id}:${last?.content_markdown.length}:${last?.status}`;

  function scrollToEnd() {
    const el = scroller.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    nearEnd.current = true;
    setHasUnseen(false);
  }

  useLayoutEffect(() => {
    if (nearEnd.current) scrollToEnd();
    else setHasUnseen(true);
  }, [signature]);

  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const onScroll = () => {
      nearEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_END_PX;
      if (nearEnd.current) setHasUnseen(false);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className={styles.listWrap}>
      <div ref={scroller} className={styles.list} tabIndex={0} aria-label="Conversation history">
        {messages.map((m) => (
          <MessageItem key={m.id} message={m} claims={claims} artifacts={artifacts} />
        ))}
        {loadingNewer && <p className={styles.muted} role="status">Loading the latest messages…</p>}
      </div>
      {hasUnseen && (
        <div className={styles.newActivity}>
          <Button onClick={scrollToEnd}><ArrowDownIcon /> New activity</Button>
        </div>
      )}
    </div>
  );
}
