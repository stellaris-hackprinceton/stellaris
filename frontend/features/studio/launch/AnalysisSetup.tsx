"use client";
import Link from "next/link";
import { useId, useRef, useState } from "react";
import type { Artifact, Capabilities, Experiment, ID, Json, Run } from "@/contracts/api";
import type { StartRun } from "@/contracts/requests";
import { useStartRun } from "@/lib/queries";
import { Button, ErrorNotice, StatusBadge, describeError, errorCode, newCommandKey } from "@/components/ui";
import { hrefs } from "@/components/shell";
import { AnalysisLaunchSummary } from "./AnalysisLaunchSummary";
import styles from "../studio.module.css";

type Props = {
  project_id: ID;
  experiment: Experiment;
  inputs: Map<ID, Artifact>;
  hasMoreArtifacts?: boolean;
  loadingArtifacts?: boolean;
  loadMoreArtifacts?: () => void;
  caps: Capabilities | undefined;
  planDirty: boolean;
  planOutOfDate: boolean;
  archived: boolean;
  refetchExperiment: () => void;
  onLaunched: (run: Run) => void;
  onNavigate: (view: "plan" | "inputs") => void;
};

type Method = "" | "bouncing_ball_v1" | "python_analysis_v1";
type BallParams = { video: ID | ""; start: string; end: string; hint: string };
const MAX_PARAMETERS_BYTES = 64 * 1024;

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

export function validateParametersJson(raw: string): { value: Record<string, Json> | null; error: string | null } {
  if (new TextEncoder().encode(raw).length > MAX_PARAMETERS_BYTES) return { value: null, error: "Parameters must be at most 64 KiB of JSON." };
  try {
    const value: unknown = JSON.parse(raw);
    if (value === null || Array.isArray(value) || typeof value !== "object") return { value: null, error: "Parameters must be a JSON object." };
    const finite = (v: unknown): boolean => typeof v === "number" ? Number.isFinite(v) : Array.isArray(v) ? v.every(finite) : v !== null && typeof v === "object" ? Object.values(v).every(finite) : true;
    if (!finite(value)) return { value: null, error: "Parameter numbers must be finite." };
    return { value: value as Record<string, Json>, error: null };
  } catch {
    return { value: null, error: "Enter valid JSON parameters." };
  }
}

