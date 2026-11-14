# Agent C frontend implementation handoff

Status: **Sol-owned implementation complete for source-level handoff. Live backend integration, Claude A/B assembly, and human interaction review remain pending.**

This handoff implements the accepted Sol plan and the [frontend specification](../frontend-implementation-spec.md) against the [API contract](../frontend-backend-contract.md). No backend endpoints, mock server, fixture data, automated tests, or Claude-owned features were added. Nothing was committed, pushed, or deployed.

## Implemented modules

- `contracts/api.ts`: exported wire schemas taken from the contract, including resource, provenance, approval, and project-event shapes.
- `contracts/requests.ts`: separate creation/edit DTOs and command/ETag metadata types. API resource fields retain `snake_case`.
- `lib/api/`: typed resource facade, same-origin credentials, session CSRF token, required POST command keys, PATCH ETags, error envelopes, request IDs, upload-byte progress/cancellation, artifact URLs, and bounded text reads.
- `lib/queries/`: resource/detail hooks, paginated flattened lists, mutation hooks, shared query keys, and revision/message reconciliation after REST refetches.
- `lib/events/`: fetch-based SSE parsing across chunk boundaries, comment/multiline handling, cursor identity checks, resource updates, message-gap recovery, and stale-update protection.
- `providers/`: root session/capability/query providers, persistent project runtime, connection/recovery status, and the explicit Claude integration bridge.
- `features/execution/`: all seven run states, history, progress, cancellation, new-run review, logs, errors, output/provenance links, and project-wide action approvals.
- `features/workspace/`: paginated artifact browsing, loaded-file filtering, metadata, experiment/parent associations, safe previews, and authenticated downloads.
- `features/reports/`: Markdown report requests from eligible analysis evidence, generation-run links, saved report previews, and downloads.
- `app/`: the documented project routes, redirects, layout/runtime composition, and a projects error boundary. Existing global CSS, font setup, and Next.js configuration choices were preserved.

All source paths above are relative to `frontend/`. Feature-local Sol styles live in `features/execution/sol.module.css`, using the proposed shared token names with fallbacks. This does not establish a second shared UI library.

## Dependency versions

Preserved Next.js `16.4.6`, React `19.3.0`, and React DOM `19.3.0`.

Added exact versions:

- `@tanstack/react-query`: `5.107.1`.
- `react-markdown`: `10.1.0`.
- `remark-gfm`: `4.0.1`.
- `rehype-sanitize`: `6.0.0`.

The package lock records the installation. Installation reported seven moderate advisories across the full dependency tree. The production-only dependency audit returned zero advisories. No broad dependency upgrade or automatic audit fix was applied.

## Configuration and authentication

Copy the committed `.env.example` to an appropriate untracked local environment file and supply the real backend settings:

```dotenv
STELLARIS_API_ORIGIN=http://127.0.0.1:5000
NEXT_PUBLIC_LOGIN_URL=
```

`STELLARIS_API_ORIGIN` is server-only and represents an origin without `/api/v1`. Next.js rewrites `/api/v1/:path*` to the backend's matching path. Restart the frontend after changing this setting. No backend runs at that address as part of this implementation.

The backend must accept the browser-facing frontend Origin for CSRF validation. Its cookie must work through the frontend origin, with the appropriate Path, SameSite, HttpOnly, production Secure, and domain settings. Do not bind it to an unrelated internal hostname. The deployment proxy must preserve cookies, byte-range headers, event delivery, and cancellation. These behaviors have not been exercised against a server.

`NEXT_PUBLIC_LOGIN_URL` is an optional existing login entry point, not a credential. Relative same-origin paths or HTTPS URLs are accepted. Without it, the sign-in state explains the missing configuration and offers a session recheck. The frontend does not implement login or bypass authentication.

Backend-unavailable and session-expired states are distinct. Project data is protected by session/capability resolution. Session expiry stops project work and clears user-scoped resources. Camera and media consent remain Claude B's responsibility.

## Public interfaces for Claude A and B

Import resource types from `@/contracts/api`, request/transport types from `@/contracts/requests`, hooks from `@/lib/queries`, and the API facade from `@/lib/api`.

Detail hooks expose `data`, `etag`, `request_id`, query loading/error state, and `refetch`. List hooks expose deduplicated `items`, query loading/error state, `has_next_page`, and `load_next_page`. They preserve backend ordering and pagination. Queries with no selected ID remain disabled.

The exported hooks cover session, capabilities, project/workspace, projects, messages, sources, claims, experiments, artifacts, runs, run results, measurements, logs, and approvals. Mutation variables are exported by name beside the mutation hooks.

Example command shape:

```ts
const submission = {
  project_id,
  body: { content_markdown: question, attachment_ids: [] },
  command: { idempotency_key: commandKey() }
}
// Retain this exact object/key for an ambiguous retry.
await submitMessage.mutateAsync(submission)
```

Create the key for a user action, not on every render or transport attempt. Mutations do not retry automatically. Definite validation failure requires an explicit corrected submission. A new scientific run requires a new key. Existing unresolved submissions retain their original body/key.

Editing uses `{ project_id, body, edit: { etag } }`, with `experiment_id` added for experiment edits. Preserve a local draft on `412`. The mutation layer does not silently overwrite a new server revision.

