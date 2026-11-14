# Reports library and generation specification

Version: **1.1**. Updated November 14, 2026.
Status: **Agent-led analysis implemented with provider-free local verification. Live-provider verification remains pending.** New report runs invoke the configured project-contained Deep Agent. Earlier reports used deterministic assembly and remain readable. Checks and limits are recorded in [report analysis verification](verification/report-analysis.md). The report library and composer implementation is recorded in [workspace implementation](workspace-implementation-plan.md) and [verification](workspace-verification.md).

The user accepted this implementation on November 14, 2026. Narrative grounding,
citation coverage, and live-model evaluation remain [recorded follow-ups](verification/report-analysis.md#recorded-follow-ups).
Additional hallucination guards are not required for this delivery.

Read with the [Research desk](research-workspace-spec.md), [Materials views](materials-views-spec.md), and [scientific contract](frontend-backend-contract.md). This is the canonical specification for agent-led report analysis. The user requires an actual configured LangChain Deep Agent invocation during generation, superseding the earlier exclusion of LLM writing. Existing deterministic reports remain readable and immutable.

## 1. Navigation and page structure

Add **Reports** to the project navigation after Experiments and before Knowledge graph. Its index is `/projects/:project_id/reports`. Existing `/reports/:artifact_id` reader links remain valid. Report-detail pages keep Reports selected in navigation.

The index has a 24px Reports title, one sentence explaining that reports summarize saved evidence, and **Generate report** at the upper right. Use the established research desk tokens, 24px outer padding reduced to 16px on narrow content, and the 240px minimum card grid. Reports are not nested under Sources.

Below the header show report-generation activity when a report run is active, then the saved-report grid. Fetch 24 newest reports and expose Load more. A name search filters report names through the catalog. Optional experiment context is displayed as a chip and preselects the composer. It does not claim to filter the report library because an experiment-filtered catalog query is not added in this version.

An empty library says **No reports saved yet. Generate one from recorded experiment analysis.** Generation may be unavailable while existing reports remain readable. A loading or failed query never displays this empty message.

### Library layout

```text
Reports                                  [+ Generate report]
Reports summarize selected saved evidence.
[Search report names                     ]
[Report generation running · Open run]      <- conditional

[Title            ] [Title            ] [Title            ]
[Saved date       ] [Saved date       ] [Saved date       ]
[Experiment / run ] [Experiment / run ] [Experiment / run ]
[Open] [Download]   [Open] [Download]   [Open] [Download]
                         [Load more]
```

## 2. Report cards and reading

Use the same report card in Writing, the library, and mixed Materials views. Show the artifact's filename as the title. A human report title may replace it only when resolved from the generating report run's recorded input, never extracted heuristically from arbitrary Markdown.

Card content is ordered: title up to three lines, saved date, associated experiment when recorded, Generated report label, and actions. **Open report** navigates to the reader. **Download Markdown** uses the existing artifact-content download URL. A separate **Evidence and provenance** action opens the catalog inspector. Omit an unknown experiment instead of fabricating a project-wide association.

The overview shows two cards and a Generate report tile. It expands to six. The library paginates without that cap. All order by artifact `created_at` and catalog ID descending through the proposed artifact-kind filter. Keep timestamps tied to original creation, not a later catalog sync.

The reader shows title, saved date, experiment link when known, Download Markdown, Evidence and provenance, and Report generation run when `run_id` exists. The document sits in a readable column of at most 78 characters with horizontal scrolling inside wide tables or code blocks. Charts use contain sizing and links to their source artifacts. Small screens stack the action row.

Retain the existing sanitized Markdown renderer, disabled embedded HTML, permitted URL handling, and bounded text preview. If only the first 256 KiB is loaded, show the truncation notice above the document and keep full download available. Raw HTML, embedded scripts, and arbitrary external image loads remain prohibited by the existing preview rules.

Reports are immutable artifacts. Generating another report creates a separate artifact. No Edit report, autosave, draft badge, automatic version chain, or claim that the newest report supersedes older reports appears.

## 3. Composer appearance and inputs

Generate report opens a composer below the page header and above the library. It uses a full-width bordered section with a title, Close action, and form. It is not a side inspector that competes with evidence selection. On narrow screens it remains in document flow.

Form order:

1. Report title, required, single-line input.
2. Experiment, required, existing project experiment picker with pagination.
3. Analysis runs to include, required checkbox list for the chosen experiment. Each row shows execution date, run ID suffix, actual status, and available saved-result summary.
4. Saved literature sources, optional checkbox cards with title and retrieval status, plus pagination.
5. Selection summary with experiment, number of selected analysis runs, number of sources, and **Generate Markdown report**.

Use the existing backend validation: a trimmed title of 1–200 characters, 1–20 unique evidence run IDs, and 0–100 unique source IDs. Show selected counts and prevent adding beyond those limits without clearing existing selections. Terminal analysis runs are eligible, including failed or cancelled runs with partial evidence. Label those rows **Partial evidence · failed** or **Partial evidence · cancelled** and explain that limitations are retained in the report. A terminal run with no measurements is not relabelled successful or hidden as if it never occurred. The backend decides whether the selected evidence is valid.

Changing experiment clears selected evidence runs after confirmation if any are selected. Preserve title and project-scoped source selections. The UI must not submit a previous experiment's runs. No run/source is silently selected by a general entry point.

Contextual entries use `/reports?compose=1&experiment=<id>` and optionally `evidence_run=<id>`. Open the composer and validate supplied IDs against the current project. A run-results shortcut preselects its terminal analysis run only after validation. An active run shortcut explains that it must finish first. Unknown, cross-project, wrong-kind, or mismatched IDs show a local error and do not silently fall back to another experiment. Context is a draft, not automatic submission.

Closing a non-empty composer asks before discarding changed form values. A cancelled close keeps the form. Draft values survive collapse within this mounted page only. Refresh recovery and persistent writing drafts are outside this version.

## 4. Command and execution states

Submission uses the existing run command:

```json
{
  "kind": "report",
  "experiment_id": "<selected experiment>",
  "evidence_run_ids": ["<selected terminal analysis run>"],
  "source_ids": [],
  "title": "<user title>",
  "format": "markdown"
}
```

Send the existing Idempotency-Key. Lock that submitted request body while acceptance is uncertain. A transport retry sends the same body and key. A definitive validation rejection offers Edit request, preserves inputs, and creates a new command identity when the edited request is submitted.

After `202`, show **Report generation accepted** with a link to the committed run and clear the editable composer. This is not a completed report. The activity region renders the run's real state and progress. A returned run with unknown progress has no invented percentage. If it awaits approval, link to the existing approval/run UI.

When a report artifact is committed, shared event invalidation refreshes the library and Writing widget. Show a nonintrusive **Report saved · Open report** notice. Do not force navigation away from a report the researcher is reading. A succeeded run with no resolvable report artifact shows **Report output unavailable** and a run link rather than a fake saved card.

Failed or cancelled report runs remain visible through Tracker and show their error and available outputs. A deliberate Generate again action opens a new draft with the previous recorded selections and requires explicit submission with a new key. Retrying execution is different from retrying uncertain command acceptance.

## 5. Queries, capabilities, and archive behavior

The proposed library queries `/files?artifact_kind=report&sort=created_at&order=desc`, hydrates visible artifact records, and resolves experiment/run labels only when associations exist. Technical filtering comes from artifact kind, never a user reports tag. The Reports list and Writing widget share normalized query keys and detail caches.

Report-generation activity comes from existing runs with `kind=report` and workspace active run IDs. Do not add a second polling system or report-status resource. Use the project's single SSE stream and REST recovery. Generation uses `features.markdown_reports`. Reading existing artifacts does not depend on generation being enabled.

The rich index requires proposed `features.workspace_views`. An older backend retains existing report detail readers and composer entry points until that extension is deployed. The frontend must not send unknown catalog filters and interpret an unfiltered response as reports.

Archived projects allow report reading and downloads but disable generation, with a Restore project explanation. A missing or unsupported artifact displays Report unavailable. Do not open a non-report file merely because its ID appeared in a report URL.

## 6. Report evidence requirements

Keep the existing generator's evidence-backed sections: question, accepted experiment/run inputs, method, calibration assumptions, measurements, uncertainty, claims and citations, charts/media, limitations, code/log/environment references, and provenance. A report's evidence uses the saved run snapshots, not an experiment's current edited protocol.

The current generator includes at most 500 measurement rows in its Markdown table and records omissions. Reading the report must preserve that notice and links to full measurement artifacts/results. The new library does not expand this generator limit or promise that the document contains every row.

Literature metadata-only, abstract-only, full-text, and truncated/partial-extraction qualifications survive into report evidence. Full-text availability alone does not mean the agent read every section or interpreted figures. Preserve saved citation locators and excerpts against the cited immutable Source snapshot. Simulated inputs and measurements remain labelled. Partial/failed evidence remains qualified. Generating Markdown successfully establishes document creation, not confirmation of the experiment or its hypothesis.

Paper-ingestion runs are not analysis evidence choices, and shell sessions/transcripts are not report evidence. Existing Slurm-backed analysis runs, if present, remain analysis evidence under the same terminal-state and experiment checks. Preserve their recorded backend/provenance and simulated-cluster qualifications. HPC stays disabled and no new execution controls are added to the report composer.

### Required agent-led analysis

Each report run invokes the configured LangChain Deep Agent inside the owning project's persistent container. Use the existing provider configuration, report command and lifecycle, and project-scoped evidence. Do not add a browser-side model call or expose credentials.

The existing `kind: "report"` request is unchanged. `features.markdown_reports` now requires locally valid model configuration. Existing artifacts remain readable when generation is unavailable. Configuration presence does not certify model access or a successful provider invocation.

The agent examines accepted experiment snapshots, saved measurements and uncertainty, claims, retrieved source material, warnings, and failures. It assesses whether evidence supports the hypothesis, compares selected runs where meaningful, identifies contradictions and alternative explanations, and states what cannot be concluded. It explains the analysis in readable scientific language with supporting references. A paraphrase of result summaries or a pasted measurement table alone is insufficient.

Keep observations, computed results, and AI interpretations distinguishable. Numerical conclusions reference recorded measurements or reproducible calculations. New calculations use the existing isolated execution tools and retain exact code, inputs, outputs, and provenance. Never invent measurements, physical calibration, statistical significance, or source contents. Evidence insufficient to evaluate a hypothesis produces an explicitly inconclusive interpretation.

Retain exact evidence and technical references alongside the interpretation. Preserve simulation labels, unknown uncertainty, partial failures, calibration assumptions, and literature retrieval qualifications. Record model identity, evidence actually supplied or read, context truncation, analysis limitations, and any calculation runs in report provenance. Provide a concise evidence-linked explanation, not hidden chain-of-thought.

Provider or agent failure fails the report run honestly without silently publishing a deterministic-only substitute as a successful agent-analyzed report. Existing run cancellation, idempotent acceptance, immutable artifacts, and project isolation continue to apply. Historical deterministic reports are not rewritten.

The trusted backend supplies paged evidence through `read_report_evidence` and validates the final assessment, limitations, and record references. Every selected run requires initial reads of its overview, accepted experiment, measurements, claims, and sources. Selected report sources require a separate read. Each page contains at most 40 records and 80,000 serialized bytes within a 1,500,000-byte cumulative context budget. Saved paper text is bounded to 16,000 characters per source. Unread pages, truncated text, and unavailable content become explicit limitations. A record exceeding the page limit cannot be silently omitted.

`calculate_report` accepts Python source and optional selected-evidence data/media artifact IDs. The backend adds a saved JSON evidence dataset and runs a child `script_analysis_v1` execution through the existing isolated worker. At most four calculations are permitted. Calculation snapshots link the requesting report and original evidence without updating the current experiment. Calculation runs publish computed datasets/charts, with no new scientific measurements or claims. They use recorded units without inheriting the first evidence run's camera conversion. The agent has project-isolated per-report scratch and no research, organization, delegation, or native execution tool.

The agent returns a structured assessment (`supported`, `contradicted`, `inconclusive`, or `mixed`), interpretation Markdown, limitations, and referenced record IDs. This is an internal runtime protocol, not a new public API resource. Reports show that interpretation before the recorded evidence appendix. Provenance records the provider/model, runtime image/packages, exact supplied-page hashes and references, calculation runs, and analysis limitations. Incrementally committed run logs retain the audit trail if the API restarts before final artifact publication. Structural validation does not independently verify scientific conclusions.

## 7. Acceptance scenarios

Agent-analysis acceptance scenarios are below. See the [verification record](verification/report-analysis.md) for checks actually run and remaining live-model evaluation:

- A report generation invokes the configured LangChain Deep Agent and records model identity and supplied evidence in provenance.
- Given recorded results and a hypothesis, the report explains how evidence supports, contradicts, or leaves the hypothesis inconclusive and cites the relevant records.
- Contradictory selected runs are discussed with their differences and limitations rather than silently averaged or selectively omitted.
- Failed/cancelled evidence and missing measurements remain qualified. Simulated evidence is never described as a physical observation.
- Missing calibration retains pixel/native units. Unknown uncertainty is not zero and insufficient evidence does not become a confident conclusion.
- New numerical calculations have retained execution code, inputs, outputs, and provenance. Values copied from measurements reference those records.
- Provider failure and cancellation cannot publish a successful template-only replacement. Previously saved deterministic reports remain readable.

Library and composer acceptance scenarios:

- Opening Reports with no saved artifact explains generation prerequisites and offers a usable composer when permitted.
- More than 24 reports paginate newest first across the whole project, without duplicates or reordering caused by catalog synchronization.
- A run-context entry preselects exactly the validated experiment/run, with no automatic command. Switching experiment cannot submit old selections.
- A failed terminal analysis run can be selected as partial evidence. Generation and the resulting report retain its limitations.
- Disconnect during submit: the same command is retried without duplicate run creation. Definitive rejection allows editing the retained draft.
- Accepted, active, failed, cancelled, saved, and missing-output states have distinct labels. Event reconnection refreshes from persisted truth.
- Archived projects and generation-disabled backends still permit supported report reading/downloads.
- Keyboard users can open, compose, choose evidence, cancel, read, and download at narrow widths and 200% zoom. No application or live-provider verification is claimed by writing this document.
