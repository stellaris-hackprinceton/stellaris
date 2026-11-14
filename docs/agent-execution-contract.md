# Agent execution and workspace controls

Status: implemented; additive extension to the existing contracts.
User authorized implementation November 14, 2026. Existing routes remain compatible.

## Execution

Deep Agents stays in the persistent project container. LangChain tools request code
publication and execution through the trusted API controller; generated code runs only
in temporary workers without credentials, host mounts, Docker access or network.

Initial runtimes: `python`, `javascript`, `shell`. Execution capabilities advertise
available runtimes; unsupported runtimes return a validation error. Agent publication/execution binds to
the experiment revision accepted in its context, including its own subsequent saved revisions;
concurrent plan changes return REVISION_CONFLICT. Python-only and
bouncing-ball runs retain their existing behavior. The generic pipeline is
`script_analysis_v1`; its run request adds optional `runtime`, and accepts code artifacts
and zero or more genuine input artifacts. No observations may be invented for empty inputs.
Existing result.json, output validation, provenance, cancellation and limits apply.

An experiment gains optional nullable `implementation`:
`{runtime, code_artifact_id, pipeline:"script_analysis_v1"}`. It points to immutable,
project-scoped code, not agent scratch. Code generation saves source before execution.
`POST /projects/:id/experiments/:experiment_id/implementation` accepts
`{runtime,filename,source}` with Idempotency-Key and If-Match, and returns the updated
experiment and code artifact. Unsupported/mismatched references are rejected.

Tools return actual saved IDs, run status, bounded logs and output artifacts to the
agent. Each execution has a recorded immutable code snapshot; correction creates a new
code artifact/execution. File operations and executed source must refer to the same
saved files. Package downloads/network access remain disabled. Existing libraries and
installed commands can be used; missing dependencies must be reported honestly.

Studio shows implementation status beside the saved plan, including runtime, filename
and a link to inspect attached code. “Ask agent for script” opens a draft request targeted
to that existing experiment; sending the request remains explicit. Creating/designing an
experiment asks the agent to attach code when feasible unless the user requests plan-only
work. Generating code does not itself start an analysis run.

## Organization

`GET /projects/:id/agent-settings` returns
`{project_id,organization_permission:"off"|"ask"|"allow",revision,updated_at}` and ETag.
Default: `ask`. PATCH changes only `organization_permission`, requires If-Match, and
rejects archived projects. Mode changes do not execute existing pending requests.

Agent tools list materials and propose bounded organization operations: assign/remove
user tags, create collections and add/remove explicit members. Immutable originals,
system tags, scientific links and artifact IDs remain intact; physical evidence files
are not moved or overwritten. Organization permission does not authorize other projects,
code execution, deletion or network access.

Off rejects mutations. Ask saves a pending request; Allow applies it after current
permission/revision checks. `GET /projects/:id/organization-requests?status=pending`
returns Page of `{id,project_id,status,operation,revision,created_at,updated_at,error}`.
`POST /projects/:id/organization-requests/:request_id/decision` accepts
`{decision:"approve"|"reject"}` with Idempotency-Key. Decisions are single-use, scoped,
and applied against current project/permission/reference state; off blocks approval but
still permits rejecting a pending request.
Conflicts preserve the requested operation and show an honest error, not partial success.

Events: `agent.settings.updated` payload `{settings}`;
`organization.request.updated` payload `{request}`; catalog.changed retains its meaning.

## Clear chat

`POST /projects/:id/chat/clear` with `{}` and Idempotency-Key archives the current
conversation and increments its generation. Returns `{project_id,generation,cleared_at}`.
Active queued/running/awaiting-approval/cancelling agent runs block clearing with
409 CHAT_BUSY. Archived projects reject writes. Existing messages remain available for
run provenance but disappear from normal listings and future conversation context.
Agent conversation scratch is generation-scoped after clearing; published files,
sources, claims, experiments, runs and results are preserved.

`chat.cleared` payload is the clear response. Clients remove old message pages, pending
retry/draft state and active chat-specific selections. Late old-generation message events
must not repopulate cleared chat. New messages and agent snapshots carry the generation.

## Delivery checks

Verify actual Docker execution in at least two installed runtimes using real project
inputs; save outputs and failures without synthetic scientific data. Verify off/ask/allow
through the API, no-op/replay behavior and archived/conflicting requests. Verify clearing
preserves evidence, resets context and refuses active responses. Website checks use
isolated WebKit under /tmp; agents never inspect .env or host credential profiles.

## Archived runtime cleanup

The user authorized deleting old archived test containers while preserving their data.
Startup reconciliation now recreates/updates active projects only; explicitly removed
archived runtimes are not resurrected. Existing archived containers are not automatically
stopped or deleted. Workspace volumes and scientific records survive container cleanup.
This does not add idle shutdown or a project/data deletion endpoint.

## Experiment data uploads

Materials exposes Upload file, storing project-scoped files without requiring an
experiment. It opens the existing file import flow, preserving origin declarations,
upload validation and limits. Materials defaults to Desk, with Upload file available there. All materials exposes the
raw inventory of files, saved scripts, outputs and records. Experiments reference this shared
project storage rather than own a separate hidden file store. JSON is accepted as a dataset or document and retains
the existing strict, finite-number JSON validation (16 MiB parser limit). CSV, text and
other supported files remain capability-driven; this is not an unrestricted binary upload.
