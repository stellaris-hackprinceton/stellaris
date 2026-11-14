"use client";
import { useEffect, useMemo, useState } from "react";
import type { Artifact, ID, Run } from "@/contracts/api";
import {
  useArtifacts, useCapabilities, useEditExperiment, useExperiment, useExperiments, useProject, useRuns,
} from "@/lib/queries";
import {
  Button, EmptyState, ErrorNotice, Skeleton, StatusBadge, Tabs, TimestampLabel, describeError, errorCode,
} from "@/components/ui";
import { ResultsPane } from "@/features/results";
import { CapturePanel } from "./capture/CapturePanel";
import type { Recording } from "./capture/useCamera";
import { ExperimentSelector } from "./ExperimentSelector";
import { AnalysisSetup } from "./launch/AnalysisSetup";
import { ExperimentEditor } from "./plan/ExperimentEditor";
import { ExperimentImplementation } from "./plan/ExperimentImplementation";
import { usePlanDraft } from "./plan/usePlanDraft";
import { FileImport } from "./upload/FileImport";
import { mimeForFile } from "./upload/fileTypes";
import { UploadProgressView } from "./upload/UploadProgressView";
import { useArtifactUpload } from "./upload/useArtifactUpload";
import { useStudioParams, STUDIO_VIEWS } from "./useStudioParams";
import styles from "./studio.module.css";

/**
 * Experiment Studio. Uses useSearchParams, so the route must render it inside <Suspense> (Agent C).
 * Keyed by project in the route so capture and uploads are released when the project changes.
 */
export function StudioScreen({ project_id }: { project_id: ID }) {
  const { experiment: expParam, run: runParam, view, update } = useStudioParams();
  const project = useProject(project_id);
  const caps = useCapabilities();
  const list = useExperiments(project_id);
  const selectedId = expParam ?? list.items[0]?.id ?? null;
  const exp = useExperiment(project_id, selectedId);
  const archived = project.data?.status === "archived";

  if (list.error != null && list.items.length === 0) {
    return <ErrorNotice {...describeError(list.error, "Experiments could not be loaded")} action={<Button onClick={list.refetch}>Try again</Button>} />;
  }
  if (list.is_loading) return <Skeleton height="20rem" />;

  return (
    <div className={styles.screen}>
      <h2 className="sr-only">Experiment Studio</h2>
      {list.items.length === 0 && !expParam ? (
        <>
          <ExperimentSelector project_id={project_id} experiments={[]} selected={null} onSelect={(id) => update({ experiment: id, run: null })}
            hasMore={false} loadMore={() => {}} dirty={false} archived={archived} />
          <EmptyState title="No experiment plans yet">Create one here, or ask Research Chat to design an experiment for your question.</EmptyState>
        </>
      ) : exp.error != null && !exp.data ? (
        <EmptyState title="Experiment unavailable" action={<Button onClick={() => update({ experiment: null, run: null })}>Show the first experiment</Button>}>
          This experiment does not exist in this project or could not be loaded.
        </EmptyState>
      ) : !exp.data ? (
        <Skeleton height="20rem" />
      ) : (
        // Re-key per experiment so local drafts, capture and uploads never leak between plans.
        <StudioBody key={exp.data.id} project_id={project_id} experimentQuery={exp} archived={archived}
          caps={caps.data} list={list} runParam={runParam} view={view} update={update} />
      )}
    </div>
  );
}

type BodyProps = {
  project_id: ID;
  experimentQuery: ReturnType<typeof useExperiment>;
  archived: boolean;
  caps: ReturnType<typeof useCapabilities>["data"];
  list: ReturnType<typeof useExperiments>;
  runParam: string | null;
  view: "plan" | "inputs" | "analysis" | "results";
  update: ReturnType<typeof useStudioParams>["update"];
};

