# Work–energy theorem testing and repair handoff

## Test scope

- Topic: `lets prove the work energy theorem`.
- Exercise research, experiment/feature progression, agent errors, and UI behavior.
- Use isolated WebKit binaries, profiles, tooling, and fresh logs under `/tmp`.
- Capture only new test evidence; do not use historical logs.
- Minimize paid model calls: one initial topic submission, inspect its results before any follow-up, and avoid automatic retries.
- Do not read `.env` files or modify `frontend/` during this investigation.

## Current status

The user resumed Docker and requested a clean recreation after branch merges. Rebuilt all four images and recreated the frontend/API. Removed Stellaris project containers and attempted to remove their volumes; volume cleanup returned an error, so complete deletion of old project volumes is not established. The metadata volume was recreated and the UI started with zero projects. Unrelated containers were left alone.

Tested using freshly downloaded Playwright WebKit under `/tmp/stellaris-webtest/browsers`, with temporary browser profiles under `/tmp`. No frontend edits. No historical logs used. One chat submission triggered a live research run (internal provider calls may be multiple); no retries or follow-up submissions.

Project: `prj_cafbb1cf2d764ef7af724081a5855fcd`.
Run: `run_f34125c6e7ed4fb4bae5ea1e42ef89a0`.

## Confirmed issues

### 1. High: experiment proposal rejected after research

Reproduction:
1. Create project named `Work energy theorem test`, question `lets prove the work energy theorem`.
2. Send: `lets prove the work energy theorem. Find relevant literature and propose a simple experiment. Keep the response concise.`
3. Wait for the research run.

Expected: a valid proposed experiment, or a clear explanation of the supported experiment scope.
Observed: partial assistant response proposes a low-friction air-track test, then run fails after approximately 25 seconds. Run error:

```text
INVALID_AGENT_OUTPUT
Backend rejected the experiment proposal: /calibration/mode: mode must be 'none' or 'reference_length'.
retryable: false
```

Two output artifacts were preserved. No valid experiment was confirmed; downstream execution remains untested. Suspected repair scope: agent experiment tool schema/prompt and backend validator agreement. Inspect the actual submitted proposal before deciding a fix. Preserve validation and scientific honesty; do not silently accept unsupported calibration modes. Check whether this air-track experiment fits the bouncing-ball MVP.

### 2. Medium: approvals request returns 404

During the same research run, the browser requested:

```text
GET /api/v1/projects/prj_cafbb1cf2d764ef7af724081a5855fcd/runs/run_f34125c6e7ed4fb4bae5ea1e42ef89a0/approvals
404 RESOURCE_NOT_FOUND
```

Repeated once through HTTP after run failure: same result. Expected a contract-aligned response or no request for a run without supported approvals. Investigate frontend `lib/api/index.ts:58`, `lib/queries/index.ts:98`, and `providers/project-runtime.tsx`, against backend routes. Root cause is not yet established.

### 3. Medium: research chat hides actionable failure detail

The chat shows `Stellaris’s response was interrupted` and `This response stopped early`, with a `View this run` link. It does not show the calibration rejection in the captured chat. The backend records an explicit validation failure. Expected: distinguish agent/tool validation failure from a generic interrupted response and provide useful next steps. Follow-up testing confirmed the run-detail screen does show the full calibration error. This finding applies to the chat only.

### 4. Medium: artifact preview fails for generated provenance JSON

Confirmed by isolated WebKit and a separate HTTP check. Reproduction: Workspace → click `provenance.json`. The Preview section displays an error instead of JSON:

```text
GET .../artifacts/art_de5271d29aab401bb6a1e7fcbcca3578/content?disposition=inline
400 INVALID_QUERY: This media type can only be downloaded as an attachment.
```

The same artifact with `disposition=attachment` returns 200. A newly uploaded CSV previews successfully. This confirms a file-type-dependent visibility defect, not universal artifact loss. The user independently reported being unable to see artifacts.

Code evidence: `frontend/features/workspace/preview.tsx` selects a text preview for `application/json` and requests `inline`; `backend/api/stellaris_api/media.py` excludes JSON from `INLINE_MIME_TYPES`. Coordinate a safe preview strategy across both sides; do not broadly enable embedding unsafe formats. Acceptance: provenance JSON is readable in Workspace without an error, downloads still work, unsupported types receive a clear fallback, and project-scoped access remains enforced.

### 5. Medium: research source list is dominated by unrelated results

Fresh browser inspection of the test project's Sources tab shows nine retrieved records, including student satisfaction in higher education, Fermi telescope outreach, and LHC particle searches. These do not establish the requested work–energy experiment. The agent itself reported finding only one relevant theory paper. Treat this as a confirmed relevance-quality problem in this run, not proof that retrieved records are fabricated.

Investigate query construction and source selection separately. `backend/project_runtime/agent_runner.py` sends `search_query=all:{query}` and saves retrieved results. Inspect query semantics and whether irrelevant hits should be retained as candidates rather than presented as selected research. No extra retrieval/model requests were made during this follow-up scan. Acceptance: a small recorded retrieval fixture demonstrates that relevant work–energy results are surfaced and rejected candidates are distinguishable.

## Requested feature: file-explorer view for artifacts

