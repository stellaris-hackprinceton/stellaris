# Stellaris backend achievements

Completed: November 14, 2026

Implementation checkpoint: `dba2545` on the `backend` branch

## Outcome

The backend MVP now supports a connected research workflow: create a project, conduct
cited research with an agent, save an experiment plan, upload video, execute isolated
analysis, inspect measurements and visual evidence, and generate a Markdown report.

This workflow was verified using live Amazon Nova research and an explicitly simulated
bouncing-ball recording. A separate real recording was also tested, with partial results
and insufficient evidence reported honestly.

## Architecture delivered

- One backend Docker Compose configuration builds the API, project runtime, and scientific
  worker images. Project containers are created dynamically when projects are created.
- Each project has a persistent container and its own filesystem volume. Containers remain
  active for the project's duration; archiving preserves the container and evidence.
- LangChain Deep Agents runs inside the owning project container, with persistent
  LangChain filesystem scratch space separate from published artifacts.
- AWS Bedrock with Amazon Nova 2 Lite is the default model provider. Credentials are passed
  only to the selected provider's agent execution. OpenAI remains an explicit alternative.
- Flask exposes the API under `/api/v1`; SQLite stores shared metadata and execution state.
- Scientific analysis uses temporary containers with read-only inputs, bounded resources,
  no network, and no access to project volumes, credentials, or the Docker socket.

## Capabilities implemented

| Area | Delivered behavior |
| --- | --- |
| Projects | Create, list, edit, archive, restore, and reconstruct workspace state |
| Research chat | Persist messages, queue agent runs, stream responses, and preserve interrupted messages |
| Literature | Retrieve actual arXiv metadata and abstracts; store sources and citations |
| Experiment plans | Save hypotheses, protocols, variables, success criteria, calibration, and limitations |
| Uploads | Create → transfer → complete, with hash, size, media, duration, and quota validation |
| Artifacts | Immutable originals and generated outputs, protected storage, downloads, and video byte ranges |
| Bouncing-ball analysis | Track motion, estimate apex heights and height ratios, apply entered calibration, and produce charts and annotated frames |
| Python analysis | Execute a supplied Python artifact and validate its declared results and evidence |
| Reports | Assemble Markdown from committed evidence, actual values, citations, methods, plots, and limitations |
| Live updates | Replayable project SSE events for messages, progress, logs, resources, and results |
| Execution recovery | Cancel runs, retain partial evidence, and mark interrupted execution as `WORKER_LOST` after restart |

## Reliability and scientific trust

- JSON POST commands use idempotency keys; editable resources use revisions and ETags.
- Runs snapshot accepted inputs before execution so later plan edits cannot change their method.
- Measurements link to evidence. Uncalibrated distances remain in pixels; physical scale is
  never invented. Unknown uncertainty remains unknown.
- Worker output is validated for file traversal, symlinks, references, evidence bounds,
  finite values, units, and data origin before publication.
- Simulated inputs and their derived results retain their simulation labels through reports.
- Executed code, logs, environment details, calibration assumptions, and provenance are retained.
- Audit storage is reserved so ordinary outputs cannot consume space needed for logs and provenance.
- Agent cancellation and restart cleanup terminate only the matching run's process and
  finalize its assistant message before the terminal run event.

## Verification achieved

| Verification | Result |
| --- | --- |
| Docker foundation and persistence | 44 checks passed |
| Resources, uploads, downloads, and SSE | 96 checks passed |
| Scientific execution and reports | 90 checks passed |
| Provider-free Deep Agents graph, scratch, transport, and configuration isolation | 6 checks passed |
| Focused malformed-output, quota, cancellation, recovery, and missing-credential regressions | Passed |
| Live Bedrock/Nova response and validated experiment tool call | Passed |
| Connected live research → plan → simulated-video analysis → report | Passed |

The simulated fixture produced six apexes and five ratios. Its first measured apex was
280.0004 px against 280 px ground truth; the mean height ratio was 0.63998 against 0.64.

The real SERC tennis-ball recording produced 55 accepted detections from 62 frames and
one valid apex at 388.974 px. The backend correctly withheld an energy-retention ratio
because there were too few valid flights, while retaining an attributed partial-evidence report.

These checks establish the tested workflows, not accuracy for every recording or experimental setup.

## Frontend handoff

Start the backend from `backend/` with Docker running:

```sh
docker compose --profile build-only build
docker compose up -d api
curl --fail http://127.0.0.1:8000/api/v1/health
```

- [API contract](Contracts.md): requests, responses, events, errors, and resource schemas.
- [Backend README](backend/README.md): configuration, startup, storage, and test commands.
- [Verification record](backend/VERIFICATION.md): observed results and scientific limitations.
- [Implementation status](backend/IMPLEMENTATION_PLAN.md): completed scope and open decisions.

The frontend should use the same-origin `/api` boundary, with a development proxy when
needed, and read `/api/v1/capabilities` before enabling features. The backend implementation
did not modify `frontend/`.

## Deliberate limits

- Authentication is omitted by request; the default deployment binds to localhost and is
  intended for local development and MVP integration.
- The first video pipeline assumes one visible ball, a fixed camera, a mostly static
  background, and approximately planar motion. Blur, occlusion, perspective, and very
  small objects can invalidate measurements.
- Literature retrieval covers metadata and abstracts, not automatic full-paper inspection.
- Project-ending and destructive deletion policies remain undecided; containers and evidence
  are retained rather than automatically removed.
- Audio analysis, live media streaming, HPC, collaboration, PDF/DOCX exports, and production
  deployment hardening are outside this MVP.
- `.env` stays Git-ignored. Agents did not inspect or print its contents; only the application
  loads credentials at runtime. The repository contains configuration examples, not secrets.
