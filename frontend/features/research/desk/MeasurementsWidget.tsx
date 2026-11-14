"use client";
import Link from "next/link";
import type { ID, Measurement } from "@/contracts/api";
import { useExperiment, useMeasurements, useRun, useRunResults } from "@/lib/queries";
import { useCatalogView } from "@/lib/queries/views";
import { Button, ErrorNotice, Skeleton, StatusBadge, describeError } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import { RUN_STATUS_LABEL, runTone } from "./ActiveWork";
import { ListState, MediaPreview, Widget, WidgetFooter, dateLabel, listHasBlockingState, useDisclosure } from "./Widget";
import styles from "./desk.module.css";

const nf = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 6 });
const ORIGIN: Record<Measurement["data_origin"], string> = { observed: "Observed", derived: "Derived", simulated: "Simulated" };
const CALIBRATION: Record<Measurement["calibration_mode"], string> = { none: "Uncalibrated (no physical scale)", reference_length: "Reference-length calibration" };
const unit = (u: string) => (u === "1" ? "dimensionless" : u);

/** Latest projected measurement set: resolved from run_measurements, never from an unrelated latest chart. */
export function MeasurementsWidget({ project_id }: { project_id: ID }) {
  const disclosure = useDisclosure(1, 1);
  const list = useCatalogView(project_id, { origin_type: "run_measurements", sort: "created_at", order: "desc" }, 1);
  const runId = list.items[0]?.origin?.id ?? null;
  const blocked = listHasBlockingState(list);
  return (
    <Widget id="desk-measurements" title="Measurements and results"
      footer={<WidgetFooter label="measurements" canExpand={!!runId} expanded={disclosure.expanded} onToggle={disclosure.toggle} viewAll={hrefs.materialsView(project_id, "measurements")} />}>
      {blocked ? <ListState list={list} what="Measurements" skeletons={1} /> : !runId ? <p className={styles.empty}>Analyze an experiment to save measurements.</p> : <MeasurementSet project_id={project_id} run_id={runId} expanded={disclosure.expanded} />}
    </Widget>
  );
}

function MeasurementSet({ project_id, run_id, expanded }: { project_id: ID; run_id: ID; expanded: boolean }) {
  const run = useRun(project_id, run_id), results = useRunResults(project_id, run_id);
  const rows = useMeasurements(project_id, run_id, { limit: expanded ? 10 : 3 });
  const experiment = useExperiment(project_id, run.data?.input.kind === "analysis" ? run.data.input.experiment_id : null);
  if ((run.error && !run.data) || (results.error && !results.data)) return <ErrorNotice {...describeError(run.error ?? results.error, "The latest measurement set could not be loaded")} action={<Button onClick={() => { void run.refetch(); void results.refetch(); }}>Retry</Button>} />;
  if (!run.data || !results.data) return <Skeleton height="10rem" />;
  const r = run.data, res = results.data;
  const partial = r.status === "failed" || r.status === "cancelled";
  const charts = expanded ? res.chart_artifact_ids : res.chart_artifact_ids.slice(0, 1);
  const media = expanded ? res.annotated_media_artifact_ids : [];
  const sample = rows.items.slice(0, expanded ? 10 : 3);
  return (
    <div className={styles.stack}>
      <p style={{ margin: 0 }}>
        <strong>{experiment.data?.title ?? (experiment.error ? "Experiment record unavailable" : r.input.kind === "analysis" ? "Loading experiment…" : "Analysis run")}</strong>
        <span className={styles.meta}> · run …{r.id.slice(-8)} · executed {dateLabel(r.started_at ?? r.created_at)}</span>
      </p>
      <div className={styles.badges}>
        <StatusBadge tone={runTone(r.status)}>{partial ? `Partial evidence · ${r.status}` : RUN_STATUS_LABEL[r.status]}</StatusBadge>
        <span className={styles.meta}>{res.measurement_count} saved measurement{res.measurement_count === 1 ? "" : "s"}</span>
      </div>
      {charts.length || media.length
        ? <div className={styles.mediaGrid}>{[...charts, ...media].map((id) => <MediaPreview key={id} project_id={project_id} artifact_id={id} />)}</div>
        : <p className={styles.meta}>No saved chart for this run.</p>}
      {rows.error && !rows.items.length ? <ErrorNotice {...describeError(rows.error, "Measurement rows could not be loaded")} action={<Button onClick={() => void rows.refetch()}>Retry</Button>} />
        : rows.is_loading ? <Skeleton height="4rem" />
          : sample.length > 0 && <div className={styles.tableWrap}>
            <table className={styles.table}>
              <caption>Sample of saved measurements</caption>
              <thead><tr><th scope="col">Quantity</th><th scope="col">Value</th><th scope="col">Unit</th><th scope="col">Uncertainty</th><th scope="col">Origin</th><th scope="col">Calibration</th></tr></thead>
              <tbody>{sample.map((m) => <tr key={m.id}>
                <td>{m.quantity}{m.series ? <span className={styles.meta}> · {m.series}</span> : null}</td>
                <td className={styles.num} title={m.value != null ? String(m.value) : undefined}>{m.status === "missing" ? "Missing" : m.status === "rejected" ? "Rejected" : m.value != null ? nf.format(m.value) : "Missing"}</td>
                <td>{unit(m.unit)}</td>
                <td>{m.uncertainty.absolute != null ? `±${nf.format(m.uncertainty.absolute)}${m.uncertainty.method ? ` (${m.uncertainty.method})` : ""}` : "Uncertainty not recorded"}</td>
                <td>{ORIGIN[m.data_origin]}</td>
                <td>{CALIBRATION[m.calibration_mode]}</td>
              </tr>)}</tbody>
            </table>
          </div>}
      <p className={styles.meta}>Rows are a sample in saved order, not aggregate statistics or the latest value of each series.</p>
      {res.warnings.length > 0 && <div>
        <ul className={styles.meta} style={{ margin: 0, paddingLeft: "1.2em" }}>{res.warnings.slice(0, 2).map((w, i) => <li key={`${w.code}:${i}`}>{w.message}</li>)}</ul>
        {res.warnings.length > 2 && <details className={styles.details}><summary>{res.warnings.length - 2} more saved warning{res.warnings.length - 2 === 1 ? "" : "s"}</summary><ul>{res.warnings.slice(2).map((w, i) => <li key={`${w.code}:${i}`}>{w.message}</li>)}</ul></details>}
      </div>}
      <div className={styles.links}><Link href={hrefs.run(project_id, r.id)}>Inspect this run&apos;s results</Link></div>
    </div>
  );
}
