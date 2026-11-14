# Work–energy test repairs

Repairs for the confirmed findings in `WORK_ENERGY_TEST_ISSUES.md` (an untracked file, preserved unchanged). Implemented by Claude (Opus) as a bounded task. Claude made the changes without running commands; Codex subsequently verified them locally, as recorded below.

## 1. Experiment proposal rejected (`/calibration/mode`)

The exact proposal the live agent submitted was not captured, so the specific invalid `mode` value is unknown. The cause is established: proposals flowed one way only. The tool returned "sent" to the model, while a backend `ApiError` became a fatal `INVALID_AGENT_OUTPUT` `RunFailure`. The model never received a correctable error.

Changes in `backend/project_runtime/agent_runner.py`:
- `experiment_problems()` reproduces the backend's structural experiment validation (`stellaris_api/experiments.py`). It checks variables, string arrays, unique input IDs, and the exact calibration shape. Problems are returned to the model as a tool error. Nothing is emitted and the run continues. The backend remains authoritative and is unchanged.
- The agent may propose only `{"mode":"none","assumptions":[...]}`. It cannot view frames, so any `reference_length` pixel points or length it supplied would be invented. It must name the reference object in `assumptions`, and the user adds the calibration in Studio. This makes validation stricter. Nothing is coerced.
- `input_artifact_ids` must be IDs the agent was given (request attachments/context artifacts or inputs of existing plans). The check is `known_artifact_ids()`.
- The system prompt and tool docstring state the supported scope: camera/video or uploaded media (the MVP is the bouncing/dropped ball), CSV/text, and isolated Python. They also say that lab equipment such as air tracks or photogates is not available. A work–energy test fits the MVP as a dropped-ball video comparing gravitational work with the gain in kinetic energy.

Backend rejections that remain fatal: only reference/race failures that the runner cannot see, such as an artifact that stopped being ready. These still fail honestly.

## 2. Approvals GET 404

`GET /projects/{p}/runs/{r}/approvals` is now implemented in `backend/api/stellaris_api/runs.py`. It returns the contract's `200 Page<Approval>`. The page is always empty because the MVP has no paid or privileged tool integration and never creates approvals (contract §7). Project and run scoping use `load_visible`/`load_run_row`, so an unknown run still returns 404. Pagination `limit` is validated, and any `cursor` returns `400 INVALID_CURSOR`. The decision route is still not implemented, and no approval machinery was added.

## 3. Chat hides failure detail

When an interrupted assistant message has a run, `frontend/features/research/chat/MessageItem.tsx` loads that run with `useRun`. The detail updates live through the existing `run.updated` cache upsert. The chat shows `error.code` and `error.message`. For `INVALID_AGENT_OUTPUT` it says the backend rejected a proposal and that nothing from the rejected proposal was saved. It suggests revising the request or creating the experiment manually in Studio. For other errors it gives retry guidance based on `retryable`. Cancelled runs say so. Saved partial text is still rendered. If no error is recorded, the previous generic text is shown.

## 4. JSON provenance preview (inline 400)

The backend inline policy is unchanged: `application/json` stays attachment-only, as the contract requires. `frontend/features/workspace/preview.tsx` text previews now fetch with the default `attachment` disposition. The bytes are read with `fetch` and rendered as escaped `<pre>` text or sanitized Markdown, never by the browser itself, so no unsafe embedding was enabled. When the whole JSON file is loaded, it is pretty-printed. Downloads and project scoping are unchanged. Unsupported types show a message that names their MIME type and points to Download.

## 5. arXiv relevance

Cause: `search_query=all:work energy theorem`. arXiv applies the field prefix only to the first word, so the other words matched broadly, which produced unrelated hits. Changes:
- `arxiv_terms()` removes stopwords and conversational request words (for example, "let's prove … find relevant literature"). It keeps quoted and hyphenated phrases and allows at most 6 terms. `build_arxiv_query()` joins them as `all:t1 AND all:"t2 phrase"`. Requests use `sortBy=relevance`.
- Tokens are Unicode letters/digits (no underscore), so terms such as "Schrödinger" stay whole. A token or quoted phrase made only of stopwords (for example `and/or` or `"of the"`) is dropped rather than required.
- `parse_arxiv_entries()` selects a record only when every term appears as a whole word or phrase in its retrieved title or abstract. A trailing plural "s" is accepted, so "theorem" matches "theorems" but "work" does not match "workshop". This is not stemming: other inflections, such as "energies" for "energy", do not match. Other retrieved records become rejected candidates. They are not published as sources, and the model is told not to cite them.
- Every search emits a `retrieval` event `{query, search_query, candidates:[{external_id,title,selected,missing_terms}]}`. `agent_runs.py` validates it, bounds it to 3 per run, writes a summary to the run log, and stores it under `execution_runtime.retrievals` in `agent-provenance.json`. Note: that provenance artifact is written only for successful runs, as before.
- Existing published sources are immutable and were not modified.

