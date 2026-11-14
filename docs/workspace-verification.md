# Workspace implementation and verification

November 14, 2026. Implementation branch: `feature/rework-frontend`.

## Delivered

- Per-project catalog schema 2, transactional upgrade/rollback, authoritative artifact
  kinds, repeated kind filtering, exact origin lookup and collection presentation.
- Responsive five-widget Research desk with evidence qualifications and shared cards.
- Manual references, explicit PDF upload/extraction, arXiv ingestion and structured
  full-text reading with source locators and original downloads.
- Curated Materials presets, URL filters, pagination, notes, collections, independent
  presentation, conflict handling, legacy links and older-backend fallbacks.
- Reports navigation/library, contextual evidence composer, preserved uncertain
  submissions, discard confirmation, immutable Markdown reading and shared report cards.
- Project-wide interactive terminal: real PTY input/output, replay, resizing, retained
  session while hidden, explicit closure and transcript download. Terminal files remain
  separate from agent scratch and published evidence.

All catalog consumers share the existing query cache and project SSE connection.
HPC remains disabled. No credentials were inspected.

## Checks performed

- Catalog extension: **48 API checks**, plus **8 in-container migration fixtures**.
  Verified populated schema-1 upgrades, failure rollback, repeat initialization,
  artifact backfill and preservation of IDs, timestamps, revisions and organization.
- Existing collection regressions: **78 checks**; limits and worker-backed relation
  checks were deliberately skipped. Existing frontend tests: **10 passed** in Docker.
- TypeScript, ESLint and the Docker production frontend build passed. Production
  builds inside the development container require `NODE_ENV=production`.
- Isolated WebKit under `/tmp` verified shell typing, hide/navigation persistence,
  resizing and explicit closure. Personal browsers/profiles were never used.
- Real-data WebKit checks retrieved and extracted
  [arXiv:2010.11315](https://arxiv.org/abs/2010.11315), opened its structured reader,
  resolved its Materials link outside the Notes filter, exercised report draft discard
  confirmation, and checked a 390px layout without horizontal overflow.
- Exactly **one research message** was submitted to the configured Bedrock provider.
  Its agent run succeeded and returned a brief response; no further paid requests
  were needed. This counts application submissions, not an assertion about internal
  model invocation counts.
- Normal in-app Research → Materials → Reports navigation maintained its live
  connection with **no page errors**. WebKit reported canceled-stream messages during
  deliberate full-document navigations in the broader test; these did not reproduce
  during normal navigation.

The earlier catalog/collection regressions and shell smoke test used clearly labeled
test projects. After the user requested no synthetic data, remaining browser checks
used the real retrieved paper and actual provider response. Synthetic measurements
are not presented as observed research.

## Fixes found during integration

- Backfill no longer rewinds a catalog timestamp changed by collection organization.
- A stale terminal start/read response cannot regress newer streamed session state.
- HTTP 408 retains terminal retry identity. Oversized session histories fail explicitly
  instead of incorrectly offering a new session.
- Saved-view status survives reopening; a chosen creation preset supplies matching
  structural filters. Existing presentation edits still preserve membership/filter.
- Report drafts clear after acceptance/discard. Analysis results link to the contextual
  composer, and capability-fetch failures remain distinct from unsupported backends.

## Verification limits

- No new real experimental recording was supplied. This pass does **not** claim a
  newly observed experiment or report generated from new real measurement evidence.
- Real arXiv ingestion was checked end to end. Uploaded-PDF controls were implemented
  and statically checked; a new real-PDF upload was not repeated in this final pass.
- Not every pagination boundary, concurrent-tab edit or browser/device combination
  was exercised. Existing backend checks cover catalog pagination and revision conflicts.
- Shell session discovery fails explicitly beyond 20,000 historical sessions; a
  dedicated current-session endpoint can remove that practical frontend limit later.

The running Compose services use this checkout and preserve existing project volumes.
