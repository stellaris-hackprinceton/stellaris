"use client";
import Link from "next/link";
import { hrefs } from "@/components/shell/hrefs";
import type { ID } from "@/contracts/api";
import { useCapabilities, useExperiments } from "@/lib/queries";
import { Button, EmptyState, ErrorNotice, Skeleton, describeError } from "@/components/ui";
import { ExperimentSummary } from "./ExperimentSummary";
import styles from "./canvas.module.css";

export function ExperimentsSection({ project_id }: { project_id: ID }) {
  const experiments = useExperiments(project_id);
  const caps = useCapabilities();

  if (experiments.error != null && experiments.items.length === 0) {
    return <ErrorNotice {...describeError(experiments.error, "Experiment plans could not be loaded")} action={<Button onClick={experiments.refetch}>Try again</Button>} />;
  }
  if (experiments.is_loading) return <Skeleton height="10rem" />;
  if (experiments.items.length === 0) {
    return (
      <EmptyState title="No experiment plans yet" action={<Link href={hrefs.studio(project_id)}>Open experiments</Link>}>
        {caps.data?.features.experiment_design
          ? "Create a plan in Experiments, or ask Assistant to draft one for your question."
          : "Create a plan in Experiments. Agent-assisted experiment design is unavailable on this server."}
      </EmptyState>
    );
  }
  return (
    <div className={styles.stack}>
      <p className={styles.muted}>Plans describe what to do. Results appear only after an analysis run.</p>
      <ul className={styles.list} aria-label="Experiment plans">
        {experiments.items.map((x) => <li key={x.id}><ExperimentSummary project_id={project_id} experiment={x} /></li>)}
      </ul>
      {experiments.has_next_page && (
        <Button onClick={experiments.load_next_page} pending={experiments.is_fetching_next_page}>Load more plans</Button>
      )}
    </div>
  );
}
