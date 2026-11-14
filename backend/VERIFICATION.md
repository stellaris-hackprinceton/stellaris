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

## Remaining live verification

Live Nova now responds and invokes the experiment tool. The latest proposal reached the
backend but failed strict experiment validation (`INVALID_AGENT_OUTPUT`). Safe provider
error-code classification is implemented; no credential values are exposed. Live verification
is incomplete until a real response and backend-validated tool result succeed. Frontend
resource, upload, run, event, and reporting endpoints are available for integration now.

Reproduction commands are in `README.md`. Local check logs are retained under
`/tmp/stellaris-claude/`; they are not committed. Test projects remain available because
no destructive project-ending policy has been approved.
