# Agent B handoff — draft complete, awaiting Agent C foundation

> Historical handoff. The foundation-waiting status below is not the current runtime status. Next-interface requirements are public in [Research desk](../research-workspace-spec.md), [Materials views](../materials-views-spec.md), and [Reports](../reports-spec.md). Experiment cards expose several plans but keep editing, calibration, upload, and launch in Studio. Reuse saved chart/media previews and measurement qualifications without adding browser physics calculations or interactive cross-run plots. Current repository instructions govern delegation. These changes are specified, not implemented or verified by this handoff.

Status: all Agent B deliverables are drafted. They compile against the contract-derived interface in §3 below. They are **not connected to live data** because C's `contracts/`, `lib/` and `providers/` do not exist yet. No version-control changes have been made.

## 1. Files

### `features/studio/` (public: `StudioScreen`)
- `StudioScreen.tsx`: experiment selection (`?experiment=`), plan editor, input capture/import, attach, launch, and results for the selected run (`?run=`). The body is re-keyed per experiment so drafts, capture and uploads never leak between plans.
- `ExperimentSelector.tsx`: switch plans (confirms before discarding unsaved edits); "New experiment" dialog (POST with all required creation fields).
- `plan/`
  - `draft.ts`: `PlanDraft` = the exact creation/PATCH fields; diff-based PATCH bodies; client validation mirroring the contract (calibration points distinct, non-negative, length > 0, uncertainty ≥ 0, artifact attached).
  - `usePlanDraft.ts`: local draft vs saved base revision. A newer remote revision replaces a clean draft but never a dirty one; then `remoteNewer` and per-field `conflicting` drive reconciliation.
  - `ExperimentEditor.tsx` (protocol editor inline), `VariableEditor.tsx`, `ListEditor.tsx`, `InputList.tsx`, `CalibrationEditor.tsx`, `ImagePointPicker.tsx`, `ConflictPanel.tsx`.
- `capture/`: `useCamera.ts` (state machine), `CapturePanel.tsx`, `CameraPreview.tsx`, `RecordingControls.tsx`, `RecordingReview.tsx`.
- `upload/`: `useArtifactUpload.ts`, `FileImport.tsx`, `UploadProgressView.tsx`.
- `launch/`: `AnalysisSetup.tsx`, `AnalysisLaunchSummary.tsx`.
- `format.ts`, `useStudioParams.ts`, `studio.module.css`.

### `features/results/` (public: `ResultsPane`, `ResultsPaneProps`)
- `ResultsPane.tsx`, `MeasurementTable.tsx`, `SeriesSelector.tsx`, `EvidenceViewer.tsx`, `UncertaintyDetails.tsx`, `ChartGallery.tsx`, `ScientificWarnings.tsx`, `useAllMeasurements.ts`, `format.ts`, `results.module.css`.

B uses A's `@/components/ui` primitives and `hrefs` from `@/components/shell`. B created no shared controls, query cache, upload client, event stream, or run-status enum.

## 2. Requests to Agent C

1. **Route mounting**: `/projects/[projectId]/studio` → `<Suspense><StudioScreen project_id=… /></Suspense>` (uses `useSearchParams`). Key it by `project_id` so capture is released on a project change. Mount `ResultsPane` in the run-detail screen.
2. **Interface match**: implement §3 as written, or tell B what differs.
3. **Upload facade**: `putContent` must reject with `name === "AbortError"` when aborted; B treats that as user cancellation.
4. **Artifact cache**: after `uploads.complete`, B relies on C's events/invalidation to add the artifact to lists. B also puts the returned artifact in its local map, so attachment works immediately.
5. **Backend gap (frame extraction)**: interactive video calibration needs an authoritative decoded-frame route (frame index, decoded timestamp, native size). Please coordinate it with the backend. Until then B keeps video point selection unavailable.

## 3. Interface B compiled against (in addition to Agent A's §3)

