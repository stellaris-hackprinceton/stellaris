# Backend implementation status

Scope: the research → experiment → measurement → Markdown-report MVP in `Contracts.md`,
with the user-approved no-auth local deployment and Docker topology in `AGENTS.md`.

- [x] API foundation, SQLite project state, idempotency, ETags, dynamic persistent project containers.
- [x] Manual sources, claims, experiment/calibration validation, uploads, immutable artifacts, SSE.
- [x] Isolated per-run workers, input snapshots, bouncing-ball and Python pipelines, output validation.
- [x] Measurements, charts, annotated evidence, logs, provenance, cancellation and restart recovery.
- [x] Evidence-based Markdown reports, source citations, simulated-data labeling.
- [x] Project-container Deep Agents/chat integration with persistent scratch and provider-free graph/transport verification.
- [x] Combined local Docker verification and documentation audit; see VERIFICATION.md.
- [ ] Live Bedrock/Nova model testing after the user supplies API configuration (explicitly deferred).

Verification evidence and commands are summarized in `README.md`; do not infer that a
checked implementation item has received live provider testing.

Still intentionally undecided: what ends a project's duration and permits container teardown.
Archiving retains both the running container and evidence. Authentication is deferred by the
user; remote/public deployment is outside the current local configuration.
