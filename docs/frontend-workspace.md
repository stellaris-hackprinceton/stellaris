# Unified research workspace

The project interface organizes saved work through one Materials catalog. Research, Experiments, Knowledge graph, and Tracker provide working views of that project. The [file workspace contract](file-workspace-contract.md) defines catalog behavior. The [scientific contract](frontend-backend-contract.md) remains authoritative for experiment commands and evidence.

## Navigation and routes

One sidebar contains Research (`/research`), Materials (`/materials`), Experiments (`/studio`), Knowledge graph (`/graph`), and Tracker (`/runs`), relative to `/projects/:project_id`. The frontend `/workspace` page is deleted without a redirect or compatibility alias. Internal artifact links open Materials. The backend `/workspace` API is unchanged.

The header keeps project identity, current view, event connectivity, a chat toggle, and a project actions menu. Archive and Restore stay in that menu. The inset rounded sidebar selection retains its straight blue accent.

## Working views

- **Research** presents the question, literature and findings summaries, saved measurement sets, compact experiment-plan checks, active work, and saved outputs. Sources and findings open a shared material inspector rather than a second set of section tabs. Manual source entry and report creation remain available here.
- **Materials** provides catalog browsing, server-side name search, sorting, tags, collections, previews, notes and their retained revisions, and explicit relations. Secondary filters sit in a compact disclosure with an active-filter summary. Organization is independent of scientific meaning. A note tagged as a hypothesis is still a note, not an evidence-backed scientific claim.
- **Experiments** retains Plan, Inputs, Analysis, and Results as local views of the selected experiment. Recording, upload, calibration, launch, and result inspection continue through the scientific APIs.
- **Knowledge graph** draws files as nodes and explicit directed relations as edges. Recorded provenance and user-created links remain distinguishable. Tags and collections narrow the view. Node selection opens the same material inspector as Materials. Pagination and rendering limits are visible. Missing loaded connections do not establish that no relationship exists.
- **Tracker** shows live work from the workspace snapshot's active run IDs, plus paged history grouped by experiment. Its statuses, progress, errors, and outputs come from saved runs. Unknown progress stays unquantified. Execution completion is not scientific confirmation.

## Shared behavior

Chat is a supporting rail on wide screens and a dismissible sheet on smaller screens. Its empty state offers prompts that populate the composer without sending. Draft text and attachments survive collapse and responsive changes within the current project.

Catalog events invalidate project-scoped catalog views and derived counts through the existing event stream. Catalog writes preserve command identity on retry and use revisions where required. Notes are editable. Artifact bytes and scientific record content remain read-only through Materials. Archived projects remain readable.

Graph links are never inferred or ranked by semantic similarity. Materials does not expose private agent scratch space or give the agent access to notes and tags. A backend without the catalog capability gets an explanatory fallback rather than requests to unsupported catalog routes.

## Verification

Verification results for this implementation are recorded in [Unified workspace verification](verification/unified-workspace.md). Frontend builds, browser checks, Docker/API integration, and model-provider requests are reported separately.
