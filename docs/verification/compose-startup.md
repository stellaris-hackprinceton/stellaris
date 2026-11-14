# Compose startup verification — November 14, 2026

The application was built and started through `backend/compose.yaml` on Windows Docker Desktop. The default host frontend port was already in use, so this run selected `STELLARIS_FRONTEND_PORT=3100` without stopping the existing development server. The API uses host port 8000.

## Verified

- API, project-runtime, and scientific-worker images built through the Compose build-only profile.
- Frontend image built successfully, including production compilation, TypeScript checks, and all application routes.
- Frontend and API services reached healthy status under Compose.
- Browser inspection of `/projects` showed the styled project list and the saved verification project, replacing the earlier backend-unavailable screen.
- `http://127.0.0.1:3100/api/v1/session` returned 200 and the explicit `development_none` session.
- API health reported database and Docker availability as `ok`.
- The documentation index, Compose guide, shared contract, and frontend handoff returned 200 through the frontend's documentation route.
- The canonical documentation directory is mounted read-only into the frontend. Its startup verification page returned 200 immediately without an image rebuild. Environment-file and encoded traversal requests returned 404.
- Creating a clearly labeled `Compose startup verification` project through the frontend proxy returned 201 and provisioned its real persistent runtime container.
- Repeating that request with the same idempotency key returned the same project. Its Workspace returned 200.
- Seven focused frontend transport tests passed, covering unresolved sessions, empty-token rejection, explicit development mode, authenticated CSRF/ETags, session clearing, command keys, and structured errors.
- Static TypeScript and source lint checks passed. Relative Markdown link checks found no missing targets after consolidation.

Docker Desktop became unresponsive during initial startup. Recovery stopped only Docker-specific processes and its Docker-specific WSL runtime, then relaunched Docker Desktop. Images and volumes were preserved. No reset, prune, volume deletion, or unrelated WSL shutdown was used.

## Limits

These checks establish local Compose startup, request routing, development-session compatibility, project persistence/runtime creation, and documentation access. They do not establish camera measurement accuracy, real experimental results, or live Bedrock/Nova access. No research-model request was made. Credentials were not inspected or printed. Earlier backend scientific verification remains separately recorded in [the backend verification history](../backend/verification.md).