## 6. Artifact explorer

`frontend/features/workspace/index.tsx` and `features/execution/sol.module.css`:
- Uses only the existing `GET /artifacts` metadata. It does not invent folders or expose scratch space.
- Groups by origin category (Original inputs, Simulated data, Generated outputs, Provenance and logs) or by run. Each group is a collapsible `<details>`.
- Rows show name, kind, MIME type, human-readable size, and origin. The selected row uses `aria-current`.
- The kind filter (server-side) and the URL `run`/`experiment` filters are preserved. Search covers name, type, and origin of loaded pages and reports when nothing matches.
- Keyboard: Arrow Up/Down, Home, and End move focus among rows in expanded groups only, and Enter/Space selects. Key presses on group summaries are left to the browser, so native collapse works. On narrow screens, selecting a file scrolls to its details.
- Details now include MIME type and category, and the download link has a `download` attribute. Rename, move, and delete are not offered.

## 7. Temperature warning

Not changed. `temperature=0` is passed to both providers. The way to avoid the warning cleanly would be to omit it for specific model IDs, but that would hard-code model-family knowledge and change Nova's deterministic setting. The warning has not been shown to cause a failure. The intended model/provider needs user confirmation first (AGENTS.md lists Nova, but the test log showed `moonshotai.kimi-k3.1`).

## Verification (to be run by Codex; not executed here)

- Offline runner checks: `agent_runtime_test.py` (deterministic, no provider or network). It covers rejected calibration modes and unknown input IDs (no event emitted), an accepted `none` plan, query construction, and an Atom fixture with placeholder IDs. The fixture shows the work–energy record selected and an unrelated record rejected with its missing terms.
- Backend: `python -m py_compile` on the changed modules. Then, with Docker: `GET .../runs/{run}/approvals` → `200 {"items":[],"next_cursor":null}`; an unknown run → 404; `?cursor=x` → 400.
- Frontend: `npm run lint` / `npm run build` in `frontend/`.
- WebKit: Workspace → `agent-provenance.json`/`provenance.json` previews as formatted JSON; download returns 200; CSV upload and preview still work; explorer grouping, search, keyboard navigation, and the mobile layout at 390×844; the chat shows the run error for an interrupted message. The existing failed test run can show this without a new model call.

## Verification observed by Codex

The final reviewed code was rebuilt and started with Docker Compose. All four images built successfully, including the Next production/TypeScript build. The API was restarted to reconcile persistent project containers to the new runtime image without deleting their volumes.

Passed on the final code:
- Deterministic Deep Agents runtime test in a disposable container with no network or provider environment. Includes calibration rejection/recovery inputs, query/token matching fixtures, and scratch/tool flows.
- Existing frontend HTTP tests: 7 passed. ESLint exited successfully.
- Existing Docker resource integration script with `--skip-heartbeat`: 95 checks passed (uploads, resource scoping, persistence behavior, and SSE replay). Two dedicated integration test projects were retained. The idle heartbeat check was explicitly skipped.
- Isolated WebKit at desktop and mobile sizes: actionable failure detail in chat, JSON provenance preview, CSV preview, explorer search, grouping by run, keyboard navigation including collapsed groups, and no document-level mobile overflow. No page exceptions or failed API responses were captured by this final browser script.
- Direct local HTTP: approvals list 200/empty, invalid cursor 400, missing run 404, JSON attachment download 200, JSON inline still correctly refused with 400.
- `git diff --check` passed.

Evidence: `/tmp/stellaris-opus-repairs/` holds build, offline, lint/test, integration and browser logs; final WebKit screenshots and text are under `/tmp/stellaris-webtest/repairs-1794644726678/`.

No new live research/model request was submitted during repairs or verification. End-to-end live proposal recovery and live search relevance remain unverified; offline tests establish local behavior, not live model success. Existing failed-run text and originally saved sources were preserved. The temperature warning remains informational and unchanged.
