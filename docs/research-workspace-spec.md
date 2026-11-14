# Research desk and widget specification

Version: **1.0 proposed**. Prepared November 14, 2026.
Status: **Specified, not implemented or verified.** This document describes the next interface, not the current screenshot or a completed feature.

This is the public implementation specification for the project's Research overview. Read it with [Materials views](materials-views-spec.md), [Reports](reports-spec.md), and the [file workspace contract](file-workspace-contract.md#16-proposed-curated-views-extension). The scientific contract remains authoritative for evidence and commands.

## 1. Research model and current baseline

The researcher can collect literature, write notes, design several experiments, inspect results, and generate reports in any order. The overview is a desk for continuing work, not a wizard or a required sequence. A question is optional until a command needs it.

The current `frontend/features/research/canvas/ResearchScreen.tsx` combines literature, findings, measurements, and a report into one text-heavy panel. It selects one experiment for a neighboring checklist. Multiple experiments already exist in the data model. This specification changes their visibility and presentation, not their scientific identity.

Content has distinct roles:

- Literature is external reference material. Retrieval status describes what was actually obtained.
- Recordings, images, and datasets are materials. Their recorded origin determines whether they are observed, derived, simulated, generated, or reference material.
- Findings are persisted `Claim` records with evidence and qualifications. Notes do not become claims by receiving a tag.
- Measurements are saved numerical records associated with an experiment and run. Charts are immutable artifacts representing saved analysis.
- Reports communicate selected evidence. They are outputs, not literature sources.

References stay inside the current project. Cross-project knowledge, human taskboards, catalog-wide full-text search, custom widget builders, and interactive cross-run plotting are outside this version. The backend's per-paper agent reading/search tools are distinct from catalog search. The fetched [research extension](research-contract.md) already implements ingestion. Its frontend integration below remains proposed.

## 2. Page composition and appearance

Use existing CSS tokens from `frontend/styles/tokens.css`: system font, 24px page title, 20px widget titles, 16px body, 14px metadata, white surfaces, gray borders, blue actions, and 2px panel/control radii. No new decorative palette, gradients, oversized headings, or charts invented for empty states.

The main content fills its available column up to 1440px. Use 24px outer padding, reduced to 16px below 800px of content width. A 12-column grid has 16px gutters. The breakpoint is the width available to the research content after navigation and Chat, not the browser viewport.

- At 800px or wider, Literature and Experiments each span six columns. Findings and Measurements each span six columns on the next row. Writing spans twelve columns.
- Below 800px, all widgets span twelve columns in that same reading order. The grid never has horizontal overflow.
- Cards use `repeat(auto-fit, minmax(min(240px, 100%), 1fr))` with 12px gaps. At narrow widget widths this naturally becomes a vertical stack.
- Panels have 16px padding, a 1px border, and natural height. Grid items align to the start. Short panels do not stretch to match a neighbor.
- Card padding is 12px. Titles use 16px semibold. Metadata uses 14px muted text. Title truncation is three lines and prose previews are three lines. The inspector exposes complete text.
- Charts and images use `object-fit: contain`. Preview media has a maximum height of 200px on the desk and never crops axes, units, or annotations. Expanding or opening Results provides a larger view.
- Controls have a minimum 40px height. Large add tiles have a minimum 112px height, a 32px plus icon, and a visible action label. They follow real cards in reading order.

Above the grid, show the Research title and project description, then a compact question region. An unset question displays “What are you investigating?” and an Edit action. Editing uses the existing project revision behavior. Do not create a full-height question panel.

The active-work strip follows the question. Hide it when no runs are active and no failure has been selected for inspection. Show up to three active run summaries, their actual states, meaningful progress messages, and links to run details. “View active runs” opens Tracker. Unknown progress has no percentage. This strip does not invent researcher tasks or scientific blockers.

Handle all current run kinds explicitly: agent → Research, analysis → Analysis, report → Report generation, and paper_ingest → Paper ingestion. Tracker, run details, overview summaries, and rerun controls must not classify an unrecognized run as a report. Terminal shell sessions are separate resources, not runs or scientific evidence.

### Annotated layouts

Populated desk at wide content width:

