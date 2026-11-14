# Stellaris backend

Flask API, SQLite metadata, dynamic Docker project containers, isolated scientific workers,
and a LangChain Deep Agents research runtime. The frontend and API run together through the same Compose configuration.
The wire resources and events are defined in the [shared contract](../frontend-backend-contract.md).

## Run locally

Docker must be running. From the repository root:

```sh
docker compose -f backend/compose.yaml --profile build-only build
docker compose -f backend/compose.yaml up -d --wait
curl --fail http://127.0.0.1:8000/api/v1/health
```

One Compose file builds four images. The frontend and API are permanent Compose services.
Creating a project dynamically creates its persistent project container and named volume;
analysis creates a temporary worker and input volume, removed after collection.
The API listens on `127.0.0.1:8000` by default. Authentication is intentionally omitted.
`GET /api/v1/session` provides a local development identity for client compatibility.
Mutations validate supplied browser origins; a development frontend should proxy `/api`.

Open the app on port 3000. Compose supplies the internal API origin. See the [Compose guide](../docker-compose.md) for alternative ports, frontend hot reload, and troubleshooting.

Populate `backend/.env` yourself with the Bedrock variables listed below when ready for
live research-agent testing. Agents must never inspect that file. Variable names and
optional settings are documented in `.env.example`. Recreate the API after configuration
changes (`docker compose -f backend/compose.yaml up -d --force-recreate api` from the repository root). No LangChain API key is required;
LangSmith tracing is optional. The current provider is AWS Bedrock with Amazon Nova.

```dotenv
STELLARIS_MODEL_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.amazon.nova-2-lite-v1:0
# AWS_SESSION_TOKEN=  # only for temporary credentials
```

These are US-region example settings. The IAM identity needs Bedrock invocation and
streaming permission and access to the selected inference profile. Host AWS credential
files are never mounted.

## Behavior

- Projects: creation, listing, revision-based edits, archive/restore, and workspace summary.
  JSON POSTs require `Idempotency-Key`; editable records require their latest `If-Match` ETag.
- Research resources: sources, evidence-linked claims, and experiment plans with calibration.
  An experiment plan does not imply an execution has completed.
- Uploads: create → raw-byte PUT → complete. The server validates hashes, sizes, MIME types,
  decoded media, and quotas before exposing immutable artifacts. Downloads support ranges.
- Scientific runs: `bouncing_ball_v1` tracks one ball against a mostly static background.
  Decoded frame timestamps, detection failures, calibration, code, logs, environment, and
  assumptions are retained. `python_analysis_v1` accepts a Python code artifact and validates
  its `/output/result.json` against the worker contract.
- Reports: the project-contained LangChain Deep Agent evaluates terminal analysis evidence
  and the hypothesis, with isolated reproducible calculations when needed. Saved Markdown
  distinguishes AI interpretation from recorded measurements, citations, plots, uncertainty,
  limitations, and accepted method snapshots. Model/provider failure produces no template-only
  substitute. Historical deterministic reports remain readable. See [report verification](../verification/report-analysis.md).
- Chat: queued research-agent runs execute inside the owning project container. The agent
  has a persistent LangChain filesystem scratch space and proposes resources for backend
  validation. Missing model configuration produces an honest failed run, never a fake answer.
- Events: project SSE streams replay committed changes from opaque project-specific cursors,
  with reconnect support and idle heartbeats. REST remains sufficient to reconstruct state.

See `/api/v1/capabilities` for configured feature availability and enforced limits.
Audio, HPC, collaboration, live video streaming, and PDF/DOCX reports are outside this MVP.

## Storage and isolation

Shared metadata lives on `stellaris-api-data`. Each project uses a separate named volume
mounted at `/workspace`, with writable agent scratch at `/workspace/scratch` and protected
artifact files under `/workspace/data/artifacts`. The primary backend alone controls Docker.
Project containers have no published ports, socket, or host mounts; their bridge blocks
project-to-project communication while allowing outbound model/research requests.

Scientific workers receive only a read-only input volume and bounded output/tmp tmpfs.
They have no network, project volume, credentials, Docker socket, or host filesystem access.
Worker outputs are untrusted: paths, file types, evidence, local references, units, finite
numbers, and simulated origin are validated before publication.

