# Workspace implementation plan

Approved November 14, 2026. Canonical UI requirements: Research desk, Materials views,
and Reports specifications in this directory. Preserve the existing design system,
scientific commands, immutable evidence, and working Studio/graph/chat behavior.

## Delivery slices

- [ ] Catalog schema 2: transactional migration, artifact kinds and filtering,
  collection presentation, exact origin lookup, capability gating, preservation checks.
- [ ] Shared frontend contracts, capability fallbacks, cards and evidence inspection.
- [ ] Literature: manual references, explicit PDF extraction, arXiv ingestion,
  structured full-text reader and honest retrieval states.
- [ ] Research desk: Literature, Experiments, Findings, Measurements, Writing widgets.
- [ ] Materials: curated views, URL filters, pagination, collections and deep links.
- [ ] Reports: navigation, library, shared cards, contextual composer, safe reader.
- [ ] Terminal: project-wide bottom panel, ANSI display, replay, sequenced input,
  resize, transcript download and explicit end-session action.
- [ ] Integrated verification and implementation handoff.

## Agreed defaults

- Frontend implementation is authorized. Use Claude Opus for implementation and
  Sonnet for light tasks; this supersedes the earlier Luna preference.
- Closing the terminal panel or navigating does not end the shell. The backend's
  session limits still apply. Terminal files are separate from research/evidence.
- Backend support ships first; `workspace_views` gates richer frontend queries.
- Add paired `origin_type` / `origin_id` exact filtering to the catalog contract
  and existing list endpoint so legacy links need no unrelated page scan.
- Keep HPC disabled. No live paid-model calls without separate authorization.
- Never inspect `.env` files. Browser binaries, tooling and profiles stay in `/tmp`.
- Delegate writers in isolated worktrees, inspect their diffs, verify bounded slices,
  and commit/push incremental results without merging the feature branch.

## Verification

Exercise new and populated schema-1 catalogs, repeat migrations and failure rollback;
preserve content, IDs, timestamps, notes/revisions and user organization. Verify filter
pagination, presentation conflicts and project scoping. Run focused checks and the
frontend build. Use Docker/API checks and isolated WebKit for real integration;
clearly label fixture-based checks and any unavailable live-provider coverage.

## Progress

Implementation started. Verification results will be recorded as slices land.
