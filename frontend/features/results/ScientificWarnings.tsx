import type { Measurement, Run, RunResults } from "@/contracts/api";
import { StatusBadge } from "@/components/ui";
import styles from "./results.module.css";

type Props = { run: Run; results: RunResults | undefined; measurements: Measurement[] };

/** Qualifications that must travel with the numbers. */
export function ScientificWarnings({ run, results, measurements }: Props) {
  const simulated = measurements.some((m) => m.data_origin === "simulated");
  const uncalibrated = measurements.some((m) => m.calibration_mode === "none");
  const warnings = results?.warnings ?? [];
  const status = run.status;

  return (
    <div className={styles.warnings}>
      {(status === "queued" || status === "running" || status === "awaiting_approval" || status === "cancelling") && (
        <p className={styles.banner} data-tone="info" role="status">
          <StatusBadge tone="info">Run {status.replace("_", " ")}</StatusBadge> Results below are partial and may change.
        </p>
      )}
      {(status === "failed" || status === "cancelled") && (
        <p className={styles.banner} data-tone="warning">
          <StatusBadge tone={status === "failed" ? "error" : "warning"}>Run {status}</StatusBadge>
          These are partial results saved before the run stopped.
          {run.error && <> <span className={styles.mono}>{run.error.code}</span>: {run.error.message}</>}
        </p>
      )}
      {status === "succeeded" && (
        <p className={styles.banner} data-tone="neutral">
          <StatusBadge tone="success">Pipeline completed</StatusBadge>
          The analysis ran to completion. That alone does not confirm or refute the hypothesis.
        </p>
      )}
      {simulated && (
        <p className={styles.banner} data-tone="warning"><StatusBadge tone="warning">Simulated data</StatusBadge> Some results come from simulated inputs, not physical observation.</p>
      )}
      {uncalibrated && (
        <p className={styles.banner} data-tone="neutral">No physical calibration: lengths are in pixels. Ratios are dimensionless under the stated assumptions.</p>
      )}
      {warnings.length > 0 && (
        <ul className={styles.warningList} aria-label="Analysis warnings">
          {warnings.map((w, i) => <li key={i}><span className={styles.mono}>{w.code}</span> {w.message}</li>)}
        </ul>
      )}
    </div>
  );
}
