"use client";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import type { Artifact, Capabilities, CodeRuntime, Experiment, ID, Json, Run } from "@/contracts/api";
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

type Method = "" | "bouncing_ball_v1" | "python_analysis_v1" | "script_analysis_v1";
type BallParams = { video: ID | ""; start: string; end: string; hint: string };
const NO_RUNTIMES: NonNullable<Capabilities["execution"]["runtimes"]> = [];
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
  const codeFiles = [...inputs.values()].filter((a) => a.project_id === project_id && a.kind === "code");
  const availableRuntimes = caps?.execution.runtimes ?? NO_RUNTIMES;
  const savedImplementation = x.implementation ?? null;
  const [method, setMethod] = useState<Method>(savedImplementation ? "script_analysis_v1" : "");
  const [ball, setBall] = useState<BallParams>({ video: "", start: "0", end: "", hint: "" });
  const [codeId, setCodeId] = useState<ID | "">(savedImplementation?.code_artifact_id ?? "");
  const [runtimeOverride, setRuntime] = useState<CodeRuntime | null>(savedImplementation?.runtime ?? null);
  const runtime = runtimeOverride ?? availableRuntimes[0]?.id ?? "python";
  const [selectedInputs, setSelectedInputs] = useState<ID[]>(() => [...x.input_artifact_ids]);
  const selectedInputsChanged = useRef(false);
  const [parametersText, setParametersText] = useState("{}");
  const [accepted, setAccepted] = useState<Run | null>(null);
  const [revisionConflict, setRevisionConflict] = useState(false);
  const [unresolved, setUnresolved] = useState(false);
  const key = useRef<{ key: string; body: StartRun } | null>(null);

  const video = videos.find((v) => v.id === ball.video) ?? (method === "bouncing_ball_v1" && videos.length === 1 ? videos[0] : undefined);
  const runtimeMimeTypes: Record<CodeRuntime, string[]> = {
    python: ["text/x-python", "text/plain"],
    javascript: ["text/javascript", "application/javascript", "text/plain"],
    shell: ["text/x-shellscript", "text/plain"],
  };
  const genericCodeFiles = codeFiles.filter((a) => runtimeMimeTypes[runtime].includes(a.mime_type));
  const code = method === "python_analysis_v1"
    ? codeFiles.find((a) => a.id === codeId && a.mime_type === "text/x-python")
    : genericCodeFiles.find((a) => a.id === codeId);
  const savedCodeMissing = Boolean(codeId && !code && codeId === savedImplementation?.code_artifact_id);
  const start = ball.start.trim() === "" ? 0 : Number(ball.start);
  const end = ball.end.trim() === "" ? null : Number(ball.end);
  const hint = ball.hint.trim();
  const intervalError = method === "bouncing_ball_v1" ? validateInterval(start, end, video?.metadata.duration_ms) : null;
  const parsedParameters = method === "python_analysis_v1" || method === "script_analysis_v1" ? validateParametersJson(parametersText) : { value: null, error: null };
  const chosenInputs = selectedInputs.map((aid) => inputs.get(aid)).filter((a): a is Artifact => !!a && a.project_id === project_id && a.kind !== "code" && x.input_artifact_ids.includes(a.id));
  const analysisInputs = chosenInputs.filter((a) => a.id !== codeId);
  const genericEnabled = caps?.execution.allowed_backends.includes("isolated_python") && availableRuntimes.length > 0;

  useEffect(() => {
    if (!selectedInputsChanged.current) setSelectedInputs([...x.input_artifact_ids]);
  }, [x.input_artifact_ids]);

  const blocker =
    !method ? "Choose an analysis method to configure this run."
    : method === "bouncing_ball_v1" && !caps?.features.video_analysis ? "Video analysis is not enabled on this server."
    : (method === "python_analysis_v1" || method === "script_analysis_v1") && !caps?.execution.allowed_backends.includes("isolated_python") ? "Isolated worker analysis is not enabled on this server."
    : method === "script_analysis_v1" && !availableRuntimes.some((item) => item.id === runtime) ? "This runtime is not available on the configured worker."
    : archived ? "This project is archived."
    : planDirty ? "Save the plan first. Analysis always uses a saved revision."
    : planOutOfDate ? "A newer revision was saved elsewhere. Review it above before launching."
    : method === "bouncing_ball_v1" && videos.length === 0 ? "Attach a video to the saved plan first."
    : method === "bouncing_ball_v1" && !video ? "Choose the video to analyse."
    : method === "bouncing_ball_v1" && intervalError ? intervalError
    : method === "bouncing_ball_v1" && (hint.length < 1 || hint.length > 100) ? "Add a tracking label (1–100 characters)."
    : method === "python_analysis_v1" && !code ? "Choose a Python script from this project."
    : method === "python_analysis_v1" && analysisInputs.length === 0 ? "Choose at least one input file attached to the saved plan."
    : method === "script_analysis_v1" && !codeId ? "Choose a compatible code artifact from this project."
    : (method === "python_analysis_v1" || method === "script_analysis_v1") && parsedParameters.error ? parsedParameters.error
    : null;

  function makeBody(): StartRun | null {
    if (method === "bouncing_ball_v1" && video) return {
      kind: "analysis", experiment_id: x.id, experiment_revision: x.revision,
      input_artifact_ids: [video.id], pipeline: "bouncing_ball_v1", code_artifact_id: null,
      parameters: { start_time_s: start, end_time_s: end, object_hint: hint },
    };
    if (method === "python_analysis_v1" && code && parsedParameters.value) return {
      kind: "analysis", experiment_id: x.id, experiment_revision: x.revision,
      input_artifact_ids: analysisInputs.map((a) => a.id), pipeline: "python_analysis_v1", code_artifact_id: code.id,
      parameters: parsedParameters.value,
    };
    if (method === "script_analysis_v1" && codeId && parsedParameters.value) return {
      kind: "analysis", experiment_id: x.id, experiment_revision: x.revision,
      input_artifact_ids: analysisInputs.map((a) => a.id), pipeline: "script_analysis_v1", runtime,
      code_artifact_id: codeId, parameters: parsedParameters.value,
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
        <select id={`${id}-method`} className={styles.input} value={method} disabled={disabled} onChange={(e) => {
          const next = e.target.value as Method;
          setMethod(next);
          if (next === "python_analysis_v1" && codeFiles.find((a) => a.id === codeId)?.mime_type !== "text/x-python") setCodeId("");
          if (next === "script_analysis_v1" && codeId && !runtimeMimeTypes[runtime].includes(codeFiles.find((a) => a.id === codeId)?.mime_type ?? "") && codeId !== savedImplementation?.code_artifact_id) setCodeId("");
        }}>
          <option value="">Choose a method</option>
          <option value="bouncing_ball_v1">Bouncing-ball video tracker</option>
          <option value="script_analysis_v1" disabled={!genericEnabled}>Run saved or custom code</option>
          <option value="python_analysis_v1">Legacy Python analysis</option>
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

      {method === "script_analysis_v1" && <>
        <div className={styles.varField}>
          <label htmlFor={`${id}-runtime`} className={styles.smallLabel}>Runtime</label>
          <select id={`${id}-runtime`} className={styles.input} value={runtime} disabled={disabled} onChange={(e) => {
            const next = e.target.value as CodeRuntime;
            setRuntime(next);
            if (!runtimeMimeTypes[next].includes(codeFiles.find((a) => a.id === codeId)?.mime_type ?? "")) setCodeId("");
          }}>
            {availableRuntimes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            {availableRuntimes.length === 0 && <option value={runtime}>No runtimes available</option>}
          </select>
        </div>
        <div className={styles.varField}>
          <label htmlFor={`${id}-script`} className={styles.smallLabel}>Code artifact</label>
          <select id={`${id}-script`} className={styles.input} value={codeId} disabled={disabled} onChange={(e) => setCodeId(e.target.value)}>
            <option value="">Choose compatible code</option>
            {savedCodeMissing && <option value={codeId}>Saved implementation · {codeId}</option>}
            {genericCodeFiles.map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}
          </select>
          {codeId && <Link href={hrefs.artifact(project_id, codeId)}>Inspect code artifact</Link>}
          {hasMoreArtifacts && <div className={styles.row}><Button disabled={loadingArtifacts || disabled} pending={loadingArtifacts} onClick={loadMoreArtifacts}>Load more files</Button><span className={styles.muted}>Only loaded project code appears here.</span></div>}
        </div>
        <fieldset className={styles.fieldset} disabled={disabled}>
          <legend className={styles.smallLabel}>Input files <span className={styles.muted}>(optional)</span></legend>
          {attached.filter((a) => a.kind !== "code").map((a) => <label key={a.id} className={styles.radio}><input type="checkbox" checked={selectedInputs.includes(a.id)} onChange={(e) => {
            selectedInputsChanged.current = true;
            setSelectedInputs((old) => e.target.checked ? [...old, a.id] : old.filter((value) => value !== a.id));
          }} /><span>{a.filename} <span className={styles.muted}>({a.kind})</span></span></label>)}
          {attached.every((a) => a.kind === "code") && <p className={styles.muted}>This implementation can run without input files.</p>}
          {hasMoreArtifacts && <div className={styles.row}><Button disabled={loadingArtifacts || disabled} pending={loadingArtifacts} onClick={loadMoreArtifacts}>Load more files</Button><span className={styles.muted}>Run inputs must be attached to the saved plan.</span></div>}
        </fieldset>
        <div className={styles.varField}>
          <label htmlFor={`${id}-params`} className={styles.smallLabel}>Parameters (JSON object)</label>
          <textarea id={`${id}-params`} className={styles.input} rows={5} value={parametersText} disabled={disabled} onChange={(e) => setParametersText(e.target.value)} />
          <span className={styles.muted}>Passed to the selected runtime in the immutable input manifest (up to 64 KiB). The script must write the documented result.json output. <Link href="/docs/frontend-backend-contract.md">Worker input and output contract</Link></span>
          {parsedParameters.error && <span role="alert" className={styles.fieldError}>{parsedParameters.error}</span>}
        </div>
      </>}

      {method === "python_analysis_v1" && <>
        <div className={styles.varField}>
          <label htmlFor={`${id}-code`} className={styles.smallLabel}>Python script</label>
          <select id={`${id}-code`} className={styles.input} value={codeId} disabled={disabled} onChange={(e) => setCodeId(e.target.value)}>
            <option value="">Choose a Python script</option>{codeFiles.filter((a) => a.mime_type === "text/x-python").map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}
          </select>
          {codeId && <Link href={hrefs.artifact(project_id, codeId)}>Inspect code artifact</Link>}
        </div>
        <fieldset className={styles.fieldset} disabled={disabled}>
          <legend className={styles.smallLabel}>Input files</legend>
          {attached.filter((a) => a.kind !== "code").map((a) => <label key={a.id} className={styles.radio}><input type="checkbox" checked={selectedInputs.includes(a.id)} onChange={(e) => { selectedInputsChanged.current = true; setSelectedInputs((old) => e.target.checked ? [...old, a.id] : old.filter((value) => value !== a.id)); }} /><span>{a.filename} <span className={styles.muted}>({a.kind})</span></span></label>)}
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

      {method && <AnalysisLaunchSummary project_id={project_id} experiment={x} method={method} runtime={method === "script_analysis_v1" ? runtime : "python"} inputs={method === "bouncing_ball_v1" ? (video ? [video] : []) : analysisInputs} code={method === "script_analysis_v1" || method === "python_analysis_v1" ? code : undefined} codeId={codeId} parameters={method === "python_analysis_v1" || method === "script_analysis_v1" ? parametersText : undefined} start={start} end={end} hint={hint} caps={caps} />}

      {revisionConflict && <p className={styles.note} role="alert">The plan changed after you prepared this run. The latest saved plan is now loaded above; review it and launch again.</p>}
      {err != null && codeError !== "EXPERIMENT_REVISION_CONFLICT" && <ErrorNotice {...describeError(err, "Analysis not started")} action={<div className={styles.row}>
        {unresolved && <Button onClick={() => void launch(true)} pending={startRun.isPending}>Retry submission</Button>}
        <Button disabled={startRun.isPending} onClick={() => { key.current = null; setUnresolved(false); startRun.reset(); }}>Dismiss</Button>
      </div>} />}
      {blocker && <div className={styles.muted}><p>{blocker}</p>
        {planDirty || planOutOfDate ? <Button onClick={() => onNavigate("plan")}>Review plan</Button>
          : method === "bouncing_ball_v1" && videos.length === 0 || method === "python_analysis_v1" && (!code || analysisInputs.length === 0) ? <Button onClick={() => onNavigate("inputs")}>Add data</Button> : null}
      </div>}
      <div className={styles.row}>
        <Button variant="primary" disabled={Boolean(blocker) || unresolved} pending={startRun.isPending} onClick={() => void launch(false)}>Start analysis</Button>
        {accepted && <span className={styles.row} role="status"><StatusBadge tone="info">Accepted · {accepted.status}</StatusBadge><Link href={hrefs.run(project_id, accepted.id)}>Follow this run</Link></span>}
      </div>
    </div>
  );
}