User explicitly requested a file-explorer-style view in the artifact zone, alongside the visibility fix. This is a requested enhancement, not a reproduced defect. Implementation is deferred to Opus; no frontend files were changed during testing.

Suggested minimal scope for review:
- Explorer list with file name, type, size, origin, and related experiment/run; preserve current filtering and search.
- Selecting a file opens its preview and metadata, with an obvious download action and selected state.
- Use real backend paths only if exposed. Otherwise group existing artifacts by run/experiment/type; do not invent filesystem folders or imply access to private agent scratch space.
- Clearly distinguish original inputs, simulated data, generated outputs, and provenance.
- Show useful empty, loading, unsupported-preview, and error states; support keyboard selection and a mobile layout.
- Preserve artifact immutability and project scoping. Rename/move/delete operations are outside this minimal request unless separately specified.

## Follow-up scan: verification and limits

No additional model-triggering submissions. All follow-up checks were browser navigation, local CRUD/upload actions, read-only API checks, and source inspection. No `.env` access or frontend edits.

Passed:
- Research question, Sources, Findings, Experiment plans, Studio, Runs, run detail, and Workspace load.
- No page exceptions in the desktop/mobile route scan; no document-level horizontal overflow at 1440×1000 or 390×844. This is not a full visual/accessibility audit.
- Mobile chat opens and closes with Escape.
- Manual experiment creation succeeds. Protocol edits survive reload; attaching an input advances the saved plan revision.
- Manual reference creation succeeds and is marked metadata only.
- Synthetic CSV upload, attachment, and Workspace preview succeed. Origin explicitly set to `simulated`.
- Run results read returns 200; missing artifact read returns 404; provenance download returns 200.

Test fixtures left in the existing test project: experiment `exp_cb3fcc9d5f564baeb37647e37e738f48` (`Manual work energy validation`), one clearly marked manual reference, and `synthetic-work-energy.csv`. These are test fixtures, not measurements.

Additional observation: the run-detail log reports a `moonshotai.kimi-k3.1` model warning about unsupported temperature. This differs from the historical Nova choice in AGENTS.md. Configuration was not inspected; confirm current intended provider/model with the user before changing it. The warning alone is not a demonstrated cause of failure.

Not tested in this follow-up: camera permissions/recording, successful scientific analysis, chart generation, report generation, long-running cancellation, or container restart persistence. No live model retry was used to bypass the proposal failure.

Follow-up evidence directories:
- `/tmp/stellaris-webtest/scan-1794643606825`: route/tab text, desktop/mobile screenshots, layout measurements, page/network errors.
- `/tmp/stellaris-webtest/interactions-1794643654167`: manual creation, reference, JSON preview failure, mobile chat.
- `/tmp/stellaris-webtest/upload-1794643732949`: saved protocol, upload, attachment, CSV preview; no HTTP errors captured.
- `/tmp/stellaris-webtest/api-check-fresh.json`: independent fresh HTTP status checks.
- Reproduction scripts: `/tmp/stellaris-webtest/scan.cjs`, `interactions.cjs`, `upload.cjs`, `api-check.cjs`. These do not submit model requests. `upload.cjs` requires the documented existing experiment and adds another fixture when rerun.

## Fresh evidence

Files are local temporary artifacts, not committed fixtures:
- `/tmp/stellaris-webtest/chat.png`: failed chat screenshot.
- `/tmp/stellaris-webtest/chat.txt`: captured browser text.
- `/tmp/stellaris-webtest/network.log`: fresh API response statuses.
- `/tmp/stellaris-webtest/run.json`: terminal run and error.
- `/tmp/stellaris-webtest/api-fresh.log`: API logs from this test window.
- `/tmp/stellaris-webtest/chat.cjs`: reproduction script (submits a paid run; do not rerun casually).
- `/tmp/stellaris-fresh-build.log` and `/tmp/stellaris-fresh-start.log`: rebuild/start evidence.

No browser page exceptions were captured. The initial pass did not exercise the remaining screens; see the follow-up verification above for expanded coverage and remaining gaps.

## Evidence to collect for each confirmed issue

Record reproduction steps, expected and observed behavior, project/run identifiers, fresh request status and error text, screenshot/log paths, severity, and a suggested repair scope. Separate confirmed observations from suspected causes. Record the number of model-triggering submissions.

## Opus repair instructions

Work from the confirmed reproductions above. Preserve user work and secrets. Keep fixes small and verify the affected flow. Prioritize the proposal rejection, then artifact visibility, the approvals mismatch, and error presentation. Include the requested artifact explorer as a separately reviewable UI change. Avoid additional live model calls until local schema/route checks are complete.

## Repair status after Claude Opus implementation

Opus implemented the fixes and the artifact explorer. Codex reviewed the changes, requested small keyboard/query corrections, rebuilt Docker images and verified the result. See [repair details and verification](docs/agents/work-energy-repairs.md).

Local verification passed: production build/TypeScript, lint, 7 existing frontend HTTP tests, deterministic provider-free agent checks, 95 Docker resource integration checks, approvals HTTP behavior, and isolated desktop/mobile WebKit checks for chat errors, JSON/CSV previews, explorer search/grouping/keyboard navigation. No additional live model calls were made. Live model proposal recovery and search-result relevance still need a later controlled retest; the temperature warning was left unchanged. Historical evidence and source records were preserved.
