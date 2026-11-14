"use client";
import { useProjectRuntime } from "@/providers";
import { Button } from "@/components/ui";
import type { StatusTone } from "@/components/ui";
import styles from "./shell.module.css";

const LABELS: Record<string, { tone: StatusTone; text: string }> = {
  connecting: { tone: "neutral", text: "Connecting" },
  connected: { tone: "info", text: "Live" },
  reconnecting: { tone: "warning", text: "Reconnecting" },
  offline: { tone: "error", text: "Live updates stopped" },
};

/** Shows the event-stream state only. It never implies anything about run state. */
export function ConnectionStatus() {
  const { connection, reconnect } = useProjectRuntime();
  const label = LABELS[connection] ?? LABELS.connecting;
  return (
    <div className={styles.connection} role="status" aria-live="polite">
      <span className={styles.connectionLabel} data-state={connection}><span aria-hidden="true" />{label.text}</span>
      {connection === "offline" && <Button onClick={reconnect}>Reconnect</Button>}
    </div>
  );
}
