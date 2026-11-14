# Backend verification — 2026-11-14

The backend is built and running locally through `backend/compose.yaml`. No frontend files
were modified. No agent read or printed `.env`; Docker/the application loads configuration
at runtime. Model credentials are excluded from worker containers and public responses.

Verified against the Docker implementation:

- Foundation smoke: **44 checks passed**, including real container creation, volume/network
  isolation, idempotency, revisions, restarts, and image reconciliation.
- Resource/upload/SSE integration: **96 checks passed**, including actual media validation,
  immutable storage, range downloads, reference ownership, event replay, and heartbeats.
- Scientific workflow: **90 checks passed**, including fixture-ground-truth measurements,
  calibration, charts/annotated frames, reports, Python-worker isolation, invalid-output
  rejection, cancellation, and `WORKER_LOST` recovery.
- Provider-free Deep Agents integration: **6 checks passed**. A real Deep Agents graph with
  an injected test-only model calls tools and writes/reads persistent scratch. Docker stdin
  transport and selected-provider credential isolation passed. The production-configured
  API was deliberately not sent a fake missing-credentials request.
- Isolated missing-credentials API test: passed without network, credentials, or Docker
  socket, including idempotency, honest failure, persistent interrupted messages, and SSE order.
- Focused worker-output validation, audit quota/cancellation cleanup, and agent recovery
  regressions passed. A matching test process that ignores TERM is killed within the grace
  period; its run-specific temporary files are removed.
- Public arXiv retrieval returned three actual abstract-only source proposals without a model.
- `ChatBedrockConverse` constructed with dummy credentials in a network-disabled container.
  This verifies SDK construction, not real IAM/model access.

## Scientific data checks

The explicitly simulated fixture produced six apexes and five ratios. First apex:
280.0004 px versus 280 px truth; mean height ratio: 0.63998 versus 0.64 truth. Simulated
origin remains visible through measurements and generated reports.

A separate real recorded [SERC tennis-ball clip](https://serc.carleton.edu/microbelife/teaching/teachingwdata/video.html)
(Peter Bohacek, CC BY-NC-SA 3.0) produced 55/62 accepted detections and one valid apex at
388.974 px. It correctly retained `INSUFFICIENT_EVIDENCE` for a ratio: only one acceptable
complete flight was available. A partial-evidence Markdown report preserved its failure,
measurements, limitations, attribution, and source link. The chart and annotated frame
were inspected. The source video and test outputs remain outside Git under `/tmp`.

## Live Bedrock/Nova verification

Live Nova 2 Lite verification passed through the backend using runtime configuration:
a real response and validated experiment tool call, then cited arXiv research with a
persisted hypothesis, simulated-video analysis, and an evidence-grounded Markdown report
in the same project. The research run retained its log and provenance artifacts. Model
tool enums and JSON-array validation were tightened after the first live attempts; bad
proposal shapes now return useful tool feedback rather than escaping as internal errors.

No agent opened `.env` or printed credential values. Frontend files were unchanged.
Reproduction commands are in `README.md`. Local logs remain under `/tmp/stellaris-claude/`;
they are not committed. Test projects remain available because no destructive project-ending
policy has been approved.


## File workspace foundation — 2026-11-14

Observed against rebuilt API and project-runtime images, with the existing volumes preserved:

- `workspace_files_test.py --slice 1`: **76 checks passed** (backfill, deterministic IDs,
  original downloads/ranges, rendered records/measurements, filters, paging and project scope).
- `workspace_files_test.py --slice 2`: **112 checks passed** (notes, revisions, ETags,
  no-ops, Unicode validation, user tags, atomic bulk operations, events and archive rules).
- `workspace_collections_test.py`: **86 checks passed** (manual/saved collections,
  filter intersections, user links, exact recorded system edges, limits and protected provenance).
- `integration_test.py --skip-heartbeat`: **95 existing checks passed**. Only the idle
  heartbeat-delay check was skipped; upload and event replay checks ran.
- Catalog metadata survived an API restart unchanged. A separate invalid SQLite fixture
  returned 503 and was preserved byte-for-byte, then explicitly removed only in that test project.
- An isolated 5-byte note budget rejected a revision with 413 and preserved content/history.
- A validated synthetic citation projected exactly one `cites` relation without a model.
- The offline, network-disabled `agent_runtime_test.py` passed. Public capabilities expose
  the two actual analysis pipelines and whether each requires a supplied code artifact.

These checks made **no paid application-model calls**. They used explicitly simulated
worker inputs. No `.env` or host credential files were inspected, and no frontend files
were changed. No new browser verification was needed for this backend-only change.

The new catalog is a backend-owned per-project SQLite file on the API data volume. Notes
live there; structured scientific records are projected JSON/CSV files and existing artifact
bytes remain in their project filesystem. See the file workspace contract and backup notes.
The hand/finger-analysis bug is diagnosed, with capability/prompt clarification added;
full pipeline selection or strict target rejection remains a separate product decision.


## Manual HPC/research integration and terminal — 2026-11-14

See [hpc-research-terminal-plan.md](hpc-research-terminal-plan.md) for actual observations.
The source branch was not merged: selected backend files and changes were adapted manually,
with the current file workspace retained. Paper ingestion passed 27 offline API checks;
HPC passed seven transport fixtures; terminal PTY, replay, resize, Ctrl-C, binary transcripts,
reopen persistence and output-limit/pagination checks passed. Existing integration (95) and
notes/tagging (112) checks passed, as did the offline Deep Agents flow and database FK check.
Live Slurm/Apptainer, live arXiv and live model requests were not run. The source branch's
historical live verification is not represented as current verification.
