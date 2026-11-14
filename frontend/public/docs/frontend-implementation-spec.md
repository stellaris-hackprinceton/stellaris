# Stellaris frontend implementation specification

Version: **1.0-draft**  
Status: **Implementation plan. No frontend implementation or agent execution is implied.**  
Prepared: **November 13, 2026**  
Companion document: [Frontend–backend contract](frontend-backend-contract.md), version `1.0.0-draft`.

## 1. Context carried forward from this chat

Stellaris is the research platform described in the supplied HackPrinceton 2026 document. Its frontend connects a scientific question to literature, an experiment plan, real experimental inputs, inspectable measurements, and a scientific report in one persistent project.

The preceding work in this chat established the proposed API contract. This spec implements that boundary rather than creating a second API. Resource schemas, error codes, project access, upload semantics, run states, and SSE payloads come from the companion contract. If this document conflicts with that contract, record the discrepancy and reconcile it before changing transport behavior.

The requested team is exactly three implementation agents:

- **Agent A: Claude, using Opus or Fable as selected by the user.** Owns the shared interface, project entry, chat, and research canvas.
- **Agent B: Claude, using Opus or Fable as selected by the user.** Owns Experiment Studio, browser capture, calibration controls, and scientific results inspection.
- **Agent C: GPT-6.1 Sol.** Owns API integration, shared server state, live events, execution, artifacts, reports, and final integration.

These names identify assignment slots. The responsibilities do not depend on a claim about which model is strongest or whether a particular model name is available in a launcher. Two separate Claude sessions fill A and B even if both use the same model.

These planning documents were originally prepared in the Upstream workspace. Their canonical shared location is now **`frontend/public/docs/` in the Stellaris repository**. All implementation paths below are relative to the existing `frontend/` root. An initialized Next.js application already exists there. Extend that application rather than creating a second scaffold or placing web components inside the Upstream game's directory.

The workflow constraints carried forward from this chat are:

- Do not create, run, or maintain automated tests, harnesses, or fixtures.
- Do not launch the game or editor for agent-driven verification.
- Verify through focused source inspection and review. Human interaction review is a separate handoff.
- Keep shared Stellaris specifications and agent handoffs in `public/docs/` so they can be committed and used by all three agents. Preserve the original workspace's scratchpad and game content.
- This spec is not a taskboard claim. If implementation is coordinated through the shared board, follow its ownership procedure before claiming work. A role assignment here does not override another chat's claim.

## 2. Product outcome and scope

The completed frontend lets a researcher perform this sequence:

1. Create or reopen a project and state a research question.
2. Ask the agent to investigate literature and design an experiment.
3. Inspect sources, citations, hypotheses, protocol, variables, and limitations.
4. Record a video or select an existing file, preview it, and explicitly upload it.
5. Attach the ready artifact to an experiment and save its configuration.
6. Start analysis and inspect genuine server progress, logs, and failures.
7. Inspect annotated evidence, measurement values, units, uncertainty, and charts.
8. Generate and download a Markdown report grounded in committed results.
9. Refresh or reopen the project and recover its saved history and outputs.

The primary delivery path is the bouncing-ball example. Other features may appear only when the backend reports support and the relevant frontend workflow exists. A backend feature flag alone does not promise a complete frontend workflow.

The MVP does not implement live media streaming, microphone capture, HPC controls, collaboration, notebooks, PDF/DOCX export, knowledge graphs, or a freeform diagram editor. Research Canvas is a structured research view. Charts initially display backend-authored image artifacts. Generated Python can be inspected or uploaded as an artifact, but a browser IDE is outside this scope.

## 3. Architecture and selected stack

Use React, Next.js App Router, and TypeScript with strict checking. Use TanStack Query for server resources. Use component-local React state for unsaved form values, capture state, selection, and disclosure controls. Do not introduce a second global copy of server entities.

Use CSS custom properties and CSS Modules. A small set of shared components provides consistent controls. Use one icon set, introduced by Agent A through a dependency request to Agent C. Markdown rendering disables embedded HTML and limits links to approved protocols. Select the renderer and pin its dependency through Agent C.

Agent C owns dependency selection and the lockfile. Pin the actual installed versions together during setup and record them in the implementation handoff. This spec does not assert uninstalled version numbers.