/** Launches only the explicitly selected method and immutable saved experiment revision. */
export function AnalysisSetup({ project_id, experiment: x, inputs, hasMoreArtifacts = false, loadingArtifacts = false, loadMoreArtifacts, caps, planDirty, planOutOfDate, archived, refetchExperiment, onLaunched, onNavigate }: Props) {
  const id = useId();
  const startRun = useStartRun(project_id);
  const attached = x.input_artifact_ids.map((a) => inputs.get(a)).filter((a): a is Artifact => a?.project_id === project_id);
  const videos = attached.filter((a) => a.kind === "video");
  const pythonFiles = [...inputs.values()].filter((a) => a.project_id === project_id && a.kind === "code" && a.mime_type === "text/x-python");
  const [method, setMethod] = useState<Method>("");
  const [ball, setBall] = useState<BallParams>({ video: "", start: "0", end: "", hint: "" });
  const [codeId, setCodeId] = useState<ID | "">("");
  const [selectedInputs, setSelectedInputs] = useState<ID[]>([]);
  const [parametersText, setParametersText] = useState("{}");
  const [accepted, setAccepted] = useState<Run | null>(null);
  const [revisionConflict, setRevisionConflict] = useState(false);
  const [unresolved, setUnresolved] = useState(false);
  const key = useRef<{ key: string; body: StartRun } | null>(null);

  const video = videos.find((v) => v.id === ball.video) ?? (method === "bouncing_ball_v1" && videos.length === 1 ? videos[0] : undefined);
  const code = pythonFiles.find((a) => a.id === codeId);
  const start = ball.start.trim() === "" ? 0 : Number(ball.start);
  const end = ball.end.trim() === "" ? null : Number(ball.end);
  const hint = ball.hint.trim();
  const intervalError = method === "bouncing_ball_v1" ? validateInterval(start, end, video?.metadata.duration_ms) : null;
  const parsedParameters = method === "python_analysis_v1" ? validateParametersJson(parametersText) : { value: null, error: null };
  const chosenInputs = selectedInputs.map((aid) => inputs.get(aid)).filter((a): a is Artifact => !!a && a.project_id === project_id && x.input_artifact_ids.includes(a.id));
  const pythonInputs = chosenInputs.filter((a) => a.id !== code?.id);

  const blocker =
    !method ? "Choose an analysis method to configure this run."
    : method === "bouncing_ball_v1" && !caps?.features.video_analysis ? "Video analysis is not enabled on this server."
    : method === "python_analysis_v1" && !caps?.execution.allowed_backends.includes("isolated_python") ? "Isolated Python analysis is not enabled on this server."
    : archived ? "This project is archived."
    : planDirty ? "Save the plan first. Analysis always uses a saved revision."
    : planOutOfDate ? "A newer revision was saved elsewhere. Review it above before launching."
    : method === "bouncing_ball_v1" && videos.length === 0 ? "Attach a video to the saved plan first."
    : method === "bouncing_ball_v1" && !video ? "Choose the video to analyse."
    : method === "bouncing_ball_v1" && intervalError ? intervalError
    : method === "bouncing_ball_v1" && (hint.length < 1 || hint.length > 100) ? "Add a tracking label (1–100 characters)."
    : method === "python_analysis_v1" && !code ? "Choose a Python script from this project."
    : method === "python_analysis_v1" && pythonInputs.length === 0 ? "Choose at least one input file attached to the saved plan."
    : method === "python_analysis_v1" && parsedParameters.error ? parsedParameters.error
    : null;

  function makeBody(): StartRun | null {
    if (method === "bouncing_ball_v1" && video) return {
      kind: "analysis", experiment_id: x.id, experiment_revision: x.revision,
      input_artifact_ids: [video.id], pipeline: "bouncing_ball_v1", code_artifact_id: null,
      parameters: { start_time_s: start, end_time_s: end, object_hint: hint },
    };
    if (method === "python_analysis_v1" && code && parsedParameters.value) return {
      kind: "analysis", experiment_id: x.id, experiment_revision: x.revision,
      input_artifact_ids: pythonInputs.map((a) => a.id), pipeline: "python_analysis_v1", code_artifact_id: code.id,
      parameters: parsedParameters.value,
    };
    return null;
  }

  async function launch(isRetry: boolean) {
    const pending = isRetry ? key.current : null;
    const body = pending?.body ?? makeBody();
    if ((!isRetry && blocker) || !body) return;
    if (!isRetry) key.current = { key: newCommandKey(), body };
    const exact = key.current;
    if (!exact) return;
    setRevisionConflict(false);
    try {
      const res = await startRun.mutateAsync({ body: exact.body, idempotency_key: exact.key });
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
        const status = err && typeof err === "object" ? (err as { status?: unknown }).status : undefined;
        if (typeof status === "number" && status >= 400 && status < 500 && status !== 429) {
          // A definitive client rejection was not accepted. Allow correction and a new deliberate command.
          key.current = null;
          setUnresolved(false);
        } else setUnresolved(true);
      }
    }
  }

  const disabled = unresolved || startRun.isPending;
  const err = startRun.error;
  const codeError = errorCode(err);
  return (
    <div className={styles.stack}>
      <div className={styles.varField}>
        <label htmlFor={`${id}-method`} className={styles.smallLabel}>Analysis method</label>
        <select id={`${id}-method`} className={styles.input} value={method} disabled={disabled} onChange={(e) => setMethod(e.target.value as Method)}>
          <option value="">Choose a method</option>
          <option value="bouncing_ball_v1">Bouncing-ball video tracker</option>
          <option value="python_analysis_v1">Run Python analysis</option>
        </select>
      </div>

      {method === "bouncing_ball_v1" && <>
        {videos.length > 0 && <div className={styles.varField}>
          <label htmlFor={`${id}-v`} className={styles.smallLabel}>Video</label>
          <select id={`${id}-v`} className={styles.input} value={video?.id ?? ""} disabled={disabled} onChange={(e) => setBall({ ...ball, video: e.target.value })}>
            <option value="" disabled>Choose a video</option>{videos.map((v) => <option key={v.id} value={v.id}>{v.filename}</option>)}
          </select>
        </div>}
        <div className={styles.grid3}>
          <div className={styles.varField}><label htmlFor={`${id}-s`} className={styles.smallLabel}>Start (s)</label><input id={`${id}-s`} type="number" min={0} step="0.01" className={`${styles.input} ${styles.mono}`} value={ball.start} disabled={disabled} onChange={(e) => setBall({ ...ball, start: e.target.value })} /></div>
          <div className={styles.varField}><label htmlFor={`${id}-e`} className={styles.smallLabel}>End (s)</label><input id={`${id}-e`} type="number" min={0} step="0.01" className={`${styles.input} ${styles.mono}`} value={ball.end} placeholder="end of video" disabled={disabled} onChange={(e) => setBall({ ...ball, end: e.target.value })} /></div>
          <div className={styles.varField}><label htmlFor={`${id}-h`} className={styles.smallLabel}>Tracking label</label><input id={`${id}-h`} aria-describedby={`${id}-hint-help`} className={styles.input} value={ball.hint} disabled={disabled} onChange={(e) => setBall({ ...ball, hint: e.target.value })} /><span id={`${id}-hint-help`} className={styles.muted}>The tracker follows one ball in a fixed camera view. This label does not enable tracking other objects.</span></div>
        </div>
        {intervalError && video && <p className={styles.fieldError} role="alert">{intervalError}</p>}
      </>}

      {method === "python_analysis_v1" && <>
        <div className={styles.varField}>
          <label htmlFor={`${id}-code`} className={styles.smallLabel}>Python script</label>
          <select id={`${id}-code`} className={styles.input} value={codeId} disabled={disabled} onChange={(e) => setCodeId(e.target.value)}>
            <option value="">Choose a Python script</option>{pythonFiles.map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}
          </select>
        </div>
        <fieldset className={styles.fieldset} disabled={disabled}>
          <legend className={styles.smallLabel}>Input files</legend>
          {attached.filter((a) => a.id !== code?.id).map((a) => <label key={a.id} className={styles.radio}><input type="checkbox" checked={selectedInputs.includes(a.id)} onChange={(e) => setSelectedInputs((old) => e.target.checked ? [...old, a.id] : old.filter((value) => value !== a.id))} /><span>{a.filename} <span className={styles.muted}>({a.kind})</span></span></label>)}
          {attached.length === 0 && <p className={styles.muted}>No saved-plan inputs are loaded yet.</p>}
          {hasMoreArtifacts && <div className={styles.row}><Button disabled={loadingArtifacts || disabled} pending={loadingArtifacts} onClick={loadMoreArtifacts}>Load more files</Button><span className={styles.muted}>Only loaded project files appear here; run inputs must also be attached to the saved plan.</span></div>}
        </fieldset>
        <div className={styles.varField}>
          <label htmlFor={`${id}-params`} className={styles.smallLabel}>Parameters (JSON object)</label>
          <textarea id={`${id}-params`} className={styles.input} rows={5} value={parametersText} disabled={disabled} onChange={(e) => setParametersText(e.target.value)} />
          <span className={styles.muted}>Passed to your script in the immutable input manifest (up to 64 KiB). The script must write the documented result.json output. <Link href="/docs/frontend-backend-contract.md">Worker input and output contract</Link></span>
          {parsedParameters.error && <span role="alert" className={styles.fieldError}>{parsedParameters.error}</span>}
        </div>
      </>}

      {method && <AnalysisLaunchSummary experiment={x} method={method} inputs={method === "bouncing_ball_v1" ? (video ? [video] : []) : pythonInputs} code={method === "python_analysis_v1" ? code : undefined} parameters={method === "python_analysis_v1" ? parametersText : undefined} start={start} end={end} hint={hint} caps={caps} />}

      {revisionConflict && <p className={styles.note} role="alert">The plan changed after you prepared this run. The latest saved plan is now loaded above; review it and launch again.</p>}
      {err != null && codeError !== "EXPERIMENT_REVISION_CONFLICT" && <ErrorNotice {...describeError(err, "Analysis not started")} action={<div className={styles.row}>
        {unresolved && <Button onClick={() => void launch(true)} pending={startRun.isPending}>Retry submission</Button>}
        <Button disabled={startRun.isPending} onClick={() => { key.current = null; setUnresolved(false); startRun.reset(); }}>Dismiss</Button>
      </div>} />}
      {blocker && <div className={styles.muted}><p>{blocker}</p>
        {planDirty || planOutOfDate ? <Button onClick={() => onNavigate("plan")}>Review plan</Button>
          : method === "bouncing_ball_v1" && videos.length === 0 || method === "python_analysis_v1" && (!code || pythonInputs.length === 0) ? <Button onClick={() => onNavigate("inputs")}>Add data</Button> : null}
      </div>}
      <div className={styles.row}>
        <Button variant="primary" disabled={Boolean(blocker) || unresolved} pending={startRun.isPending} onClick={() => void launch(false)}>Start analysis</Button>
        {accepted && <span className={styles.row} role="status"><StatusBadge tone="info">Accepted · {accepted.status}</StatusBadge><Link href={hrefs.run(project_id, accepted.id)}>Follow this run</Link></span>}
      </div>
    </div>
  );
}
