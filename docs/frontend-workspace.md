# Unified research workspace

The [experiment studio design](design/experiment-studio.md) defines the current visual system and labels. Research is now Overview, Materials is Library, Knowledge graph is Connections, Tracker is Activity, and Research chat is Assistant. Existing route and resource identifiers remain unchanged.

The approved [experiment studio design](design/experiment-studio.md) supersedes the historical visual desk layout. It defines flat content sections, one primary navigation, and a compact Library toolbar. Current checks are recorded in [experiment studio verification](verification/experiment-studio.md).

The project interface organizes saved work through one Library catalog. Overview, Experiments, Reports, Connections, and Activity provide working views of that project. The [file workspace contract](file-workspace-contract.md) defines catalog behavior. The [scientific contract](frontend-backend-contract.md) remains authoritative for experiment commands and evidence.

## Card interface and capability support

The public [Research desk specification](research-workspace-spec.md), [Materials views specification](materials-views-spec.md), and [Reports specification](reports-spec.md) describe the card interface and its requirements. The [visual desk direction](design/virtual-desk.md) supersedes their earlier layout dimensions. The remaining sections record behavior and historical context. Verification remains separate from these requirements.

Overview separates Sources, Experiments, Results, Findings, and Reports into full-width sections. Recent cards, bounded expansion, and labelled add tiles replace the combined text panel. Experiments remain plural and open independent Studio contexts. Materials defaults to cards even on the foundation catalog, with a list option. Curated presentations and saved presentation metadata require the backend extension. Reports has its own destination and index. The desk supports these activities in any order.

Backend prerequisites are proposed in [file workspace contract section 16](file-workspace-contract.md#16-proposed-curated-views-extension). No richer view may infer scientific types from user tags or send unsupported kind filters to an older backend. The specs describe pending work, while [Unified workspace verification](verification/unified-workspace.md) remains evidence for the existing implementation only.

The fetched [research extension](research-contract.md) already supports full-text PDF/arXiv ingestion. The proposed Literature UI exposes it with extraction states and a source-linked reader. [Terminal sessions](terminal-contract.md) use separate scratch storage and do not become catalog evidence. [HPC](hpc-contract.md) remains disabled and does not add a widget or new navigation destination in this design.

## Navigation and routes

One sidebar contains Overview (`/research`), Library (`/materials`), Experiments (`/studio`), Reports (`/reports`), Connections (`/graph`), and Activity (`/runs`), relative to `/projects/:project_id`. The frontend `/workspace` page is deleted without a redirect or compatibility alias. Internal artifact links open Materials. The backend `/workspace` API is unchanged.

The utility header keeps project identity, event connectivity, Assistant and Terminal toggles, and project actions. Pages own their destination heading. Archive and Restore stay in the project menu. The aluminum sidebar uses violet selection and a short brand rule.

## Working views

- **Research** presents the question, literature and findings summaries, saved measurement sets, compact experiment-plan checks, active work, and saved outputs. Sources and findings open a shared material inspector rather than a second set of section tabs. Manual source entry and report creation remain available here.
- **Materials** provides catalog browsing, server-side name search, sorting, tags, collections, previews, notes and their retained revisions, and explicit relations. Secondary filters sit in a compact disclosure with an active-filter summary. Organization is independent of scientific meaning. A note tagged as a hypothesis is still a note, not an evidence-backed scientific claim.
- **Experiments** retains Plan, Inputs, Analysis, and Results as local views of the selected experiment. Recording, upload, calibration, launch, and result inspection continue through the scientific APIs.
- **Knowledge graph** draws files as nodes and explicit directed relations as edges. Recorded provenance and user-created links remain distinguishable. Tags and collections narrow the view. Node selection opens the same material inspector as Materials. Pagination and rendering limits are visible. Missing loaded connections do not establish that no relationship exists.
- **Tracker** shows live work from the workspace snapshot's active run IDs, plus paged history grouped by experiment. Its statuses, progress, errors, and outputs come from saved runs. Unknown progress stays unquantified. Execution completion is not scientific confirmation.

## Shared behavior

Assistant is a supporting rail from 1360px and a dismissible sheet on smaller screens. Its empty state offers prompts that populate the composer without sending. Draft text and attachments survive collapse and responsive changes within the current project.

Catalog events invalidate project-scoped catalog views and derived counts through the existing event stream. Catalog writes preserve command identity on retry and use revisions where required. Notes are editable. Artifact bytes and scientific record content remain read-only through Materials. Archived projects remain readable.

Graph links are never inferred or ranked by semantic similarity. Materials does not expose private agent scratch space or give the agent access to notes and tags. A backend without the catalog capability gets an explanatory fallback rather than requests to unsupported catalog routes.

## Verification

Verification results for this implementation are recorded in [Unified workspace verification](verification/unified-workspace.md). Frontend builds, browser checks, Docker/API integration, and model-provider requests are reported separately.
