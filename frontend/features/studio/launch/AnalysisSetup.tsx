"use client";
import Link from "next/link";
import { useId, useRef, useState } from "react";
import type { Artifact, Capabilities, Experiment, ID, Run } from "@/contracts/api";
import { useStartRun } from "@/lib/queries";
import { Button, ErrorNotice, StatusBadge, describeError, errorCode, newCommandKey } from "@/components/ui";
import { hrefs } from "@/components/shell";
import { AnalysisLaunchSummary } from "./AnalysisLaunchSummary";
import styles from "../studio.module.css";

type Props = {
  project_id: ID;
  /** The saved experiment (server state), never the local draft. */
  experiment: Experiment;
  inputs: Map<ID, Artifact>;
  caps: Capabilities | undefined;
  planDirty: boolean;
  planOutOfDate: boolean;
  archived: boolean;
  refetchExperiment: () => void;
  onLaunched: (run: Run) => void;
};

type Params = { video: ID | ""; start: string; end: string; hint: string };

export function validateInterval(start: number, end: number | null, durationMs: number | undefined): string | null {
  if (!Number.isFinite(start) || start < 0) return "Start must be 0 s or later.";
  if (end != null && (!Number.isFinite(end) || end <= start)) return "End must be after start.";
  if (durationMs != null) {
    const dur = durationMs / 1000;
    if (start >= dur) return `Start must be before the end of the video (${dur.toFixed(2)} s).`;
    if (end != null && end > dur) return `End must be within the video (${dur.toFixed(2)} s).`;
  }
  return null;
}

/**
 * Launch the default bouncing-ball analysis. The request is built from the confirmed saved revision:
 * if the plan has unsaved edits or a newer revision exists, launching is blocked until resolved.
 * A deliberate launch gets a new idempotency key; "Retry submission" after an ambiguous failure reuses it.
 */
export function AnalysisSetup({ project_id, experiment: x, inputs, caps, planDirty, planOutOfDate, archived, refetchExperiment, onLaunched }: Props) {
  const id = useId();
  const startRun = useStartRun(project_id);
  const videos = x.input_artifact_ids.map((a) => inputs.get(a)).filter((a): a is Artifact => a?.kind === "video");
  const [p, setP] = useState<Params>({ video: "", start: "0", end: "", hint: "ball" });
  const [accepted, setAccepted] = useState<Run | null>(null);
  const [revisionConflict, setRevisionConflict] = useState(false);
  // An earlier submission whose outcome is unknown: only "Retry submission" (same key) or "Dismiss" may follow.
  const [unresolved, setUnresolved] = useState(false);
  const key = useRef<{ key: string; body: string } | null>(null);

  const video = videos.find((v) => v.id === p.video) ?? (videos.length === 1 ? videos[0] : undefined);
  const start = p.start.trim() === "" ? 0 : Number(p.start);
  const end = p.end.trim() === "" ? null : Number(p.end);
  const intervalError = validateInterval(start, end, video?.metadata.duration_ms);
  const hint = p.hint.trim() || "ball";

  const blocker =
    !caps?.features.video_analysis ? "Video analysis is not enabled on this server."
    : archived ? "This project is archived."
    : planDirty ? "Save the plan first. Analysis always uses a saved revision."
    : planOutOfDate ? "A newer revision was saved elsewhere. Review it above before launching."
    : videos.length === 0 ? "Attach a video to the saved plan first."
    : !video ? "Choose the video to analyse."
    : intervalError;

  async function launch(isRetry: boolean) {
    if (blocker || !video) return;
    const body = {
      kind: "analysis" as const,
      experiment_id: x.id,
      experiment_revision: x.revision,
      input_artifact_ids: [video.id],
      pipeline: "bouncing_ball_v1" as const,
      code_artifact_id: null,
      parameters: { start_time_s: start, end_time_s: end, object_hint: hint },
    };
    const serialized = JSON.stringify(body);
    if (!isRetry || !key.current || key.current.body !== serialized) key.current = { key: newCommandKey(), body: serialized };
    setRevisionConflict(false);
    try {
      const res = await startRun.mutateAsync({ body, idempotency_key: key.current.key });
      key.current = null;
      setUnresolved(false);
      setAccepted(res.data);
      onLaunched(res.data);
    } catch (err) {
      if (errorCode(err) === "EXPERIMENT_REVISION_CONFLICT") {
        key.current = null;
        setRevisionConflict(true);
        setUnresolved(false);
        refetchExperiment();
      } else {
        setUnresolved(true);
      }
    }
  }

  const err = startRun.error;
  const code = errorCode(err);
  return (
    <div className={styles.stack}>
      {videos.length > 1 && (
        <div className={styles.varField}>
          <label htmlFor={`${id}-v`} className={styles.smallLabel}>Video</label>
          <select id={`${id}-v`} className={styles.input} value={video?.id ?? ""} onChange={(e) => setP({ ...p, video: e.target.value })}>
            <option value="" disabled>Choose a video</option>
            {videos.map((v) => <option key={v.id} value={v.id}>{v.filename}</option>)}
          </select>
        </div>
      )}
      <div className={styles.grid3}>
        <div className={styles.varField}>
          <label htmlFor={`${id}-s`} className={styles.smallLabel}>Start (s)</label>
          <input id={`${id}-s`} type="number" min={0} step="0.01" className={`${styles.input} ${styles.mono}`} value={p.start}
            onChange={(e) => setP({ ...p, start: e.target.value })} />
        </div>
        <div className={styles.varField}>
          <label htmlFor={`${id}-e`} className={styles.smallLabel}>End (s)</label>
          <input id={`${id}-e`} type="number" min={0} step="0.01" className={`${styles.input} ${styles.mono}`} value={p.end}
            placeholder="end of video" onChange={(e) => setP({ ...p, end: e.target.value })} />
        </div>
        <div className={styles.varField}>
          <label htmlFor={`${id}-h`} className={styles.smallLabel}>Object to track</label>
          <input id={`${id}-h`} className={styles.input} value={p.hint} onChange={(e) => setP({ ...p, hint: e.target.value })} />
        </div>
      </div>
      {intervalError && video && <p className={styles.fieldError} role="alert">{intervalError}</p>}

      <AnalysisLaunchSummary experiment={x} video={video} start={start} end={end} hint={hint} caps={caps} />

      {revisionConflict && (
        <p className={styles.note} role="alert">
          The plan changed after you prepared this run. The latest saved plan is now loaded above; review it and launch again.
        </p>
      )}
      {err != null && code !== "EXPERIMENT_REVISION_CONFLICT" && (
        <ErrorNotice {...describeError(err, "Analysis not started")}
          action={
            <div className={styles.row}>
              {code !== "PROJECT_ARCHIVED" && code !== "FEATURE_UNAVAILABLE" && code !== "VALIDATION_FAILED" && (
                <Button onClick={() => void launch(true)} pending={startRun.isPending}>Retry submission</Button>
              )}
              <Button onClick={() => { key.current = null; setUnresolved(false); startRun.reset(); }}>Dismiss</Button>
            </div>
          } />
      )}
      {blocker && <p className={styles.muted}>{blocker}</p>}
      <div className={styles.row}>
        <Button variant="primary" disabled={Boolean(blocker) || unresolved} pending={startRun.isPending} onClick={() => void launch(false)}>
          Start analysis
        </Button>
        {accepted && (
          <span className={styles.row} role="status">
            <StatusBadge tone="info">Accepted · {accepted.status}</StatusBadge>
            <Link href={hrefs.run(project_id, accepted.id)}>Follow this run</Link>
          </span>
        )}
      </div>
    </div>
  );
}