For uploads, use `api.uploads.create`, `api.uploads.putContent`, `api.uploads.get`, and `api.uploads.complete`. `putContent` takes a Blob/File and optional `{ signal, on_progress }`. `on_progress` receives `loaded_bytes` and nullable `total_bytes`. Only successful completion yields an Artifact suitable for attaching to a saved plan. The facade does not retain media in the query cache.

`useAppSession()` exposes `{ session, capabilities }` inside the root providers. `useProjectRuntime()` exposes `{ project_id, connection, reconnect }` inside project routes. `connection` is `connecting`, `connected`, `reconnecting`, or `offline`.

## Connecting Claude exports

`providers/feature-bridge.tsx` is the only integration point for the absent Claude components. It contains typed slots for:

- A: `ProjectsScreen`, `ProjectShell`, `ResearchScreen`.
- B: `StudioScreen`, `ResultsPane`.

When an owner supplies those exports, Agent C imports them statically into the bridge and replaces the corresponding `null` entries. Their prop shapes are defined there. No missing-module imports currently exist. Until assembly, affected views explicitly say “Awaiting Claude implementation”.

The fallback project navigation is temporary and contains no chat replacement. The execution screen mounts B's ResultsPane through its slot and does not open another event stream. Claude A's shell must preserve the passed route children. Claude features consume the existing providers rather than constructing independent query clients or project streams.

Claude A still owns global styling/shared controls, project creation/list UI, shell/chat, and research. Claude B still owns Studio/capture, full experiment editing, calibration, upload orchestration, and measurements/evidence inspection. No files were created in those feature directories.

## Recovery and evidence behavior

- Initial event subscription starts after a committed Workspace snapshot and visible-resource refresh. Cursors stay opaque and in runtime memory.
- SSE supports multiline data, CR/LF framing across chunks, and heartbeats. Events over the client safety limit of 1 MiB fail the connection visibly rather than growing memory indefinitely.
- Duplicate events do not append duplicate text. Older run revisions and older message chunks do not replace newer cached data. Finalized messages ignore delayed streaming updates. A gap reloads the Message.
- Expired event cursors trigger a new snapshot. Transient failures use bounded exponential backoff, then require manual reconnect. A connection that remains open for over 30 seconds resets the retry budget.
- While disconnected, active runs/results refresh every 10 seconds for at most five minutes. Polling stops when live events reconnect, the runtime exits, or active work ends.
- Connection loss never changes a server run to failed. Cancellation/approval state remains server-authored. Approval requires the persisted exact action hash and a user decision.
- Log rendering is bounded to 1,000 loaded entries. Sequence gaps trigger refetches. Complete retained logs remain available through pagination/output artifacts, subject to server retention and any server truncation warning.
- Text previews request bytes `0-262143` and stop reading at 256 KiB even if the server ignores Range. Truncation is disclosed. The full artifact remains downloadable.
- Markdown HTML is disabled and sanitized. Automatically loaded Markdown images are restricted to authenticated artifact content routes. Unsupported/executable document formats are not embedded.
- Report generation requires eligible terminal analysis evidence. Failed/cancelled evidence is visibly labeled partial. Saved outputs/provenance remain accessible regardless of the analysis outcome.

## Verification performed

- Read the existing Next.js instruction file and bundled documentation on layouts, client boundaries, and rewrites.
- Inspected source paths for authentication, command identity, ETag handling, cursor recovery, stale-cache protection, upload abort, preview limits, approval conflicts, and report eligibility.
- Static TypeScript check: `tsc --noEmit` passed.
- Source lint: ESLint over `app`, `providers`, `contracts`, `lib`, and `features` passed.
- Production-only dependency advisory inspection reported zero advisories.

At the initial handoff, verification was limited to source review, TypeScript, lint, and dependency inspection. The user subsequently clarified that tests and application launches are allowed for Stellaris. Additional verification is recorded below. No automated test suite or fixtures have been added, and no live backend workflows have been exercised.

### Additional verification — November 14, 2026

- The user authorized tests, application launches, and browser checks for Stellaris. The frontend `AGENTS.md` and implementation specification record that permission.
- `npm run build` passed, including production compilation, TypeScript, and generation of all documented project routes.
- The production frontend launched successfully on `http://127.0.0.1:3100`.
- Browser inspection of `/projects` confirmed the expected “Stellaris is unavailable” screen when the absent backend produces an HTTP 500 through the local API proxy.
- Pressing “Retry connection” kept the interface in that truthful unavailable state. No project records, fake measurements, or fabricated success were displayed.
- Next.js emitted a non-blocking lockfile-root warning. It did not prevent the build or launch.

These checks establish production build/launch and the backend-unavailable path. They do not verify authenticated project work, SSE recovery, real uploads, or scientific analysis. Those still need the actual backend and the Claude-owned UI. No unit-test suite was run.

## Remaining integration dependencies and human review

The backend directory currently has no API implementation. Supply authentication/session/capabilities, persistence, uploads, runs, artifacts, approvals where supported, and project SSE according to the contract. Authoritative video-frame extraction remains a separate unagreed backend extension. Do not invent a physical scale to bypass it.

After backend and Claude assembly, a human should exercise session failure/recovery, project navigation, permission denial, explicit recording/upload, interrupted upload, stale-plan edits, cancellation, approvals, event interruption, partial/failed results, safe previews, report generation/download, and refresh/deep-link recovery. Inspect desktop/mobile layout, focus handling, contrast, native media compatibility, and whether every scientific value links back to its actual evidence.

The implementation is ready for those integration steps. It does not establish that the complete research-to-report product is operational.