```text
Research                                      [Chat]
Project description
Question: How does bounce height change?       [Edit]
[Analysis running · tracking frames · Open run]   <- conditional strip

+ Literature ----------------+ + Experiments ----------------+
| recent source cards        | | recent experiment cards     |
| [+ Add source]             | | [+ New experiment]          |
| Expand / View all          | | Expand / View all           |
+----------------------------+ +-----------------------------+
+ Findings ------------------+ + Measurements and results ---+
| statement + evidence links | | saved chart, values, units  |
| qualifications             | | origin, calibration, warning|
+----------------------------+ +-----------------------------+
+ Writing ---------------------------------------------------+
| report card | report card | [+ Generate report]              |
+------------------------------------------------------------+
```

Empty desk retains the same headings but replaces each content area with one short explanation and its relevant action. Literature has the Add source tile. Experiments has the New experiment tile. Findings says “Findings appear when research or analysis saves a claim.” Measurements says “Analyze an experiment to save measurements.” Writing says “Generate a report from recorded analysis.” No empty chart axes, dummy cards, or unavailable numeric zeros appear.

Expanded widgets grow in normal document flow, pushing later content down. They do not become modal dashboards. On a narrow screen, the page reads Question → active work → Literature → Experiments → Findings → Measurements → Writing. Chat and inspectors use sheets rather than adding cramped columns.

## 3. Shared widget behavior

Each widget is a labelled section with heading, optional authoritative count, contextual action, preview content, and footer. A count derived from loaded pages is labelled “N loaded” or “More available”, never presented as a total. Do not fetch every page just to produce a count.

The footer separates **Expand** from **View all**. Expand reveals the bounded preview described below. Collapse returns to the preview limit and keeps focus on the disclosure. View all navigates to a full view. Hide Expand when there are no further preview items. Pagination failure keeps loaded cards visible with a local Retry action.

Disclosure state is local to the overview and lasts while the project shell is mounted. It is not saved as collection metadata. The card order is stable by the specified timestamp and ID in descending order. New event data can insert a new card but must not steal keyboard focus.

Card titles are links or inspector buttons. Secondary controls are separate siblings, never nested interactive elements. Hover changes the border to the accent color. Focus uses the existing 2px outline. Selected cards use the existing selection surface. Status labels include words, not color alone.

Initial loading uses neutral skeletons at the expected card size. An error is not an empty state. Errors, unsupported capabilities, and missing linked records have separate messages. A failed image leaves the title, metadata, and Open action usable. Archived projects remain readable with creation actions disabled and “Restore project to add or generate material.”

## 4. Literature widget

Heading: **Literature**. Default: three source cards ordered by project `created_at` descending, followed by **+ Add source**. Expanded limit: nine source cards plus the tile. Footer View all opens Materials with `view=literature`.

A source card contains, in order:

1. Three-line title, opening the material inspector.
2. First two authors and “et al.” when needed, then publication year if provided. Omit absent metadata rather than guessing.
3. Up to three lines of the saved abstract. If absent, “No abstract saved.”
4. Retrieval label: Metadata only, Abstract retrieved, Full text retrieved, or Retrieval failed. The label follows `retrieval_status`, not the presence of user-entered abstract text.
5. Added date and provider. The inspector exposes retrieval date, source URL, DOI, full author list, complete abstract, and retrieved document if present.

Add source opens a small action menu: **Add reference**, **Upload PDF**, and **Retrieve arXiv full text**. Add reference uses the existing manual-entry form. The latter two appear only with `features.full_text_papers` and are independent of the proposed catalog-view capability. A secondary **Find literature in Chat** action opens Chat with an editable prompt, without sending it. Discovery remains arXiv-based. Full-text ingestion from arXiv or uploaded PDFs is implemented in the backend, while its controls and reader described here are pending. Do not imply that every paper has retrievable or completely extracted full text.

Upload PDF opens a file selection and metadata form. Transfer through the existing upload create/transfer/complete flow using `application/pdf`, kind document, and reference origin. Respect advertised upload limits and the ingestion ceiling of 50 MiB, whichever is smaller. Only after upload completion, an explicit **Extract paper** action submits `POST /runs` with `{kind:"paper_ingest",document:{artifact_id}}` and optional uploaded-document metadata supported by the research contract. Upload alone does not create a Source or prove successful extraction. Retrieve arXiv full text asks for an arXiv ID and explicitly submits the same run kind with `document:{arxiv_id}`. Arbitrary URL retrieval is not introduced.