```ts
// @/contracts/api — contract types verbatim, plus Measurement, RunResults, RunInput, Upload, UploadRequest, Calibration
// @/contracts/requests
type CreateExperimentRequest = Omit<Experiment, "id" | "project_id" | "revision" | "created_at" | "updated_at">
type EditExperimentRequest = Partial<CreateExperimentRequest>
type StartRunRequest = Extract<RunInput, { kind: "analysis" }> | Extract<RunInput, { kind: "report" }>

// @/lib/queries  (null id ⇒ no request)
useExperiment(project_id, experiment_id | null): DetailQuery<Experiment>
useArtifact(project_id, artifact_id | null): DetailQuery<Artifact>
useRuns(project_id, { experiment_id?, status?, kind? }): ListQuery<Run>
useRun(project_id, run_id | null): DetailQuery<Run>
useRunResults(project_id, run_id | null): DetailQuery<RunResults>
useMeasurements(project_id, run_id | null, { series? }): ListQuery<Measurement>
useCreateExperiment(project_id): Mutation<{ body: CreateExperimentRequest, idempotency_key: string }, Experiment>
useEditExperiment(project_id, experiment_id): Mutation<{ body: EditExperimentRequest, etag: string }, Experiment>
useStartRun(project_id): Mutation<{ body: StartRunRequest, idempotency_key: string }, Run>

// @/lib/api
api.uploads.create(project_id, UploadRequest, { idempotency_key, signal? }): Promise<ApiResult<Upload>>
api.uploads.get(project_id, upload_id, { signal? }): Promise<ApiResult<Upload>>
api.uploads.putContent(project_id, upload_id, Blob, { signal?, on_progress?(UploadProgress) }): Promise<ApiResult<null>>
api.uploads.complete(project_id, upload_id, { idempotency_key, signal? }): Promise<ApiResult<Artifact>>
artifactContentUrl(project_id, artifact_id, "inline" | "attachment"): string
```

Error codes B branches on: `REVISION_CONFLICT`, `EXPERIMENT_REVISION_CONFLICT`, `IDEMPOTENCY_CONFLICT`, `PROJECT_ARCHIVED`, `FEATURE_UNAVAILABLE`, `VALIDATION_FAILED`, `UPLOAD_EXPIRED`, `UPLOAD_IN_PROGRESS`, `UPLOAD_CONTENT_CONFLICT`, `UPLOAD_TOO_LARGE`, `PROJECT_QUOTA_EXCEEDED`, `UNSUPPORTED_MEDIA_TYPE`, `MEDIA_DECODE_FAILED`, `HASH_MISMATCH`.

## 4. Behavior established by source review

**Plan editing (B1)**
- "Unsaved changes" badge plus explicit Save and Discard. A PATCH sends only the changed fields, with the loaded ETag. Blank list rows are stripped on save.
- A remote update never replaces a dirty form. On `412`, or when a newer revision arrives, `ConflictPanel` shows saved vs local values for fields both sides changed. "Use saved" works per field; "Continue from revision N with my edits" rebases. Save stays blocked until the user resolves the conflict.
- Archived projects make the plan read-only.

**Launch (B1)**
- Launch is blocked while the plan is dirty or out of date, so the run request always comes from the saved experiment and its `revision`.
- Default bouncing-ball path: one video, `pipeline: "bouncing_ball_v1"`, `code_artifact_id: null`, parameters only `start_time_s`, `end_time_s` (null = media end) and `object_hint`. The interval is validated against the reported duration.
- The launch summary shows the plan revision, input, interval, object, pipeline, calibration mode and execution limits.
- Each deliberate launch gets a new key. After an ambiguous failure, Start is disabled until "Retry submission" (same key) or "Dismiss". `EXPERIMENT_REVISION_CONFLICT` refreshes the plan and requires a new explicit submission.
- After a `202`, the run is selected (`?run=`) and linked immediately; nothing waits for execution.