function StudioBody({ project_id, experimentQuery, archived, caps, list, runParam, view, update }: BodyProps) {
  const x = experimentQuery.data!;
  const plan = usePlanDraft(x);
  const edit = useEditExperiment(project_id, x.id);
  const up = useArtifactUpload(project_id);
  const [captureTab, setCaptureTab] = useState("record");
  const [focusImport, setFocusImport] = useState(false);
  const [attachNote, setAttachNote] = useState<string | null>(null);
  const [attachConflict, setAttachConflict] = useState(false);

  // Resolve attached inputs from the experiment-filtered list plus the general list.
  const forExp = useArtifacts(project_id, { experiment_id: x.id });
  const all = useArtifacts(project_id, {});
  const inputs = useMemo(() => {
    const m = new Map<ID, Artifact>();
    for (const a of [...all.items, ...forExp.items]) m.set(a.id, a);
    if (up.artifact) m.set(up.artifact.id, up.artifact);
    return m;
  }, [all.items, forExp.items, up.artifact]);

  const runs = useRuns(project_id, { experiment_id: x.id, kind: "analysis" });
  // A linked run must be an analysis of this experiment; keep paging until found or exhausted.
  const runFound = runParam != null && runs.items.some((r) => r.id === runParam);
  const { has_next_page: moreRuns, is_fetching_next_page: fetchingRuns, load_next_page: loadRuns } = runs;
  useEffect(() => {
    if (runParam && !runFound && moreRuns && !fetchingRuns) loadRuns();
  }, [runParam, runFound, moreRuns, fetchingRuns, loadRuns]);
  const runMissing = runParam != null && !runFound && !runs.is_loading && !moreRuns;
  const runId = runParam ? (runFound ? runParam : null) : runs.items[0]?.id ?? null;

  function uploadRecording(r: Recording) {
    const ext = r.mime_type.includes("mp4") ? "mp4" : "webm";
    up.start({
      blob: r.blob,
      request: {
        filename: `recording-${r.recorded_at.replace(/[:.]/g, "-")}.${ext}`,
        mime_type: r.mime_type, size_bytes: r.blob.size, kind: "video", origin: "observed", experiment_id: x.id,
        capture: { method: "browser_camera", recorded_at: r.recorded_at, recording_permission_confirmed: true },
      },
    });
  }

  function uploadFile(file: File, kind: Artifact["kind"] & ("document" | "dataset" | "image" | "video" | "audio" | "code"), origin: "observed" | "simulated" | "reference" | "generated") {
    const mime = mimeForFile(file.type, file.name);
    up.start({
      // Keep the transfer Content-Type consistent with the normalized upload declaration.
      blob: file.slice(0, file.size, mime),
      request: {
        filename: file.name, mime_type: mime, size_bytes: file.size, kind, origin, experiment_id: x.id,
        capture: { method: "file_upload", recorded_at: null, recording_permission_confirmed: false },
      },
    });
  }

  /** Attach a ready artifact through an experiment save. A conflict keeps the artifact and offers a retry. */
  async function attach(a: Artifact) {
    setAttachNote(null);
    if (plan.draft?.input_artifact_ids.includes(a.id) || x.input_artifact_ids.includes(a.id)) { up.reset(); return; }
    if (plan.dirty) {
      plan.setDraft((d) => ({ ...d, input_artifact_ids: [...d.input_artifact_ids, a.id] }));
      setAttachNote(`“${a.filename}” was added to your unsaved plan. Save the plan to attach it.`);
      up.reset();
      return;
    }
    if (!experimentQuery.etag) return;
    try {
      const res = await edit.mutateAsync({ body: { input_artifact_ids: [...x.input_artifact_ids, a.id] }, etag: experimentQuery.etag });
      plan.markSaved(res.data);
      setAttachConflict(false);
      up.reset();
    } catch (err) {
      if (errorCode(err) === "REVISION_CONFLICT") { setAttachConflict(true); experimentQuery.refetch(); }
    }
  }

  const uploadsCaps = caps?.uploads;
  const ready = up.phase === "ready" ? up.artifact : null;
  const taskCopy = {
    plan: "Set the hypothesis and protocol, then save your plan.",
    inputs: "Record a video or add a file to your plan.",
    analysis: "Choose a method and inputs, then start the run.",
    results: "Review the run and its evidence.",
  }[view];
  const taskLabels = { plan: "Plan", inputs: "Inputs", analysis: "Analysis", results: "Results" };
  function moveTo(next: typeof view) {
    if (next !== "inputs") setFocusImport(false);
    update({ view: next });
  }
  function uploadDataFile() {
    setCaptureTab("import");
    setFocusImport(true);
    moveTo("inputs");
  }

  return (
    <>
      <header className={styles.context}>
        <div className={styles.topBar}>
        <ExperimentSelector project_id={project_id} experiments={list.items} selected={x.id}
          onSelect={(id) => update({ experiment: id, run: null, view: "plan" })} hasMore={list.has_next_page} loadMore={list.load_next_page}
          dirty={plan.dirty} archived={archived} />
          <span className={plan.dirty ? styles.dirtyState : styles.savedState} role="status">{plan.dirty ? "Unsaved changes" : `Saved · revision ${x.revision}`}</span>
          <Button variant="primary" disabled={archived} onClick={uploadDataFile}>Upload data file</Button>
        </div>
        <p className={styles.taskGuidance}>{taskCopy}</p>
        <div role="tablist" aria-label="Experiment tasks" className={styles.taskTabs}>
          {STUDIO_VIEWS.map((item) => <button key={item} type="button" role="tab" aria-selected={view === item}
            aria-controls={`studio-panel-${item}`} id={`studio-tab-${item}`} tabIndex={view === item ? 0 : -1}
            className={styles.taskTab} onClick={() => moveTo(item)} onKeyDown={(event) => {
              const i = STUDIO_VIEWS.indexOf(item);
              const next = event.key === "ArrowRight" ? (i + 1) % STUDIO_VIEWS.length : event.key === "ArrowLeft" ? (i + STUDIO_VIEWS.length - 1) % STUDIO_VIEWS.length : event.key === "Home" ? 0 : event.key === "End" ? STUDIO_VIEWS.length - 1 : -1;
              if (next >= 0) { event.preventDefault(); moveTo(STUDIO_VIEWS[next]); document.getElementById(`studio-tab-${STUDIO_VIEWS[next]}`)?.focus(); }
            }}>{taskLabels[item]}</button>)}
        </div>
      </header>

      <ExperimentImplementation project_id={project_id} experiment={x} archived={archived}
        dirty={plan.dirty} remoteNewer={plan.remoteNewer} enabled={caps?.features.agent_code_execution === true} />

      <section id="studio-panel-plan" role="tabpanel" aria-labelledby="studio-tab-plan" tabIndex={0} hidden={view !== "plan"} className={styles.taskPanel}>
        <ExperimentEditor project_id={project_id} experiment={x} etag={experimentQuery.etag} plan={plan} inputs={inputs}
          archived={archived} refetch={experimentQuery.refetch} />
        <div className={styles.taskActions}><Button variant="primary" onClick={() => moveTo("inputs")}>Continue to inputs</Button></div>
      </section>

      <section id="studio-panel-inputs" role="tabpanel" aria-labelledby="studio-tab-inputs" tabIndex={0} hidden={view !== "inputs"} className={styles.taskPanel}>
        {view === "inputs" && <section className={styles.panel} aria-labelledby="studio-inputs">
          <h3 id="studio-inputs">Add input data</h3>
          <p className={styles.muted}>Leaving Inputs stops the camera and discards any recording that has not been uploaded.</p>
          <Tabs label="Input source" value={captureTab} onChange={setCaptureTab} items={[
            { id: "record", label: "Record video", content: view === "inputs" && captureTab === "record" ? (
              <CapturePanel uploads={uploadsCaps} disabled={archived} onUpload={uploadRecording} uploadBusy={up.busy}
                uploadedBlob={up.phase === "ready" ? up.input?.blob ?? null : null} />
            ) : null },
            { id: "import", label: "Import a file", content: captureTab === "import" ? <FileImport uploads={uploadsCaps} disabled={archived || up.busy} onUpload={uploadFile}
              autoFocus={focusImport} onPickerFocused={() => setFocusImport(false)} /> : null },
          ]} />
          <UploadProgressView up={up}>
            {ready && <div className={styles.stack}>
              {attachConflict && <p className={styles.note} role="alert">The plan changed while attaching. The file is saved; attach it to the refreshed plan.</p>}
              {edit.error != null && !attachConflict && <ErrorNotice {...describeError(edit.error, "File saved, but not attached")} />}
              <div className={styles.row}>
                <Button variant="primary" pending={edit.isPending} disabled={archived || plan.remoteNewer} onClick={() => void attach(ready)}>{attachConflict ? "Attach to refreshed plan" : "Attach to this plan"}</Button>
                <Button onClick={up.reset}>Not now</Button>
              </div>
              {plan.remoteNewer && <p className={styles.muted}>Resolve the plan revision notice first.</p>}
            </div>}
          </UploadProgressView>
          {attachNote && <p className={styles.note} role="status">{attachNote}</p>}
          <div className={styles.taskActions}><Button variant="primary" onClick={() => moveTo("analysis")}>Continue to analysis</Button></div>
        </section>}
      </section>

      <section id="studio-panel-analysis" role="tabpanel" aria-labelledby="studio-tab-analysis" tabIndex={0} hidden={view !== "analysis"} className={styles.taskPanel}>
        <section className={styles.panel} aria-labelledby="studio-launch">
          <h3 id="studio-launch">Configure analysis</h3>
          <AnalysisSetup key={`${x.id}:${x.implementation?.code_artifact_id ?? ""}`} project_id={project_id} experiment={x} inputs={inputs} caps={caps}
            hasMoreArtifacts={all.has_next_page || forExp.has_next_page}
            loadingArtifacts={all.is_fetching_next_page || forExp.is_fetching_next_page}
            loadMoreArtifacts={() => {
              if (all.has_next_page && !all.is_fetching_next_page) all.load_next_page();
              if (forExp.has_next_page && !forExp.is_fetching_next_page) forExp.load_next_page();
            }}
            planDirty={plan.dirty} planOutOfDate={plan.remoteNewer} archived={archived}
            refetchExperiment={experimentQuery.refetch}
            onNavigate={(next) => moveTo(next)}
            onLaunched={(r: Run) => update({ run: r.id, view: "results" })} />
        </section>
      </section>

      <section id="studio-panel-results" role="tabpanel" aria-labelledby="studio-tab-results" tabIndex={0} hidden={view !== "results"} className={`${styles.results} ${styles.taskPanel}`}>
        <div className={styles.resultsHead}>
          <h3 id="studio-results">Results</h3>
          {runs.items.length > 0 && <RunPicker runs={runs.items} value={runId} onChange={(id) => update({ run: id })}
            hasMore={runs.has_next_page} loadMore={runs.load_next_page} />}
        </div>
        {runMissing ? <EmptyState title="Run unavailable" action={<Button onClick={() => update({ run: null })}>Clear selection</Button>}>That run is not an analysis of this experiment.</EmptyState>
          : runParam && !runFound ? <Skeleton height="8rem" />
          : runId ? <ResultsPane project_id={project_id} run_id={runId} />
          : <div className={styles.stack}><p className={styles.muted}>No analysis has been run for this plan yet. Results appear after a run is accepted.</p><Button variant="primary" onClick={() => moveTo("analysis")}>Configure analysis</Button></div>}
      </section>
    </>
  );
}

function RunPicker({ runs, value, onChange, hasMore, loadMore }: {
  runs: Run[]; value: ID | null; onChange: (id: ID) => void; hasMore: boolean; loadMore: () => void;
}) {
  const current = runs.find((r) => r.id === value);
  return (
    <div className={styles.row}>
      <label className={styles.smallLabel} htmlFor="studio-run-picker">Run</label>
      <select id="studio-run-picker" className={`${styles.input} ${styles.autoWidth}`} value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {runs.map((r) => (
          <option key={r.id} value={r.id}>
            {r.created_at.slice(0, 16).replace("T", " ")} UTC · {r.status}
            {r.input.kind === "analysis" ? ` · plan rev ${r.input.experiment_revision}` : ""}
          </option>
        ))}
      </select>
      {hasMore && <Button onClick={loadMore}>Older runs</Button>}
      {current && <span className={styles.muted}>Started <TimestampLabel iso={current.created_at} /></span>}
      {current && current.input.kind === "analysis" && <StatusBadge tone="neutral">Evidence from plan revision {current.input.experiment_revision}</StatusBadge>}
    </div>
  );
}