Keep route composition separate from browser behavior. Place camera APIs, interactive forms, query consumers, and the event connection in client components. Static route adapters may remain server components. This follows the supported [Next.js server/client component boundary](https://nextjs.org/docs/app/getting-started/server-and-client-components).

### Runtime ownership

```text
Root layout
  AppProviders                         [C]
    SessionGate                        [C]
      ProjectsScreen                   [A]   /projects
      ProjectRuntime                   [C]   /projects/:project_id/*
        ProjectShell                   [A]
          ProjectNavigation            [A]
          ProjectHeader                [A]
          Route content
            ResearchScreen             [A]
            StudioScreen               [B]
            ExecutionScreen            [C]
              ResultsPane              [B]
            WorkspaceScreen            [C]
            ReportScreen               [C]
          ResearchChat                 [A]
          ApprovalDialog               [C]
```

There is one ProjectRuntime and one SSE connection for the active project in a browser tab. Route switches within that project reuse the runtime. Leaving the project closes its stream, aborts obsolete requests, and releases capture resources. Separate browser tabs may have separate streams.

ProjectRuntime supplies session/capability state, project identity, connectivity state, and access to the shared query client. It does not become a general container for every feature's local state.

### Routes

- `/` redirects to `/projects` after session resolution.
- `/projects` lists projects and supports creation, archive visibility, and reopening.
- `/projects/[projectId]` redirects to that project's `/research` view.
- `/projects/[projectId]/research` shows evidence, hypotheses, protocol summaries, and source details. Research Chat remains available alongside it.
- `/projects/[projectId]/studio` selects or creates an experiment, collects media, saves setup, and starts analysis. Query parameters `experiment` and `run` preserve selection.
- `/projects/[projectId]/runs` lists run history.
- `/projects/[projectId]/runs/[runId]` shows execution, logs, approvals, and scientific results.
- `/projects/[projectId]/workspace` browses persisted artifacts and previews selected files. Query parameter `artifact` preserves selection.
- `/projects/[projectId]/reports/[artifactId]` previews a saved Markdown report with evidence links and a download action.

Opaque IDs must be encoded in URLs. A selected object is validated against the route's project before display. Missing or inaccessible resources show a project-local unavailable state. Route files and shared layouts are owned only by Agent C.

## 4. Interface structure and visual requirements

This is an application for carrying out research. Prioritize readable evidence, clear controls, and honest state over marketing treatments. The following visual values are proposed implementation defaults, not descriptions of an existing app.

### Desktop and smaller screens

- At viewport widths of 1280 CSS pixels and above, use a 208-pixel project/navigation sidebar, a flexible content area, and a 352-pixel chat rail. The chat rail can collapse. Preserve a practical content minimum rather than forcing three columns into a narrow window.
- From 768 through 1279 pixels, keep the main workspace visible and open chat in a dismissible side sheet. Collapse project navigation to a menu when necessary.
- Below 768 pixels, show one main surface, a compact project header, and navigation in a menu. Open chat as a full-height sheet. Stack Studio setup and preview vertically.
- At 320 pixels, every action remains reachable. Tables may scroll inside labeled containers. The document itself must not develop horizontal overflow.
- Desktop panels scroll independently where useful. Mobile reading uses ordinary vertical flow. Sticky controls must not obscure the final form fields or measurements.

### Shared design tokens, owned by A

Start with these named CSS variables and adjust them only in the shared stylesheet:

```css
--color-background: #f6f7f9;
--color-surface: #ffffff;
--color-surface-muted: #edf1f5;
--color-text: #15212b;
--color-text-muted: #53616f;
--color-border: #ccd5df;
--color-accent: #225d91;
--color-success: #1b6a45;
--color-warning: #8a5400;
--color-danger: #a32929;
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;
--radius-control: 6px;
--radius-panel: 10px;
```

Use a system sans-serif family and a monospace family for code, logs, IDs, and numerical alignment. Body text is 16 pixels, compact labels 14 pixels, and section titles 18–24 pixels. Prose stays near 70 characters per line. Use tabular figures where numerical comparisons matter.

Every interactive control needs default, hover, focus, disabled, pending, and error behavior. Semantic colors also carry text or an icon. Recording uses a persistent textual indicator and elapsed time. Success labels are reserved for confirmed resource state.

Required shared components: `Button`, `IconButton`, `Field`, `TextInput`, `TextArea`, `Select`, `Dialog`, `Sheet`, `Tabs`, `StatusBadge`, `EmptyState`, `ErrorNotice`, `Skeleton`, `MarkdownView`, `ArtifactLink`, and `TimestampLabel`. Agent A publishes named exports from `components/ui/index.ts`. Feature agents request additions rather than creating duplicate shared controls.

Use visible labels, keyboard navigation, focus restoration for overlays, an accessible description for icon buttons, and suitable live announcements. Do not announce every streamed token or log line. Respect reduced motion. Primary controls should have at least a 40-pixel target size. Contrast and focus visibility require human review before presentation.

## 5. Shared frontend module contracts

### File boundaries

```text
src/
  app/                                 C: routes, layouts, error boundaries
  providers/                           C: session/query/project runtime
  contracts/                           C: API types and request DTOs
  lib/
    api/                               C: HTTP, uploads, errors, URLs
    queries/                           C: keys, resource hooks, mutations
    events/                            C: one SSE client and cache updates
  components/
    ui/                                A: shared controls and Markdown
    shell/                             A: navigation, header, chat placement
  styles/
    tokens.css                         A
    global.css                         A
  features/
    projects/                          A
    research/                          A: chat, canvas, sources, claims
    studio/                            B: plan editing, capture, uploads UI
    results/                           B: measurements and evidence inspection
    execution/                         C: history, progress, logs, approvals
    workspace/                         C: artifacts and generic preview
    reports/                           C: report composition and saved preview
public/docs/handoffs/
  agent-a.md                           A
  agent-b.md                           B
  agent-c.md                           C
```

The source tree above describes module ownership. The existing scaffold uses root-level `app/`. Preserve that layout and map the proposed `src/` module paths to the existing project structure rather than moving the scaffold just to match this illustration. CSS Modules belong to the owner of the corresponding component. Only Agent C edits `package.json`, the lockfile, Next.js configuration, TypeScript configuration, environment examples, or route files. Only Agent A edits global tokens, global CSS, and shared UI primitives. The frontend handoff documents above are future implementation deliverables, not files created by this spec.

Features may import public contracts, query hooks, UI components, and their own files. They must not import another feature's private files. Cross-feature imports use the named public exports below:

```ts
// Owned by A
export type ProjectShellProps = {
  project_id: ID,
  children: React.ReactNode
}
export function ProjectShell(props: ProjectShellProps): React.ReactNode
export function ProjectsScreen(): React.ReactNode
export function ResearchScreen(props: { project_id: ID }): React.ReactNode

// Owned by B
export function StudioScreen(props: { project_id: ID }): React.ReactNode
export function ResultsPane(props: {
  project_id: ID,
  run_id: ID
}): React.ReactNode

// Owned by C
export function ExecutionScreen(props: {
  project_id: ID,
  run_id?: ID
}): React.ReactNode
export function WorkspaceScreen(props: { project_id: ID }): React.ReactNode
export function ReportScreen(props: {
  project_id: ID,
  artifact_id: ID
}): React.ReactNode
```

These are interface declarations, not implementation bodies. Agent C adapts route parameter conventions to the pinned Next.js version. Do not independently invent camelCase copies of API entities. Wire resources retain `snake_case`. A view-specific derived label is allowed when its origin is clear.

### API client, owned by C

`contracts/api.ts` contains the companion contract's public resource types. `contracts/requests.ts` contains creation/PATCH DTOs that exclude server-authored fields. Do not use `Partial<Project>` as a project mutation type because it would admit IDs and timestamps.

The shared API facade provides typed operations grouped as `session`, `capabilities`, `projects`, `messages`, `sources`, `claims`, `experiments`, `uploads`, `artifacts`, `runs`, and `approvals`. These map directly to the documented routes. Feature components do not call `fetch`, XMLHttpRequest, or EventSource directly. Browser media APIs remain local to Studio.

```ts
type ApiResult<T> = {
  data: T,
  etag: string | null,
  request_id: string | null
}
type CommandOptions = {
  idempotency_key: string,
  signal?: AbortSignal
}
type EditOptions = {
  etag: string,
  signal?: AbortSignal
}
type UploadProgress = {
  loaded_bytes: number,
  total_bytes: number | null
}
```

The facade includes CSRF headers, same-origin credentials, JSON serialization, error-envelope parsing, safe binary handling, and metadata extraction. JSON POST calls require `CommandOptions`. PATCH calls require `EditOptions`. `uploads.putContent` accepts a Blob/File, an abort signal, and an optional upload-progress callback. XMLHttpRequest may implement byte progress behind this facade. It must preserve the same authentication, CSRF, and error behavior as the other transport.

Provide one `artifactContentUrl(project_id, artifact_id, disposition)` helper. Inline image/video/audio previews use authenticated content URLs without downloading the whole file into application state. Text and reports use authenticated text reads. Do not put session tokens in URLs.

The frontend never adds new endpoints, searches vendor APIs directly, or sends model/provider keys to the browser. It does not implement a replacement Flask API in Next.js route handlers. A same-origin development/production proxy forwards the existing `/api/v1` routes, cookies, bytes, range headers, and unbuffered SSE.

### Query hooks, owned by C

Publish these resource hooks from `lib/queries/index.ts` during the foundation handoff:

- `useSession()`, `useCapabilities()`, `useProject(project_id)`, and `useWorkspace(project_id)`.
- `useProjects(filters)`, `useMessages(project_id)`, `useSources(project_id, filters)`, and `useClaims(project_id, filters)`.
- `useExperiments(project_id)`, `useExperiment(project_id, experiment_id)`, and `useArtifact(project_id, artifact_id)`.
- `useArtifacts(project_id, filters)`, `useRuns(project_id, filters)`, and `useRun(project_id, run_id)`.
- `useRunResults(project_id, run_id)`, `useMeasurements(project_id, run_id, filters)`, `useRunLogs(project_id, run_id)`, and `useApprovals(project_id, run_id)`.

Detail hooks expose `data`, `etag` where relevant, loading/error state, and explicit refetch. Lists expose flattened deduplicated `items`, loading/error state, `has_next_page`, and `load_next_page`. IDs that are not selected do not produce requests.

Publish mutation hooks `useCreateProject`, `useEditProject`, `useSubmitMessage`, `useCreateSource`, `useCreateExperiment`, `useEditExperiment`, `useStartRun`, `useCancelRun`, and `useDecideApproval`. Their mutation variable types are exported alongside them. Hooks do not silently regenerate a command key during a retry.

Upload orchestration lives in B's `useArtifactUpload` hook and calls C's typed upload facade. This keeps Studio's local Blob and progress state out of the shared entity cache while retaining one transport implementation.

Query keys start with `['session']`, `['capabilities']`, `['projects', filters]`, or `['project', project_id, resource, ...selection]`. Include every filter and selected ID in the key. This follows [TanStack Query's query-key rules](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys). Agent C exports key factories so event handlers and features use the same identities.

### State and editing rules

- Server resources live in the query cache. Form drafts and capture Blobs stay local. Do not store media, reports, or API resource copies in localStorage.
- UI preferences such as a collapsed chat rail may persist locally. CSRF tokens stay in memory. Changing users clears resource caches.
- URL query parameters hold shareable selection and filters. Opening a citation, run, artifact, or report works after refresh.
- Every user action gets one stable idempotency key. An ambiguous network outcome offers “Check status” or “Retry submission” with that key. A deliberate new scientific run gets a new key.
- PATCH saves use the loaded ETag. A `412` preserves the local draft, fetches the latest version, and offers comparison/reapply. Do not overwrite a new revision automatically.
- A `409 EXPERIMENT_REVISION_CONFLICT` before analysis offers refreshed plan review and requires an explicit new submission. Do not silently analyze a different protocol.
- No optimistic completion. A `202` shows acceptance or queued state, not measured results.
- Archiving disables new-work controls. Existing accepted runs remain visible and can still be cancelled through their documented route.

## 6. Agent A: shared interface and research workflow

### Exclusive ownership

Agent A owns `components/ui/`, `components/shell/`, `styles/`, `features/projects/`, `features/research/`, and its handoff document. A is the visual consistency owner, not the integration owner. Route and configuration edits are requested from C.

### A1. Project entry and navigation

Build `ProjectsScreen` with project creation, recent projects, an archived filter, pagination, and clear empty/error states. A creation form captures name, optional description, and research question. On confirmed creation, navigate to the project's Research screen. Reopening uses the saved project, not a recreated local session.

Build `ProjectShell` with project title, the current view, navigation to Research, Studio, Runs, and Workspace, a chat toggle, and connection status. Opening a saved report uses its dedicated route. Archive/restore uses C's revision-aware mutation hook.

An unauthenticated state explains that sign-in is needed and offers the configured login entry point. Do not invent a local password flow. If no login entry point has been configured, show a configuration message rather than a nonfunctional sign-in button.

### A2. Research Chat

Build `ResearchChat`, `MessageList`, `MessageItem`, `ChatComposer`, `AttachmentPicker`, and `CitationLink`. Expose `ResearchChat` internally through ProjectShell so other agents do not mount another chat instance.

- Submit text and references to ready artifacts only. Uploading new experimental media happens in Studio.
- Preserve composer text while a submission is unresolved. Clear it only after the server accepts the command.
- Show assistant streaming status and interrupted messages. Never reveal internal tool prompts or hidden reasoning.
- Auto-scroll only while the user is near the end. Otherwise expose a “New activity” affordance.
- The API lists messages oldest-first. Load subsequent pages until the latest persisted history is reached, showing that history is still loading. Do not assume the first 50 messages are the latest 50 or invent a reverse-order query parameter.
- Claims and citations open persisted source/evidence details. Unresolved citation IDs show an unavailable reference, not a made-up bibliographic entry.
- A user may continue sending messages during existing work. Each accepted command keeps its own assistant message and run. Do not concatenate unrelated runs into one status.

### A3. Research Canvas

Build a structured `ResearchScreen` with Research question, Sources, Findings, and Experiment plans sections. Use tabs or section navigation when content grows. Do not implement a draggable infinite canvas.

Source cards show title, authors, publication precision, provider, retrieval status, and a source URL. A details pane shows the retrieved abstract/document link and exact available citation excerpts. “Metadata only” and “Abstract retrieved” are visible qualifications.

Finding cards distinguish observation, inference, and hypothesis. Show assumptions, limitations, and links to measurements or evidence. The experiment summary shows its saved revision, method, protocol, variables, success criteria, and a link to Studio. Full plan editing belongs to B.

Manual reference entry uses the existing source-creation route. Paper discovery and experiment generation use contextual chat prompts rather than invented `/search` or `/plan` routes.

### A's completion evidence

Publish the shared component exports and tokens, then deliver all three public screen/shell exports. Inspect imports, rendering branches, keyboard affordances, empty states, long source titles, streaming status, archive state, and safe Markdown handling through source review. Record files, remaining issues, and any unverified visual claims in `public/docs/handoffs/agent-a.md`.

## 7. Agent B: Experiment Studio and scientific results

### Exclusive ownership

Agent B owns `features/studio/`, `features/results/`, and its handoff document. B consumes A's controls and C's queries/API facade. B does not create a second upload client, query cache, SSE connection, or run-status enum.

### B1. Experiment editing

Build `StudioScreen`, `ExperimentSelector`, `ProtocolEditor`, `VariableEditor`, `CalibrationEditor`, `AnalysisSetup`, and `AnalysisLaunchSummary`.

The editable fields match Experiment creation/PATCH fields. Show hypothesis, method, protocol, independent/dependent/controlled variables, success criteria, attached input artifacts, calibration, and limitations. Show “Unsaved changes” and an explicit Save action. Remote updates do not replace a dirty form. A revision conflict offers the saved and local values for deliberate reconciliation.

Before starting analysis, save the plan, wait for its confirmed revision, and construct the run request from that saved state. Show the input file, selected interval, calibration mode, pipeline, and configured execution limits in the launch summary. For the default bouncing-ball path, use one video, `code_artifact_id: null`, and only the documented parameters.

After a successful `202`, link to the accepted run. Do not wait for execution to finish before allowing the researcher to inspect its progress. Selecting a historical run shows that run's evidence, not a recomputation from the current plan.

### B2. Browser capture

Build `CapturePanel`, `CameraPreview`, `RecordingControls`, and `RecordingReview`. Camera state is local and independent of backend run state:

```text
idle -> requesting_permission -> previewing -> recording -> reviewing
  permission denied/unavailable -> actionable error -> idle or file import
  reviewing -> discard -> idle
  reviewing -> explicit upload -> upload workflow
```

- Camera access starts only when the user presses “Enable camera”. Request video without microphone for the initial MVP.
- Choose a recorder MIME type supported by both the browser and `accepted_mime_types`. If no compatible recorder exists, retain file import as the available path.
- Show preview, Start recording, Stop recording, recording indicator, and elapsed duration. Disable invalid transitions and handle permission revocation/device removal.
- Stop MediaRecorder and every media track on stop, discard, project change, or capture-surface unmount. Review uses the recorded Blob rather than a live camera stream. Re-enabling the camera is a new user action.
- Use a managed object URL for local review and revoke it when replaced or discarded. Never upload because recording stopped.
- Require an explicit “Upload recording” action. Keep the recording available if transfer fails while the page remains open. Explain that leaving/reloading discards an unuploaded recording.
- Apply published duration/size limits locally as an early guard and stop recording when the guard is reached. The backend remains authoritative. Do not promise exact memory limits from a browser-side byte estimate.

### B3. Upload and attach

Build `FileImport`, `UploadProgressView`, and `useArtifactUpload`. Accept supported video and other implemented artifact types, show declared origin, and offer a preview when safe. A user importing synthetic data must be able to label it simulated.

The controller tracks `selected`, `creating`, `transferring`, `finalizing`, `ready`, `failed`, and `cancelled` UI states without confusing them with backend Upload status. Execute create → content PUT → complete through C's facade. Show byte progress only when available, otherwise an indeterminate transfer state.

Only completion returns a usable Artifact. Attach that ID through an experiment save. If transfer succeeds but attachment conflicts, retain the ready artifact and offer to attach it to the refreshed plan. Do not upload it again or label it lost.

Cancellation aborts the transfer. It does not delete a committed artifact or imply the backend has a cancel-upload route. After an ambiguous completion response, inspect the Upload before deciding whether completion needs retrying. An expired upload needs a new upload session. Retransmission uses the same bytes for a restartable PUT.

### B4. Calibration and frame accuracy

The default video analysis works with `calibration.mode: "none"`. It displays pixels and supported dimensionless ratios with explicit assumptions. Physical units are not inferred from camera preview dimensions, nominal frame rate, or a guessed ball size.

The existing contract supports a reference-length calibration but does not provide an exact decoded-video-frame retrieval route. Browser `currentTime` and nominal frame rate do not establish an authoritative zero-based frame index, especially for variable-frame-rate media. This is an integration gap, not a reason to silently change the API.

Implement the calibration-mode UI and schema-aware validation now. For a ready image artifact used in a supported image workflow, reference points use its native decoded dimensions and frame index `0`. When such a workflow is unavailable, keep it hidden. For video, an existing saved reference calibration may be inspected, but interactive point selection remains unavailable until an authoritative frame source is agreed with the backend.

The backend extension proposal is a frame-extraction operation returning a ready still-image artifact plus its originating video ID, exact frame index, decoded timestamp, width, and height. That proposal is **not** a route authorized by the existing contract. Agent C records and coordinates it. Pixel-based video analysis remains the required complete MVP path.

When authoritative frame selection becomes available, B maps pointer coordinates through the displayed image's scale and letterboxing into native pixel coordinates. Do not mirror or crop the calibration image without a reversible mapping. Expose numeric point values, reference length in meters, optional nonnegative uncertainty, and assumptions. Save calibration against the source video/frame, not the transient preview element.

### B5. Results inspection

Build the exported `ResultsPane` with `MeasurementTable`, `SeriesSelector`, `EvidenceViewer`, `UncertaintyDetails`, `ChartGallery`, and `ScientificWarnings`.

- Consume run results, measurement pages, referenced claims, and artifacts from C's hooks. ResultsPane may be mounted in Studio or Execution without opening another stream.
- Group measurements by series and quantity. Display value, unit, time, status, origin, uncertainty, and evidence links. Do not combine unlike units into one unlabeled column.
- Show missing/rejected values as unavailable with their explanation. Unknown uncertainty is “Not estimated”, never zero.
- Label simulated results throughout. Show partial results with the run's failed/cancelled status. Pipeline success alone is not scientific confirmation of a hypothesis.
- Display backend charts and annotated media. Do not invent charts while output is pending or recalculate physical conclusions in the browser.
- Opening evidence uses its artifact, timestamp, frame index, or row index. A normal video seek can be approximate and must not claim exact frame navigation. Exact frame inspection depends on authoritative extracted media.
- Resolve a measurement ID by loading the run's measurement pages when no individual-measurement route exists. Never invent `/measurements/{id}`.
- Provide a path from a measured value to its raw input and provenance manifest. Numerical formatting is presentational and does not change stored precision.

### B's completion evidence

Deliver StudioScreen and ResultsPane, the local capture/upload cleanup paths, saved-revision launch behavior, and the calibration limitation. Inspect every media lifecycle exit, retry branch, evidence link, unit label, and missing-value branch through source review. Record unresolved browser behavior for human review in `public/docs/handoffs/agent-b.md`.

## 8. Agent C: shared integration, execution, workspace, reports

### Exclusive ownership

Agent C owns route/configuration files, `providers/`, `contracts/`, all `lib/` modules, `features/execution/`, `features/workspace/`, `features/reports/`, and its handoff document. C integrates A and B's public components without editing their private feature code during concurrent work.

### C1. Foundation and transport

Create the app skeleton, pin dependencies, establish the API proxy, publish contract types and DTOs, and implement the shared HTTP facade, query keys, hooks, error translation, and project/session providers. Make browser-only boundaries explicit. Imports should fail visibly if a required public interface is missing rather than accepting `any` or a fake server response.

Session/capability resolution precedes protected resources. A session failure closes the event stream, stops mutation retries, clears user-scoped caches, and presents the authentication state. Preserve unsubmitted text in the current component where practical, but do not persist private research data to general browser storage.

### C2. Events and recovery

Implement a fetch-based SSE client behind ProjectRuntime so it can inspect `401`, `410`, and other HTTP failures directly. Parse SSE framing across arbitrary network chunks, including multi-line data and comment heartbeats. Keep a single ordered event application path.

Initial load reads Workspace, loads the visible resource lists, and subscribes after its cursor. Apply resource events by ID and revision. For immutable resources deduplicate by ID. For messages use finalization state and `last_chunk_index`. For resources without revisioned event payloads, apply ordered events and refetch on reconnect rather than guessing version numbers.

- Persist the last applied cursor in runtime memory. Reconnect strictly after it. Do not compare opaque cursor strings numerically or lexically.
- Duplicated known cursors produce no duplicated entities or text. Keep any deduplication window bounded and discard the old window after a full resnapshot.
- A chunk gap fetches the Message and replaces text/index. A finalized message ignores delayed deltas. Ignore a stale message snapshot that would move its finalized state or last chunk index backward.
- Run updates with older revisions do not overwrite newer data. A list refetch must also reconcile against newer cached detail records.
- New source/artifact/claim events update or invalidate the corresponding lists. Measurement-available events refresh measurement/results queries rather than carrying invented rows.
- `410 EVENT_CURSOR_EXPIRED` refreshes Workspace and visible resources, then resumes from the new cursor. A connection failure uses bounded backoff. A permanent failure offers manual reconnect and REST refresh.
- A broken stream shows “Reconnecting” without changing an active run to failed. REST run state remains authoritative.
- Buffer incoming high-frequency chat/log updates for short render batches. Cursor application still preserves ordering. Limit mounted log/message content and use explicit history loading rather than an unbounded DOM.

While disconnected, a bounded REST fallback may refresh active runs and their results. Stop it when events reconnect or no work remains active. It is an application behavior, not an agent monitoring task or automated verification harness.

### C3. Execution and approvals

Build `RunHistory`, `ExecutionScreen`, `RunHeader`, `RunProgress`, `LogViewer`, `RunErrorDetails`, and `ApprovalDialog`. Import ResultsPane from B in the run-detail screen.

Use all seven documented run states. Indeterminate progress stays indeterminate. A visible Cancel action remains pending until the server confirms the result. Terminal runs retain timestamps and code/provenance links. Rerun is an explicit new command with the prior accepted inputs, with plan revision differences reviewed before submission.

Approval UI shows the persisted exact action, its hash-bound identity, known/unknown cost, expiry, and Approve/Reject choices. It never approves automatically or treats a chat message as authorization. A changed/expired/already-decided approval reloads server state. Render pending approvals globally within the project so navigating away from Execution does not hide required user action.

Logs show stream and sequence, use escaped plain text, preserve scroll position, and expose truncation notices. Do not render terminal control sequences as executable content. Fetch older/missed retained logs through the documented endpoint.

### C4. Project Workspace and artifact preview

Build `WorkspaceScreen`, `ArtifactBrowser`, `ArtifactDetails`, and `ArtifactPreview`. Use server metadata and filters, with honest pagination. There is no server-side filename search in this contract. If providing client-side filtering, label it “Filter loaded files” and do not imply it searches unloaded pages.

Preview supported images, video/audio, plain text, Markdown, code, and dataset snippets. Do not load arbitrary large datasets into memory for a browser spreadsheet. Unsupported formats offer metadata and download. Serve HTML/SVG as downloads or inert text according to the backend policy. Do not embed executable arbitrary documents.

Artifact details show kind, origin, size, timestamp, parents, linked run, and hash. If `experiment_id` is null, find experiment association from saved experiment input IDs rather than mutating the immutable artifact. Opening a report navigates to ReportScreen. Original inputs and derived artifacts are visibly distinguishable.

### C5. Reports

Build `ReportComposer` and `ReportScreen`. The composer chooses an experiment, eligible terminal analysis runs, saved source IDs, and a title. It submits `kind: "report"`, `format: "markdown"` through the documented run route.

Eligible failed/cancelled analysis runs can supply clearly labeled partial evidence. The UI explains that report generation success does not mean the underlying experiment succeeded. Do not offer generation until the request has at least one eligible evidence run.

A report link appears only after its artifact is committed. Preview the saved artifact, with safe Markdown, citations, image links, limitations, and provenance. Offer a `.md` download. Do not add unsupported export formats. The browser does not draft a replacement scientific report when backend generation fails.

### C6. Final integration

Mount all public exports, reconcile query/event behavior with feature usage, inspect capability gates, and ensure route selection survives refresh. Ask the owning agent to fix feature-local defects while their session is active. A cross-owner file edit requires an explicit ownership handoff, not silent concurrent editing.

Record implementation versions, API assumptions, exact remaining backend gaps, source-review findings, and unfinished behavior in `public/docs/handoffs/agent-c.md`. C's integrated delivery is complete only when A and B's required exports are connected to live contract data and no placeholder success/results remain.

## 9. Execution order and handoff gates

This sequence allows useful parallel work while protecting shared files.

### Gate 0: choose the application checkout and freeze interfaces

Before feature implementation, open the existing Stellaris frontend root and read its applicable repository instructions, including its bundled Next.js documentation guidance. Give all three agents the supplied product document, this spec, and the companion contract from `public/docs/`.

Agent C extends the existing project skeleton and publishes TypeScript API types, request types, query-hook signatures, runtime context shape, and route imports. Agent A publishes the shared token file, UI export names, and shell interface. Agent B publishes the StudioScreen/ResultsPane entry points and local capture/upload state definitions.

This gate may use empty component bodies that honestly say the feature is not connected yet. It must not use fake papers, measurements, completed runs, API fixtures, mock servers, or a test harness. Temporary incomplete screens are removed from the delivered workflow.

The gate is complete when each agent can implement against stable imports without editing another owner's files. No working backend is required to write the components, but missing backend access remains a delivery limitation rather than evidence of integration success.

### Gate 1: parallel feature delivery

- A implements projects, shell, chat, source/claim inspection, and research summaries.
- B implements plan editing, file selection, capture/review, upload orchestration, launch configuration, and ResultsPane.
- C completes transport, queries, SSE/recovery, execution, artifact browsing, and reports.

Each agent records interface changes before another agent consumes them. A shared dependency change goes through C. A visual primitive change goes through A. B's calibration gap goes through C for backend coordination.

### Gate 2: one complete vertical workflow

Integrate project → chat research → saved experiment → video upload → saved plan → accepted analysis → real results → report → reopen. Finish file upload first if camera compatibility is unresolved, then connect camera recording to the same upload controller. Both paths use the same persisted artifacts and run flow.

Do not expand into new modalities or redesign completed screens while this path is disconnected. Pixel-based measurements and explicit scientific limitations satisfy the first complete camera/video workflow. Unavailable physical calibration stays visibly qualified.

### Gate 3: source review and human handoff

Review the integrated source for contract alignment, ownership boundaries, media cleanup, access/capability handling, sanitization, state honesty, and failure recovery. Inspect changed files and imports. Do not create or run automated tests, fixture data, browser automation, or gameplay checks under the current project instructions.

Provide a concise human review itinerary covering project creation, permission denial, capture review, upload failure, plan conflict, analysis failure/cancellation, reconnect, evidence inspection, and report download. These are human interaction checkpoints, not an automated suite. Do not claim they passed unless a human reports the outcome.

If compilation, dependency installation, or a development-server run has not been performed under the applicable implementation instructions, state that accurately. This planning document does not launch any application.

## 10. Completion requirements for the frontend

All items below describe delivered behavior to establish through source review and subsequent human use. They are not instructions to build automated checks.

- A real project and all five product areas are reachable through one coherent interface.
- Every visible server-backed record comes from a documented resource. There are no fabricated results or hidden mock-mode fallbacks.
- Camera activation and upload are separate explicit user actions. Capture cleanup covers every exit path.
- Analysis consumes a confirmed saved experiment revision and ready input artifacts.
- Run states, progress, logs, partial results, approvals, and errors match server state.
- Event recovery cannot duplicate chat text or overwrite newer run state. A refresh recovers persisted content without event history.
- Sources retain retrieval qualifications. Claims retain observation/inference/hypothesis distinctions.
- Measurements retain units, evidence, origin, uncertainty, and missing/rejected status. Physical scale is not guessed.
- Reports link to committed evidence and download as Markdown. Failed experiment evidence remains labeled accurately.
- Archive state, unsupported features, session expiry, and access errors offer truthful recovery paths.
- Shared styling is consistent, keyboard controls are reachable, and mobile layouts preserve the workflow.
- Agent A, B, and C handoffs identify their files, review evidence, backend blockers, and anything not verified by human interaction.

## 11. Decisions and dependencies still requiring external input

These do not prevent writing most frontend code, but must not be silently invented:

- **Application checkout:** use the existing Stellaris `frontend/` checkout. Confirm that all three agents work against that same checkout and its repository instructions.
- **Authentication:** backend login provider and a real login entry point. Session consumption is already specified.
- **Deployment:** same-origin proxy configuration that preserves cookies, byte ranges, and SSE delivery.
- **Capabilities:** actual MIME support, upload/storage limits, execution budgets, enabled providers, and live backend access.
- **Physical video calibration:** authoritative decoded-frame access and the corresponding agreed contract extension. The existing pixel-based workflow remains usable without it.
- **Model selection:** which available Claude variant fills each Claude slot. File ownership and handoff responsibilities remain unchanged.

If a missing dependency affects a feature, show that limitation and record it in C's handoff. Do not substitute a different backend, silently change the scientific behavior, or represent a locally composed placeholder as completed research.

## 12. Ready-to-assign agent briefs

### Agent A brief — Claude research/interface owner

Read the supplied Stellaris product document, `frontend-backend-contract.md`, this spec, and applicable project instructions. Implement only the shared UI/styles, shell, projects, and research directories assigned to A. Deliver ProjectsScreen, ProjectShell, and ResearchScreen through their named public exports. Own visual consistency, chat, literature/citation inspection, claim distinctions, and experiment summaries. Consume C's shared API/query layer. Coordinate UI exports before B and C consume them. Do not edit routes, dependencies, transport, Studio, ResultsPane, or C's features. Record changes, focused source review, unresolved dependencies, and human review needs in your handoff. Follow the no-automated-tests rule. Do not spawn additional agents.

### Agent B brief — Claude experiment/results owner

Read the same source documents and project instructions. Implement only Studio, capture/review, upload orchestration UI, plan/calibration editing, and results inspection assigned to B. Deliver StudioScreen and ResultsPane. Use A's UI primitives and C's typed transport/query hooks. Preserve explicit recording/upload consent, cleanup, immutable evidence, saved-revision launches, units, uncertainty, missing values, and simulated-data labels. Keep interactive video-frame calibration unavailable until authoritative frame retrieval is agreed. Do not edit shared routes, configuration, dependencies, transport, or another owner's files. Record source review and human review needs in your handoff. Follow the no-automated-tests rule. Do not spawn additional agents.

### Agent C brief — GPT-6.1 Sol integration owner

Read the same source documents and project instructions. Establish the frontend skeleton and shared API types, DTOs, transport, upload-byte transport, resource hooks, query keys, session/capability handling, and the single project SSE runtime. Own routes/configuration/dependencies, Execution, approvals, Workspace, and Reports. Publish the foundation interfaces first so A and B can work independently. Integrate their public exports, coordinate backend gaps, and preserve exact contract semantics. Do not silently modify A/B's private files or invent backend routes/data. Finish with focused source review and a factual integrated handoff, explicitly distinguishing completed code from unverified human interactions. Follow the no-automated-tests rule. Do not spawn additional agents.
