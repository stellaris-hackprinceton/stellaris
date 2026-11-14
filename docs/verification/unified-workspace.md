# Unified workspace verification

Verified November 14, 2026 against the local Compose backend and a separately built production frontend. The synthetic project was **TEST launch selection regression**. No model-provider requests, literature retrieval, new scientific runs, or report generation were performed during this work.

## Build and focused checks

- Production Docker builds completed with TypeScript checking and route generation. The route manifest includes `/materials` and `/graph`, and excludes the deleted frontend `/workspace` page.
- Ten focused transport and upload-type tests passed, including DELETE with ETag/CSRF handling and an empty 204 response.
- Targeted ESLint and TypeScript checks were run for the new catalog, Materials, graph, Research overview, Tracker, shell, and chat integration.
- The running backend initially lacked catalog support. Its implemented catalog image was rebuilt and started after confirming that all existing projects had zero active runs. Project volumes were preserved.

## Connected browser and API checks

An isolated, agent-installed Chromium under `C:/tmp/stellaris-rework/` verified:

- One sidebar with Research, Materials, Experiments, Knowledge graph, and Tracker. The old frontend `/workspace` returns HTTP 404 and has no internal navigation alias.
- Creating a note, saving a new revision, and opening retained revision history. A concurrent server edit produced the expected 412 response while preserving the unsubmitted draft.
- Creating a directed user relation without representing it as scientific provenance.
- Live catalog refresh following collection membership and tag changes.
- UI tag creation and bulk assignment, collection creation and renaming, membership removal, and editing a saved filter.
- A missing `workspace_files` capability yields the artifact fallback in Materials and an explanatory unavailable state in Knowledge graph, without linking to the removed route.
- Graph selection by URL, inspector dismissal, and zoom controls. Chat suggestions populate an unsent draft, which survives rail collapse.
- All five working views fit at 1440, 1024, 768, 390, and 320 CSS pixels without horizontal document/workspace overflow or nested main landmarks.

Browser verification used the production frontend at port 3100. Its test harness forwarded write requests with the backend's configured port-3000 origin. This did not change the backend's origin policy. The normal development service was checked separately because it intermittently returned empty responses during initial compilation.

Final confirmation passed all 25 view/width combinations, keyboard operation of the filter disclosure and graph inspector, and chat draft retention across rail/sheet transitions. The normal port-3000 frontend subsequently rendered Materials successfully.

## Visual review

An independent review inspected all five views at desktop and mobile sizes. Its correction list covered graph label collisions and mobile scaling, the overview's technical-file tiles, stretched readiness content, and the mobile filter stack. The subsequent batch replaced the tiles with research-role summaries, compacted the plan checks, moved secondary Materials filters into a disclosure, and made the graph adapt to its container with selective labels and a text list.

The temporary harness, result files, and captures remain outside Git under `C:/tmp/stellaris-rework/`. Obsolete notes created by failed test attempts were moved to trash with their revisions retained. Original scientific artifacts were untouched.

The independent verdict scored all four visual corrections resolved. Graph edges were additionally shortened to expose their direction arrows outside target nodes.

## Limits

Physical recording, live provider behavior, fresh scientific analysis, and report generation were not re-executed. This is not a complete accessibility audit. The graph renders at most 200 nodes and 200 matching edges and exposes paged loading and filtering. Tracker derives state from persisted runs and does not introduce a separate task/checklist model.
