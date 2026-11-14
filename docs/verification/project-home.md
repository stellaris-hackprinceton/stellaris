# Project home design and verification

Verified November 14, 2026 against the local Compose application.

## Design

The project home uses the existing cool-neutral background, white surfaces, graphite text, slate secondary text, and blue accent through shared theme tokens. A compact Stellaris masthead, serif page heading, and static Literature → Experiment → Measurement → Report line introduce the product without claiming project progress. Geist sans-serif carries controls and project content.

The single-column list retains Active/Archived tabs, API ordering, project links, and cursor pagination. Rows show the name, research question (or description fallback), update time, and a trailing arrow. Refresh and pagination failures retain loaded rows and offer retry. Empty and loading states use the same visual treatment.

The creation dialog retains existing validation, idempotent retries, and research navigation, with clearer field guidance, pending feedback, and explicit initial focus on the project name. The shared overlay accepts an optional CSS class. Other callers retain their existing styles. No backend interfaces, authentication, or project workspace styling changed.

## Completed checks

- Production frontend Docker image built successfully, including Next.js compilation and TypeScript. Image tag: `stellaris-frontend:home-verified`.
- Targeted ESLint passed for ProjectsScreen, CreateProjectDialog, and Overlay. Changed-file whitespace checks passed.
- Agent-installed isolated Chromium checked 1440, 1024, 390, and 320 CSS pixel widths without document horizontal overflow. Desktop, mobile, empty-state, loading-state, and dialog screenshots were inspected.
- Synthetic browser fixtures exercised long unbroken names, question truncation, description and missing-question fallbacks, archived labels, keyboard tab navigation, initial error/retry, stale refresh error/retry with retained rows, pagination error/retry with retained rows, and loading announcements.
- Dialog checks covered name validation, initial focus, Escape and focus restoration, native modal keyboard containment, disabled pending submission, and reuse of the same idempotency key after failure. Native dialog traversal can briefly focus the document body at its cycle boundary. No background control received keyboard focus.
- Reduced-motion duration and theme text/background contrast checks passed. The four primary foreground/background pairs meet 4.5:1 contrast.
- Real Compose project creation returned HTTP 201, navigated to Research, and remained listed after reload. The clearly labeled `TEST home revamp verification` project and its persistent container/data were retained.
- An independent Luna source and screenshot review returned a ship disposition with no material findings.

## Limits and local evidence

Browser interaction used the Compose development frontend. The production image was built but was not separately launched. Browser harnesses, isolated Chromium, fixtures, and screenshots remain outside Git under `C:/tmp/stellaris-rework/` (`home_check.py`, `home_states.py`, and `home_create.py`). Screenshots include the Next.js development indicator. Synthetic fixtures are interface test data, not scientific evidence.

No research messages, scientific runs, uploads, report generation, or model-provider requests were submitted. These checks are not a full accessibility audit or a scientific workflow verification. The Impeccable context launcher was unavailable. Review used repository context, source inspection, screenshots, and browser assertions instead.
