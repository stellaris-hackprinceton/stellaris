# Stellaris agent instructions

## Scope and source documents

- Implement the backend. Do not modify anything in `frontend/`.
- Read `Stellaris Main Doc.md` for product scope and `Contracts.md` before implementing API, event, resource, or worker behavior. The contract is a proposed specification, not evidence of implemented functionality.
- Build the complete bouncing-ball research → experiment → measurement → Markdown-report workflow first. Keep future modalities and integrations out of the MVP.
- Keep backend code and infrastructure in `backend/`; root-level project instructions and shared documentation may live at the repository root.
- If an architectural decision requires a contract change, make the discrepancy explicit and resolve it with the user before implementing incompatible behavior.
- User decisions below supersede conflicting draft contract requirements. Update the contract to reflect them before implementing the affected interfaces.

## Confirmed implementation decisions

- Use LangChain Deep Agents. Each project's research agent runs inside that project's container and receives a project-isolated scratch space through LangChain, separate from published immutable evidence and artifacts.
- Current provider: AWS Bedrock with Amazon Nova, using LangChain ChatBedrockConverse. Configure STELLARIS_MODEL_PROVIDER=bedrock, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, and BEDROCK_MODEL_ID; AWS_SESSION_TOKEN is optional for temporary credentials. The user superseded the initial OpenAI choice. Live provider testing remains deferred until local checks finish and the user authorizes it. Never inspect credentials or load host AWS profiles; runtime receives only the configured provider environment.
- Create the project container when its project is created and keep it active for the project's duration. Do not add idle shutdown. Define what ends a project's duration before implementing container teardown; preserve its data.
- Execute scientific analysis in temporary isolated containers per run, separate from persistent project containers.
- Omit authentication for now, as explicitly requested by the user. Reconcile the session/authentication requirements in `Contracts.md` before implementing routes. Continue enforcing project-scoped references and execution isolation. Do not represent project IDs as an authorization boundary.
- Docker is available on this Mac, and the user authorizes using the existing Docker runtime for container testing. The restriction on personal applications applies to website-testing applications and profiles, not this authorized runtime.
- Use LangChain and the configured model provider. The MVP literature tool retrieves public arXiv metadata and abstracts without separate credentials; additional literature providers remain disabled. Save only material actually retrieved and never imply abstracts are full papers.

## Environment secrets

- `backend/.env` is reserved for user-populated runtime configuration and secrets. Keep it ignored by Git.
- Agents must not read, source, print, search, or otherwise inspect `.env` files, including through delegated tools. Exclude them from repository searches and handoffs. Never copy their contents into logs, prompts, or reports.
- Applications and Docker Compose may load the environment at runtime without exposing its contents. Verify configuration through safe presence checks or redacted application errors.
- Maintain variable names and blank placeholders in `backend/.env.example` for agent-readable configuration documentation. Ask the user to populate missing secrets themselves.

## Docker architecture

- Maintain one backend Docker Compose configuration for the primary backend and its fixed supporting services. Create project containers dynamically through the backend; do not generate a Compose stack per project or enumerate projects as static services.
- The primary backend owns the public API, project routing, lifecycle management, persistence coordination, and live events. The frontend communicates with this backend. Authentication is deferred per the confirmed decisions above.
- Each project has its own container and isolated persistent filesystem for project data and agent workspaces. Preserve project data across container stops and recreation. Keep project access scoped to the owning project.
- Keep scientific execution within the isolation and resource limits in `Contracts.md`. A project workspace container does not automatically provide sufficient isolation for generated code. Decide the worker arrangement before implementing execution.
- Keep Docker lifecycle control in the trusted primary backend. Project agents and scientific code must not receive the Docker socket, host credentials, or unrestricted host filesystem access.
- Use the confirmed lifecycle and worker arrangement above. Storage layout and the project-ending operation still require concrete implementation decisions.

## Claude Code delegation

- Current user override: Claude reached its usage limit during implementation. Use Luna (`gpt-6-luna`) subagents for this work until the user changes that preference. Give each writer a distinct file scope and verify its changes. Retain the Claude workflow below for future authorized use; do not retry Claude or switch models to evade its quota.
- Delegate implementation, investigation, and review primarily to the local Claude Code CLI. Codex owns task breakdown, integration, verification, and the final outcome.
- Read `CC-Instructions.md` before delegating to Claude Code and follow its preflight, task briefs, tool restrictions, and result inspection workflow.
- Explicitly select `--model opus` for normal tasks and `--model sonnet` for very light tasks. Preserve configured effort unless the user specifies otherwise.
- Supply bounded tasks, exact file scope, relevant contract requirements, and observable acceptance criteria. Carry the backend-only scope and testing restrictions into every handoff.
- Include the prohibition on reading `.env` files in every delegation brief.
- Prevent recursive delegation and concurrent writers to the same files. Inspect Claude's changes and run appropriate checks before accepting its work.
- If Claude is unavailable or unauthenticated, report the blocker. Do not silently substitute another model or install/authenticate the CLI.

## Implementation and verification

- Prefer the smallest working implementation, standard tools, and existing dependencies. Add abstractions or infrastructure only for a concrete requirement.
- Prioritize Docker integration checks and the real end-to-end workflow over extensive unit-test suites. Use focused tests where they protect important behavior; avoid coverage targets and tests that merely mirror implementation.
- Verify actual API behavior, project isolation and persistence, uploads, run lifecycle, and evidence-backed outputs as those features are built. Report which checks actually ran and any remaining gaps.
- Preserve original evidence, immutable run inputs, provenance, calibration assumptions, uncertainty, and honest failure states. Never fabricate measurements or present simulated data as observed.
- Preserve user edits. Keep credentials and temporary delegation/test artifacts out of Git.

## Testing on this Mac

- Use agent-installed test applications and isolated profiles under `/tmp` (for example, a separately downloaded WebKit browser). Do not launch, control, or reuse the user's installed applications, browser sessions, or personal profiles for website testing.
- Put downloaded test applications, their browser binaries, caches, profiles, and temporary test tooling under `/tmp`; configure tools so they do not default to user application or profile directories.
- Run backend/container checks without changing frontend files. If website testing requires missing frontend functionality, report the gap and keep the backend-only scope.

## Current authorization

- The user has authorized full backend implementation. Proceed in bounded slices following `backend/IMPLEMENTATION_PLAN.md`, resolving its open decisions with the user before implementing them.
