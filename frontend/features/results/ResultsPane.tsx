"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { ID } from "@/contracts/api";
import { useCapabilities, useRun, useRunResults } from "@/lib/queries";
import { Button, EmptyState, ErrorNotice, Skeleton, describeError } from "@/components/ui";
import { hrefs } from "@/components/shell";
import { ChartGallery } from "./ChartGallery";
import { MeasurementTable } from "./MeasurementTable";
import { ScientificWarnings } from "./ScientificWarnings";
import { SeriesSelector } from "./SeriesSelector";
import { UncertaintyDetails } from "./UncertaintyDetails";
import { AUTO_LOAD_ROWS, useAllMeasurements } from "./useAllMeasurements";
import styles from "./results.module.css";

export type ResultsPaneProps = { project_id: ID; run_id: ID };

/**
 * Scientific results for one run. Mountable in Studio or Execution; it reads C's hooks and never
 * opens its own event stream. Selecting a historical run shows that run's evidence as recorded.
 */
export function ResultsPane({ project_id, run_id }: ResultsPaneProps) {
  const capabilities = useCapabilities();
  const run = useRun(project_id, run_id);
  const results = useRunResults(project_id, run_id);
  const ms = useAllMeasurements(project_id, run_id);
  const [series, setSeries] = useState("");
  const [selected, setSelected] = useState<ID | null>(null);

  const allSeries = useMemo(() => [...new Set(ms.items.map((m) => m.series))].sort(), [ms.items]);
  const shown = series ? ms.items.filter((m) => m.series === series) : ms.items;
  const selectedM = selected ? ms.items.find((m) => m.id === selected) : undefined;

  if (run.error != null && !run.data) {
    return <EmptyState title="Run unavailable">This run does not exist in this project or could not be loaded.</EmptyState>;
  }
  if (!run.data) return <Skeleton height="12rem" />;
  const r = run.data;
  const res = results.data;
  const total = res?.measurement_count ?? null;
  const analysisInputs = r.input.kind === "analysis" ? r.input.input_artifact_ids : [];

  return (
    <div className={styles.pane}>
      <ScientificWarnings run={r} results={res} measurements={ms.items} />
      {r.result_summary && <p className="prose">{r.result_summary}</p>}

      {res && <ChartGallery project_id={project_id} chart_ids={res.chart_artifact_ids} media_ids={res.annotated_media_artifact_ids} />}
      {results.error != null && !res && (
        <ErrorNotice {...describeError(results.error, "Result summary could not be loaded")} action={<Button onClick={results.refetch}>Try again</Button>} />
      )}

      <section className={styles.stack} aria-labelledby={`meas-${run_id}`}>
        <div className={styles.toolbar}>
          <h4 id={`meas-${run_id}`}>Measurements</h4>
          <span className={styles.muted} aria-live="polite">
            {ms.items.length}{total != null ? ` of ${total}` : ""} loaded{ms.is_fetching_next_page ? " · loading…" : ""}
          </span>
          <SeriesSelector series={allSeries} value={series} onChange={setSeries} />
        </div>
        {ms.error != null && ms.items.length === 0 ? (
          <ErrorNotice {...describeError(ms.error, "Measurements could not be loaded")} action={<Button onClick={ms.refetch}>Try again</Button>} />
        ) : ms.is_loading ? (
          <Skeleton height="10rem" />
        ) : ms.items.length === 0 ? (
          <EmptyState title={r.status === "queued" || r.status === "running" ? "No measurements yet" : "No measurements"}>
            {r.status === "queued" || r.status === "running"
              ? "Measurements appear here as the analysis saves them."
              : "This run did not save any measurements."}
          </EmptyState>
        ) : (
          <div className={styles.split}>
            <MeasurementTable measurements={shown} selected={selected} onSelect={setSelected} />
            {selectedM && <UncertaintyDetails project_id={project_id} m={selectedM} onClose={() => setSelected(null)} />}
          </div>
        )}
        {ms.has_next_page && ms.items.length >= AUTO_LOAD_ROWS && (
          <Button onClick={ms.load_next_page} pending={ms.is_fetching_next_page}>Load more measurements</Button>
        )}
      </section>

      {res && res.claim_ids.length > 0 && (
        <p className={styles.muted}>
          This run saved {res.claim_ids.length} finding{res.claim_ids.length === 1 ? "" : "s"}.{" "}
          <Link href={hrefs.research(project_id, { tab: "findings", claim: res.claim_ids[0] })}>Review findings</Link>
        </p>
      )}

      <section className={styles.provenance} aria-label="Provenance">
        <h4 className={styles.smallLabel}>Trace back</h4>
        <ul className={styles.inlineList}>
          {analysisInputs.map((id) => <li key={id}><Link href={hrefs.artifact(project_id, id)}>Raw input</Link></li>)}
          {r.provenance_artifact_id
            ? <li><Link href={hrefs.artifact(project_id, r.provenance_artifact_id)}>Provenance manifest</Link></li>
            : <li className={styles.muted}>Provenance manifest not yet saved</li>}
          <li><Link href={hrefs.run(project_id, r.id)}>Run details and logs</Link></li>
          {r.input.kind === "analysis" && capabilities.data?.features.markdown_reports && <li><Link href={hrefs.reports(project_id, { compose: true, experiment: r.input.experiment_id, evidence_run: r.id })}>Generate report</Link></li>}
          {res?.report_artifact_id && <li><Link href={hrefs.report(project_id, res.report_artifact_id)}>Report</Link></li>}
        </ul>
      </section>
    </div>
  );
}
