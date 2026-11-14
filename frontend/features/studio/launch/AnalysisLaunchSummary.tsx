import type { Artifact, Capabilities, Experiment } from "@/contracts/api";
import { formatDuration } from "../format";
import styles from "../studio.module.css";

type Props = {
  experiment: Experiment;
  method: "bouncing_ball_v1" | "python_analysis_v1";
  inputs: Artifact[];
  code?: Artifact;
  parameters?: string;
  start: number;
  end: number | null;
  hint: string;
  caps: Capabilities | undefined;
};

/** Describes the selected method and the exact plan artifacts queued for submission. */
export function AnalysisLaunchSummary({ experiment: x, method, inputs, code, parameters, start, end, hint, caps }: Props) {
  const ex = caps?.execution;
  const isBall = method === "bouncing_ball_v1";
  return (
    <section className={styles.summary} aria-label="Launch summary">
      <h4 className={styles.smallLabel}>This run will use</h4>
      <dl className={styles.dl}>
        <dt>Plan</dt><dd>{x.title} · revision {x.revision}</dd>
        <dt>Method</dt><dd className={styles.mono}>{method}</dd>
        <dt>{isBall ? "Video" : "Inputs"}</dt><dd>{inputs.length ? inputs.map((a) => <span key={a.id}>{a.filename}{a.metadata.duration_ms != null && ` (${formatDuration(a.metadata.duration_ms)})`}{a.origin === "simulated" && " · simulated"} </span>) : "—"}</dd>
        {isBall ? <>
          <dt>Interval</dt><dd className="num">{Number.isFinite(start) ? start : "?"} s → {end == null ? "end of video" : `${end} s`}</dd>
          <dt>Object hint</dt><dd>{hint || "—"}</dd>
          <dt>Tracker scope</dt><dd>Single-ball tracker; the hint does not enable arbitrary object tracking.</dd>
          <dt>Calibration</dt><dd>{x.calibration.mode === "none" ? "None: results in pixels and dimensionless ratios" : `Reference length ${x.calibration.reference_length_m} m`}</dd>
        </> : <>
          <dt>Code</dt><dd>{code?.filename ?? "—"}</dd>
          <dt>Parameters</dt><dd><pre className={styles.mono} tabIndex={0} aria-label="Python analysis parameters">{parameters}</pre></dd>
          <dt>Calibration</dt><dd>Available to the script in the manifest; results depend on what the code reports.</dd>
        </>}
        <dt>Limits</dt><dd>{ex ? `${ex.max_wall_time_s} s wall time · ${ex.max_memory_mb} MB · ${ex.max_cpu_cores} CPU · no network` : "Not reported by the server"}</dd>
      </dl>
    </section>
  );
}
