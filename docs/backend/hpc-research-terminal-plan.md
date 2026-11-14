# Research, HPC and terminal backend integration

Status: planning and implementation in progress. No new capability is implied by this plan.

## Decisions

- Manually port the existing HPC/research implementation into `backend-v2`, per the user's
  clarified preference. Do not merge or cherry-pick the branch. Reuse its new modules and
  adapt its changes while preserving all current workspace behavior. The terminal is new work.
- Backend and contracts only. Preserve the file catalog and all existing scientific APIs.
- Use Luna workers while Claude is unavailable, per the user's explicit choice.
- User selected interactive terminal sessions. Terminal containers have a separate persistent
  per-project terminal volume and receive no provider keys, research scratch, host mounts,
  Docker socket, published evidence write access, or network access.
- HPC is opt-in and reports unavailable until configured. Remote jobs require explicit
  approval. Do not start a privileged local cluster implicitly or claim real-cluster testing.
- Read no `.env` or host credential/profile files. Runtime may consume explicitly configured
  settings without exposing their values. Avoid paid model calls during verification.

## Slices and ownership

1. **Research**: bounded PDF/arXiv ingestion, isolated extraction, immutable source/raw/text
   artifacts, paragraph locators, deterministic paper reading/search tools and citation checks.
   A dedicated worker owns new research modules, extractor, tools and its tests.
2. **Terminal**: real PTY shell, session lifecycle, sequenced input, streamed binary-safe output,
   resize, close, bounded retention, recovery and persistent project terminal storage.
   A dedicated worker owns new terminal modules, image and tests.
3. **HPC**: trusted SSH/Slurm/Apptainer adapter, hash-bound approvals, submission/recovery,
   cancellation and reuse of existing scientific-output validation. A dedicated worker owns
   new HPC modules and narrow analysis/executor hooks.
4. **Integration**: Codex owns existing application/schema/run acceptance/configuration/Compose
   edits, file-catalog compatibility, contract consolidation, Docker checks and commits.

Writers have disjoint file scopes. Integration starts from reviewed interfaces, not a whole
branch merge. Every slice must preserve honest failure states, original evidence and project
scoping. Existing record/artifact projection exposes the new persisted outputs in the catalog.

## Verification and checkpoints

- [ ] Contract for each feature checked against implementation and linked from shared docs.
- [ ] Research: deterministic PDF/LaTeX fixtures, archive traversal/limits, no-text failure,
      provenance and exact source/locator checks, old abstract-only behavior retained.
- [ ] Terminal: Docker PTY input/output, Ctrl-C, resize, binary output/replay, cross-project
      rejection, duplicate-input handling, limits, close/reopen persistence and restart cleanup.
- [ ] HPC: unavailable-by-default API, bound approval decisions and cancellation, scheduler
      transport/recovery fixtures; live cluster checks reported separately when configured.
- [ ] Legacy/catalog integration checks, independent review, clean commits and pushes.

No frontend implementation, general gesture-recognition pipeline, graph rendering, or broad
new integrations are included in this rewrite.
