# Stellaris agent instructions

## Scope and source documents

- Implement the backend. Do not modify anything in `frontend/`.
- Read `Stellaris Main Doc.md` for product scope and `Contracts.md` before implementing API, event, resource, or worker behavior. The contract is a proposed specification, not evidence of implemented functionality.
- Build the complete bouncing-ball research → experiment → measurement → Markdown-report workflow first. Keep future modalities and integrations out of the MVP.
- Keep backend code and infrastructure in `backend/`; root-level project instructions and shared documentation may live at the repository root.
- If an architectural decision requires a contract change, make the discrepancy explicit and resolve it with the user before implementing incompatible behavior.

## Docker architecture

- Maintain one backend Docker Compose configuration for the primary backend and its fixed supporting services. Create project containers dynamically through the backend; do not generate a Compose stack per project or enumerate projects as static services.
- The primary backend owns the public API, authentication, project routing, lifecycle management, persistence coordination, and live events. The frontend communicates with this backend.
- Each project has its own container and isolated persistent filesystem for project data and agent workspaces. Preserve project data across container stops and recreation. Keep project access scoped to the owning project.
- Keep scientific execution within the isolation and resource limits in `Contracts.md`. A project workspace container does not automatically provide sufficient isolation for generated code. Decide the worker arrangement before implementing execution.
- Keep Docker lifecycle control in the trusted primary backend. Project agents and scientific code must not receive the Docker socket, host credentials, or unrestricted host filesystem access.
- Container lifecycle, storage layout, and worker arrangement remain implementation decisions until settled with the user; do not assume that every project must run continuously.

## Claude Code delegation

- Delegate implementation, investigation, and review primarily to the local Claude Code CLI. Codex owns task breakdown, integration, verification, and the final outcome.
- Read `CC-Instructions.md` before delegating to Claude Code and follow its preflight, task briefs, tool restrictions, and result inspection workflow.
- Explicitly select `--model opus` for normal tasks and `--model sonnet` for very light tasks. Preserve configured effort unless the user specifies otherwise.
- Supply bounded tasks, exact file scope, relevant contract requirements, and observable acceptance criteria. Carry the backend-only scope and testing restrictions into every handoff.
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

- The current task is to establish these instructions and clarify implementation decisions. Begin sustained implementation when the user supplies the long-running goal.
