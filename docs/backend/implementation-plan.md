# Backend implementation status

Scope: the research → experiment → measurement → Markdown-report MVP in `docs/frontend-backend-contract.md`,
with the user-approved no-auth local deployment and Docker topology in `AGENTS.md`.

- [x] API foundation, SQLite project state, idempotency, ETags, dynamic persistent project containers.
- [x] Manual sources, claims, experiment/calibration validation, uploads, immutable artifacts, SSE.
- [x] Isolated per-run workers, input snapshots, bouncing-ball and Python pipelines, output validation.
- [x] Measurements, charts, annotated evidence, logs, provenance, cancellation and restart recovery.
- [x] Evidence-based Markdown reports, source citations, simulated-data labeling.
- [x] Project-container Deep Agents/chat integration with persistent scratch and provider-free graph/transport verification.
- [x] Combined local Docker verification and documentation audit; see [verification.md](verification.md).
- [x] Live Bedrock/Nova verification: cited research, validated plan, simulated-video analysis, and report succeeded in one project.

Verification evidence and commands are summarized in `README.md`; do not infer that a
checked implementation item has received live provider testing.

Still intentionally undecided: what ends a project's duration and permits container teardown.
Archiving retains both the running container and evidence. Authentication is deferred by the
user; remote/public deployment is outside the current local configuration.


## File workspace foundation (2026-11-14)

- [x] Per-project SQLite catalogs and repeatable projection of existing evidence and records.
- [x] File/content listing, filters, stable pagination and default/user tags.
- [x] Editable notes with retained revisions, optimistic concurrency and bounded storage.
- [x] Manual and saved-filter collections, explicit user links and recorded provenance edges.
- [x] Frontend contract, integration examples and Docker/API verification.

Follow [file-workspace-plan.md](file-workspace-plan.md) and the
[file workspace contract](../file-workspace-contract.md). Frontend adoption and graph UI
are separate work. The diagnosed ball-pipeline mismatch is documented in
[experiment-pipeline-mismatch.md](experiment-pipeline-mismatch.md).
