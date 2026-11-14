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

## Pending curated-view support (specified November 14, 2026)

Fetched baseline: full-text ingestion, isolated terminal sessions, and optional Slurm support are already integrated according to the [integration record](hpc-research-terminal-plan.md). See the existing [research](../research-contract.md), [terminal](../terminal-contract.md), and [HPC](../hpc-contract.md) contracts. Their recorded local verification is not new verification by this documentation change. HPC remains disabled. Frontend paper ingestion/type/reader work is pending in the public specs and does not require reimplementing those backend services.

These items are **not implemented or verified**. See [file workspace contract section 16](../file-workspace-contract.md#16-proposed-curated-views-extension) for exact wire and migration behavior, and the public [Research desk](../research-workspace-spec.md), [Materials views](../materials-views-spec.md), and [Reports](../reports-spec.md) for observable UI requirements.

- [ ] Add transactional catalog v1 → v2 migration and preserve existing project organization and original evidence identities/dates.
- [ ] Project authoritative artifact kind, backfill existing catalogs, and add repeatable OR kind filters with saved-filter, count, and cursor support.
- [ ] Persist optional collection presentation with existing revision, idempotency, archive, and event behavior.
- [ ] Advertise `features.workspace_views` only with complete extension support. Preserve old client behavior and existing scientific routes.
- [ ] Verify new and migrated catalogs, kind-filter pagination and tag/type distinction, presentation conflicts, events, and extension-disabled fallback through focused Docker/API checks.

The Reports library uses existing artifacts and report runs. Curated-view work does not change the execution backend, project scope, or authentication. The subsequently required agent-led report analysis is recorded separately below. Historical completed checks above do not verify either extension.

## Required agent-led report analysis (November 14, 2026)

Status: **Implemented, locally verified, and accepted by the user.** Live-provider evaluation and narrative-grounding review remain recorded follow-ups, not delivery blockers. Follow the canonical [report-analysis specification](../reports-spec.md#required-agent-led-analysis) and amended [scientific contract](../frontend-backend-contract.md#execution-panel-and-reports). New report runs invoke the project-contained agent. Earlier completed report checks establish historical deterministic behavior only. See [report verification](../verification/report-analysis.md) for the new checks and follow-ups.

- [x] Invoke the configured LangChain Deep Agent inside the owning project container during report generation, using saved evidence and accepted experiment snapshots.
- [x] Require evidence-linked hypothesis evaluation, meaningful run comparisons, contradictions, alternative explanations, and explicit inconclusive outcomes. Rephrasing saved summaries alone is insufficient.
- [x] Separate observations, computed results, and AI interpretations. Retain existing isolation and reproducible calculation code/input/output provenance.
- [x] Record model identity, evidence supplied or read, truncation, limitations, and calculation runs. Preserve immutable evidence, simulation labels, calibration, uncertainty, citations, and historical reports.
- [x] Verify provider-free agent graph/tool transport, evidence scope and references, partial failures, simulation, missing calibration, insufficient evidence, cancellation, persistence, isolated calculation, and provider failure without deterministic fallback.
- [ ] Evaluate live model hypothesis reasoning, contradictory-run interpretation, alternative explanations, and numerical grounding against real evidence after live-provider testing is authorized.


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