Show the returned run's actual status, phase, progress message, cancellation action, and run-details link. Retrying uncertain acceptance reuses the identical body and Idempotency-Key. After a definitive failed/cancelled extraction, **Try extraction again** opens a reviewed new request with a new key. A completed upload can be reused without uploading its bytes again. Failed extraction does not create a full-text source card. Original uploaded documents remain accessible in All materials. When publication succeeds, refresh the Literature query and offer **Open extracted paper** for the new immutable Source. Earlier source snapshots and citations stay unchanged.

Full-text source cards retain the retrieval badge and add **Partial extraction** when `full_text.truncated` is true. The inspector exposes format, section/page counts when known, extraction warnings, license URL when recorded, ingestion run, original document download, and extracted-paper reader. `full_text.text_artifact_id` identifies structured `paper.json`, not the flat `paper.txt` artifact. Render its sections/paragraphs as escaped text with stable locator anchors and a section list. Resolve the flat-text download through the ingestion run's output artifacts. Preserve missing outputs as unavailable instead of guessing IDs or paths. Original PDFs and source archives download as attachments, with no new inline PDF renderer.

A citation opens its saved locator in the extracted reader when available, displaying the recorded excerpt and source snapshot. Preserve truncation and extraction notes. Extraction is best-effort, has no OCR, and does not establish that figures or the whole paper were read. The agent's bounded inline `request_full_text` tool is a separate backend path and still produces recorded ingestion runs. Do not duplicate it by automatically submitting a browser request when Chat requests a paper.

## 5. Experiments widget

Heading: **Experiments**, always plural. Default: three experiment cards ordered by `updated_at` descending, then **+ New experiment**. Expanded limit: nine. View all opens the existing Experiments destination. It must expose all plans through its selector and pagination.

Each card shows title, method, two-line hypothesis excerpt or “Hypothesis not recorded”, saved revision, attached input count, last saved date, and one next-action link. A separate status line can describe the most recent known run with its execution date. Do not present a selected old run as the latest if history has not been resolved.

Choose the next action in this order: missing hypothesis → **Define hypothesis**, missing protocol → **Write protocol**, no attached inputs → **Add inputs**, otherwise → **Review experiment**. Each opens Studio with the experiment ID. These are helpful prompts, not backend readiness certification. Calibration requirements and launch validation remain in Studio.

The card never contains the full protocol, variable editor, calibration controls, or launch form. Opening one experiment does not hide other experiments on the desk. New experiment opens Studio's creation flow. It does not silently create an empty scientific record on tile click.

## 6. Findings widget

Heading: **Findings**. Default: three persisted claims by `created_at` descending. Expanded limit: six. View all opens `view=findings`. No generic Add finding tile is shown because this version has no manual claim-creation UI.

Each card shows the recorded kind, three lines of `text`, citation count, measurement-reference count, and saved date. A hypothesis label reads **Hypothesis · proposed**. Show the first recorded limitation directly below the statement, truncated to two lines, with “More qualifications” opening the inspector. Missing limitations are not replaced with “No limitations.”

Expand a card's evidence disclosure to show citations with locators, measurement links, artifact/frame/time references, assumptions, and all limitations. Unresolved references remain visible as unavailable links with an explanation. Their absence never becomes evidence against the claim.

An evidence image can appear only through an explicit evidence reference. A chart associated with the claim's run can appear in expanded content under **Related run output**. This association alone must not be labelled supporting proof. Do not infer confidence, agreement, importance, or scientific confirmation from execution state.

## 7. Measurements and results widget

Heading: **Measurements and results**. Default: the most recently created analysis run with a projected measurement set. Resolve `origin_type=run_measurements` descending, then hydrate that run and `RunResults`. Do not pick an unrelated latest chart and use its run as the project's latest measurement set.

The preview contains experiment title, run execution date and status, first saved chart in `chart_artifact_ids` order, and the first three measurement rows in API order. Label the rows **Sample of saved measurements**. Each row includes quantity, value or Missing/Rejected, unit, and uncertainty where recorded. Do not imply that these samples are aggregate statistics or the latest values of every series.

Show each sample's origin and calibration. Unknown uncertainty reads “Uncertainty not recorded.” Mixed origins or calibration modes remain per-row labels. Saved warnings appear below the preview, with the first two visible and a labelled disclosure for the remainder.

