"use client";
import Link from "next/link";
import type { ID, Run } from "@/contracts/api";
import { runKindLabel, useRun, useWorkspace } from "@/lib/queries";
import { Button, Skeleton, StatusBadge } from "@/components/ui";
import type { StatusTone } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import styles from "./desk.module.css";

export const RUN_STATUS_LABEL: Record<Run["status"], string> = {
  queued: "Queued", running: "Running", awaiting_approval: "Awaiting approval", cancelling: "Cancelling",
  succeeded: "Succeeded", failed: "Failed", cancelled: "Cancelled",
};
export function runTone(status: Run["status"]): StatusTone {
  return status === "failed" ? "error" : status === "awaiting_approval" || status === "cancelled" || status === "cancelling" ? "warning" : status === "succeeded" ? "success" : "info";
}

/** Shown only while runs are active. Real states and messages; no invented tasks or percentages. */
export function ActiveWork({ project_id }: { project_id: ID }) {
  const workspace = useWorkspace(project_id);
  const ids = workspace.data?.active_run_ids ?? [];
  if (workspace.error && !workspace.data) return <section className={styles.strip} aria-label="Active work"><span>Active work could not be loaded.</span><Button onClick={() => void workspace.refetch()}>Retry</Button></section>;
  if (!ids.length) return null;
  return (
    <section className={styles.strip} aria-label="Active work">
      <ul>{ids.slice(0, 3).map((id) => <ActiveRun key={id} project_id={project_id} run_id={id} />)}</ul>
      <div className={styles.links}>
        {ids.length > 3 && <span className={styles.meta}>{ids.length - 3} more active</span>}
        <Link href={hrefs.view(project_id, "runs")}>View active runs</Link>
      </div>
    </section>
  );
}

function ActiveRun({ project_id, run_id }: { project_id: ID; run_id: ID }) {
  const query = useRun(project_id, run_id);
  const run = query.data;
  if (!run) return <li>{query.error ? <><span className={styles.meta}>Run …{run_id.slice(-8)} could not be loaded.</span><Link href={hrefs.run(project_id, run_id)}>Open run</Link></> : <Skeleton width="60%" />}</li>;
  const fraction = run.progress.fraction;
  return (
    <li>
      <StatusBadge tone={runTone(run.status)}>{RUN_STATUS_LABEL[run.status]}</StatusBadge>
      <strong>{runKindLabel(run.input.kind)}</strong>
      {(run.progress.message || run.phase) && <span>{run.progress.message || run.phase}</span>}
      {fraction != null && <span className={styles.meta}>{Math.round(fraction * 100)}%</span>}
      <Link href={hrefs.run(project_id, run.id)}>{run.status === "awaiting_approval" ? "Review approval" : "Open run"}</Link>
    </li>
  );
}