Runs snapshot inputs before enqueueing. Cancellation serializes against completion;
interrupted execution becomes `WORKER_LOST` on backend restart. Original artifacts and
committed partial evidence remain accessible. Active runs reserve quota for bounded logs
and provenance; ordinary outputs cannot consume that reservation. Actual storage outages
are reported explicitly if an audit artifact cannot be persisted; the accepted snapshot
and retained log entries remain in backend metadata.

Project containers remain active, including for archived projects. No automatic teardown
or evidence deletion is implemented because the project-ending policy is not yet defined.

## File workspace foundation

The [file workspace contract](../file-workspace-contract.md) defines the additive API;
[its implementation plan](file-workspace-plan.md) tracks the rollout. Existing scientific
routes remain authoritative, while the file catalog provides shared organization.

Each project has a backend-owned SQLite catalog at `/data/catalogs/<project_id>.sqlite3`
on `stellaris-api-data`. `STELLARIS_CATALOG_DIR` can override the directory. This catalog
is not mounted into the project or worker container. Original artifact bytes stay in the
project volume. Structured records are downloadable JSON/CSV projections with stable IDs;
notes and their retained text revisions live in the catalog. Agent scratch is excluded.

Default tags mirror existing categories. User labels and links are organizational: they
cannot change an artifact's scientific origin or make a note into experimental evidence.
Notes have a separate retained-revision budget, `STELLARIS_MAX_NOTE_BYTES` (64 MiB default).

Back up **both** the complete API data volume and each project artifact volume. Stop writes
before copying SQLite files (including WAL/SHM), or use SQLite's online backup API; copying
only a live `.sqlite3` file can omit committed writes. A corrupt catalog fails visibly with
503 and is never replaced automatically. Restore its backup with the API stopped. If a
catalog is absent, scientific projections can be rebuilt on first access, but user notes,
tags, collections, and links require the catalog backup.

## Verification

Run the commands below from `backend/`. The scripts use HTTP and Docker, without a personal browser or other personal applications.
They create test projects whose containers and data are retained for inspection.
Synthetic fixtures and their results are explicitly marked **simulated**.

```sh
python3 scripts/smoke_test.py
python3 scripts/integration_test.py
python3 scripts/workspace_files_test.py --slice 1
python3 scripts/workspace_files_test.py --slice 2
python3 scripts/workspace_collections_test.py
python3 scripts/pipeline_test.py
docker compose exec -T api python - < scripts/check_worker_validation.py
docker compose exec -T api python - < scripts/check_audit_storage.py
python3 scripts/agent_integration_test.py
docker run --rm -i --network none --tmpfs /tmp:rw,size=64m stellaris-api:dev python - < scripts/check_missing_model.py
```

The scientific fixture checks measured heights and ratios against known values; it does
not establish accuracy for every real camera recording. The first pipeline assumes a fixed
camera, one visible ball, a mostly static background, and approximately planar motion.
Perspective, lens distortion, occlusion, and blur can invalidate measurements; inspect the
annotated evidence and limitations. Uncalibrated results remain in pixels or dimensionless ratios.
Live Bedrock/Nova behavior requires separately supplied configuration and live verification.

Observed results and remaining live-provider verification are recorded in [verification.md](verification.md).


## Full-text research, HPC and terminal extensions

See [research](../research-contract.md), [HPC](../hpc-contract.md), and
[terminal](../terminal-contract.md) for the additive frontend contracts. The existing file
catalog continues to expose new scientific sources and immutable ingestion outputs.
Paper ingestion accepts uploaded PDFs or an arXiv identifier and extracts text in an isolated
worker. Interactive terminals use a separate, non-root, network-disabled runtime with a persistent
per-project terminal workspace; they do not receive research-agent credentials or scratch.

Build the terminal image with the other backend images:

```sh
docker compose --profile build-only build api worker project-runtime terminal-runtime
python3 scripts/paper_ingest_test.py --skip-arxiv
docker compose exec -T api python - --offline-transport < scripts/hpc_test.py
```

`terminal_test.py` uses two synthetic project IDs supplied via `STELLARIS_TEST_PROJECT_ID`
and `STELLARIS_TEST_OTHER_PROJECT_ID`. It tests the backend shell; no browser is required.
HPC stays disabled with a blank `STELLARIS_SLURM_HOST`. The local `hpc` Compose profile uses a
privileged simulator and is not started by ordinary Compose startup; enabling it and real
cluster execution require separate configuration/testing. No frontend changes are included.
