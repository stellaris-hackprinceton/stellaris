import type { Artifact, Capabilities, Experiment } from "@/contracts/api";
import { formatDuration } from "../format";
import styles from "../studio.module.css";

type Props = {
  experiment: Experiment;
  video: Artifact | undefined;
  start: number;
  end: number | null;
  hint: string;
  caps: Capabilities | undefined;
};

/** Exactly what will be submitted, from saved state. */
export function AnalysisLaunchSummary({ experiment: x, video, start, end, hint, caps }: Props) {
  const c = x.calibration;
  const ex = caps?.execution;
  return (
    <section className={styles.summary} aria-label="Launch summary">
      <h4 className={styles.smallLabel}>This run will use</h4>
      <dl className={styles.dl}>
        <dt>Plan</dt><dd>{x.title} · revision {x.revision}</dd>
        <dt>Input</dt>
        <dd>{video ? <>{video.filename}{video.metadata.duration_ms != null && ` (${formatDuration(video.metadata.duration_ms)})`}{video.origin === "simulated" && " · simulated"}</> : "—"}</dd>
        <dt>Interval</dt><dd className="num">{Number.isFinite(start) ? start : "?"} s → {end == null ? "end of video" : `${end} s`}</dd>
        <dt>Object</dt><dd>{hint}</dd>
        <dt>Pipeline</dt><dd className={styles.mono}>bouncing_ball_v1</dd>
        <dt>Calibration</dt>
        <dd>{c.mode === "none" ? "None: results in pixels and dimensionless ratios" : `Reference length ${c.reference_length_m} m`}</dd>
        <dt>Limits</dt>
        <dd>{ex ? `${ex.max_wall_time_s} s wall time · ${ex.max_memory_mb} MB · ${ex.max_cpu_cores} CPU · no network` : "Not reported by the server"}</dd>
      </dl>
    </section>
  );
}