**Capture (B2)**
- The camera starts only on "Enable camera", video only.
- The recorder MIME type must be both browser-supported and in `accepted_mime_types`. If none fits, file import remains the path.
- Recording shows a persistent "Recording" text indicator with elapsed / max time. Invalid transitions are disabled.
- The recorder and every track stop on stop, discard, error, track `ended` (permission revoked or device removed) and unmount.
- The preview is never mirrored. Review plays the recorded Blob, not the live stream, through one object URL revoked on replace, discard or unmount.
- Local guards stop recording at `max_video_duration_ms` and at about 95% of `max_file_bytes`. The backend stays authoritative.
- Upload requires "Upload recording". The recording is kept if the transfer fails. A `beforeunload` prompt and on-page text explain that leaving discards an unuploaded recording.
- Recording uploads send `capture.method: "browser_camera"`, `recorded_at` and `recording_permission_confirmed: true`.

**Upload (B3)**
- UI phases are kept separate from backend `Upload.status`: `selected`, `creating`, `transferring`, `finalizing`, `ready`, `failed`, `cancelled`.
- Create and complete each keep one idempotency key across retries. A retry first reads the Upload: `pending` → PUT the same bytes again; `uploaded`/`completed` → complete; `failed` → terminal, with the server message; `expired` → a new session.
- Cancel aborts the transfer only; "Resume upload" continues the same session.
- Byte progress is shown only when the transport reports it; otherwise the bar is indeterminate.
- File import checks MIME, size and video duration locally, previews video, image and audio, and lets the user choose an origin, including **Simulated**.
- Attach is an experiment save. If the plan is dirty, the file is added to the draft with a note to save. On a `412`, the ready artifact is kept and "Attach to refreshed plan" is offered; nothing is uploaded again.

**Calibration (B4)**
- `none` is the default and is fully supported; the UI states that physical scale is never inferred.
- `reference_length` is editable only for an attached image with server-reported `width_px`/`height_px`, when `features.image_analysis` is on. It uses frame 0.
- Clicks map to native pixels by scaling (no crop, mirror or letterbox) and are disabled if the decoded size differs from the server's. Numeric fields are the authoritative and accessible way to set points.
- A saved video reference calibration is shown read-only.

**Results (B5)**
- Measurements load page by page up to 2000 rows, then "Load more". Rows are grouped by series × quantity × unit; unlike units are never in one column.
- Missing or rejected values show "Unavailable" with the first explanation line. A null uncertainty shows "Not estimated", never 0. Simulated data, a partial or failed or cancelled run, the no-calibration condition and server warnings are shown as banners.
- "Pipeline completed" states that completion does not confirm the hypothesis.
- Evidence opens the artifact. Video seeks to `time_s`, labeled approximate; the frame index is shown but not claimed. Dataset evidence gives the row number.
- Charts and annotated media are backend artifacts only; SVG is not inlined. A "Trace back" section links the raw input, provenance manifest, run details and report.

## 5. Known limitations

- Interactive video calibration is unavailable until frame extraction exists (§2.5).
- No `sha256` is sent on upload (optional in the contract; hashing large videos in the browser was skipped).
- The series selector lists only series found in loaded rows; it is labeled as such.
- Attached inputs resolve from the experiment-filtered and general artifact lists, with a per-ID fetch fallback. The calibration editor only sees inputs present in those lists.
- Camera permission revocation discards an in-progress recording rather than keeping the partial capture.
- Switching experiments with unsaved edits uses a native `confirm()`.

## 6. Unverified (needs human review)

Nothing has run against a backend or in a real browser camera session. These need human checks: camera permission prompt and denial, device unplug mid-recording, MIME selection on Safari and Firefox, the recording size and duration guards, upload cancel/resume/expiry, a plan conflict between two tabs, image point placement accuracy, video seek behavior, wide-table scrolling at 320px, and screen-reader output for recording status and upload progress.
