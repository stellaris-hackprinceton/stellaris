import type { Artifact, Capabilities, Experiment } from "@/contracts/api";
import type { CodeRuntime, ID } from "@/contracts/api";
import Link from "next/link";
import { hrefs } from "@/components/shell";
import { formatDuration } from "../format";
import styles from "../studio.module.css";

type Props = {
  project_id: ID;
  experiment: Experiment;
  method: "bouncing_ball_v1" | "python_analysis_v1" | "script_analysis_v1";
  runtime: CodeRuntime;
  inputs: Artifact[];
  code?: Artifact;
  codeId: ID | "";
  parameters?: string;
  start: number;
  end: number | null;
  hint: string;
  caps: Capabilities | undefined;
};

/** Describes the selected method and the exact plan artifacts queued for submission. */
export function AnalysisLaunchSummary({ project_id, experiment: x, method, runtime, inputs, code, codeId, parameters, start, end, hint, caps }: Props) {
  const ex = caps?.execution;
  const isBall = method === "bouncing_ball_v1";
  return (
    <section className={styles.summary} aria-label="Launch summary">
      <h4 className={styles.smallLabel}>This run will use</h4>
      <dl className={styles.dl}>
        <dt>Plan</dt><dd>{x.title} · revision {x.revision}</dd>
        <dt>Method</dt><dd>{isBall ? "Bouncing-ball video tracker" : method === "script_analysis_v1" ? "Saved code analysis" : "Legacy Python analysis"}<details className={styles.muted}><summary>Method ID</summary><code className={styles.mono}>{method}</code></details></dd>
        <dt>{isBall ? "Video" : "Data"}</dt><dd>{inputs.length ? inputs.map((a) => <span key={a.id}>{a.filename}{a.metadata.duration_ms != null && ` (${formatDuration(a.metadata.duration_ms)})`}{a.origin === "simulated" && " · simulated"} </span>) : "—"}</dd>
        {isBall ? <>
          <dt>Interval</dt><dd className="num">{Number.isFinite(start) ? start : "?"} s → {end == null ? "end of video" : `${end} s`}</dd>
          <dt>Tracking label</dt><dd>{hint || "—"}</dd>
          <dt>Tracker scope</dt><dd>Tracks one ball in a fixed camera view. The label does not enable tracking other objects.</dd>
          <dt>Calibration</dt><dd>{x.calibration.mode === "none" ? "None: results in pixels and dimensionless ratios" : `Reference length ${x.calibration.reference_length_m} m`}</dd>
        </> : <>
          <dt>Runtime</dt><dd>{runtime}</dd>
          <dt>Code</dt><dd>{codeId ? <Link href={hrefs.artifact(project_id, codeId)}>{code?.filename ?? `Code artifact ${codeId}`}</Link> : "—"}</dd>
          <dt>Parameters</dt><dd><pre className={styles.mono} tabIndex={0} aria-label="Analysis parameters">{parameters}</pre></dd>
          <dt>Calibration</dt><dd>Available to the script in the manifest; results depend on what the code reports.</dd>
        </>}
        <dt>Limits</dt><dd>{ex ? `${ex.max_wall_time_s} s wall time · ${ex.max_memory_mb} MB · ${ex.max_cpu_cores} CPU · no network` : "Not reported by the server"}</dd>
      </dl>
    </section>
  );
}