Expanded content shows all saved chart and annotated-media references, loading media only when visible, plus ten sample measurement rows. More measurements remain accessible through **Inspect this run's results**. View all opens Materials `view=measurements`. Do not combine runs, interpolate samples, fit trends, or recalculate physics in this widget.

If a measurement set has no chart, show the rows and “No saved chart for this run.” A run with no saved measurements is accessible in Tracker and its results page, but does not displace an older actual measurement set here. Failed and cancelled runs with persisted measurements remain eligible and visibly qualified.

## 8. Writing widget

Heading: **Writing**. Show two latest saved report cards followed by **+ Generate report**. Expand to six. View all opens Reports. Report card anatomy and generation rules are defined in [Reports](reports-spec.md), not duplicated here.

Report generation availability follows capabilities, project state, and eligible evidence. An empty or unavailable composer explains the missing prerequisite without preventing reading existing reports.

## 9. Data flow and implementation interfaces

Use the project query cache, one existing project SSE stream, and current scientific APIs. Widget composition is frontend code. No widget registry endpoint or second server-state store is introduced.

- Literature: `/files?origin_type=source&sort=created_at&order=desc`, then authoritative source detail for visible IDs.
- Experiments: `/files?origin_type=experiment&sort=updated_at&order=desc`, then experiment detail. Catalog projection carries current experiment revisions. Active execution still comes from workspace/run resources.
- Findings: `/files?origin_type=claim&sort=created_at&order=desc`, then claim detail.
- Measurements: `/files?origin_type=run_measurements&sort=created_at&order=desc`, then run, run results, and measurement pages.
- Writing: `/files?artifact_kind=report&sort=created_at&order=desc`, then artifact detail. This filter is proposed and capability-gated.

Use catalog file IDs as presentation identity and origin IDs for scientific reads. The first collapsed fetch requests only its preview limit plus one to detect expansion. Expansion restarts or extends the same ordered query to its maximum. If a hydration fails, preserve that card's place and allow a local retry. Do not hide failures by filling the slot with a different record.

Extend client types to match the existing research extension: Source's optional/null `full_text`, capabilities' `full_text_papers`, and the `paper_ingest` request/run-input variant. Accepted run input can contain backend-added fields such as `requested_by_run_id`. Construct a new ingestion command from permitted request fields instead of blindly resubmitting the entire accepted run input. Render source and artifact publication through the existing project event stream.

Query keys include project, resource, normalized filters, sort, and order. Reuse existing detail keys for hydration. On `catalog.changed`, invalidate catalog lists, collections, and affected detail previews. Scientific resource events also invalidate the corresponding scientific details. Reconcile newer revisions using the existing query layer. On reconnect, use its existing REST recovery rather than assuming replay delivered everything.

Full previews require the proposed `features.workspace_views` extension. An older backend retains its existing working interface with an explicit richer-views-unavailable message. Never send unsupported filters that an older backend could ignore.

Selecting a source or finding opens the shared inspector while preserving overview context. At 1100px available content width, use a 360px side inspector and a remaining content column of at least 640px. Below that, use a sheet. Closing restores focus to the card. Experiment and run-result actions navigate to their working routes instead of rendering editors in the overview.

## 10. Acceptance scenarios

- Empty project: all five widget headings remain understandable, add actions are visible, and no missing result is shown as zero.
- One then twelve experiments: no singular project-plan assumption, all plans are reachable, and cards open the right experiment across pagination.
- Twelve sources: first three and expanded nine are genuinely newest across the entire project. Publication date does not affect added order.
- A failed source retrieval, a missing linked claim, and one failed preview request show distinct local failures without blanking the desk.
- PDF upload and extraction have separate outcomes. No-text-layer, malformed, cancelled, and truncated extraction cases retain honest status. Successful publication opens the exact new Source with working paragraph locators and original/extracted downloads. Ingestion activity is never labelled Report.
- A claim with only citations has no invented chart. A same-run chart is explicitly related output.
- Simulated, uncalibrated, missing, and rejected measurements keep their qualifications. A newer chart-only run does not replace the latest saved measurement set.
- Active runs finish while the desk is open: statuses and relevant widgets refresh once through shared cache invalidation, without duplicate cards or focus movement.
- At 200% zoom and with Chat open, widgets stack before controls or scientific previews become clipped. Keyboard users can add, inspect, expand, collapse, and return to the same card.

Implementation evidence belongs in a new dated verification record after code changes. This specification itself is not verification evidence.
