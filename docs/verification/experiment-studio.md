# Experiment studio verification

Checked November 14, 2026 against the existing Docker Compose frontend and API. The [design specification](../design/experiment-studio.md) records the approved visual direction. Existing user changes and saved project data were retained.

## Frontend checks

- ESLint passed in the frontend container.
- All 10 existing focused frontend tests passed.
- TypeScript `tsc --noEmit` passed.
- An isolated production build using `NODE_ENV=production npm run build -- --webpack` completed compilation, type checking, and generation of all 14 static pages.
- `git diff --check` passed. Git reports a line-ending normalization notice for the existing tracker stylesheet.

The production build used `/tmp/stellaris-studio-build` inside the existing container so the live development output remained untouched. Dependencies were linked from `/app/node_modules`. Turbopack cannot resolve that temporary external link, so the isolated build used Webpack. Next reported 27 files outside the temporary output tracing root when assembling standalone output. This verifies production compilation, not a deployable standalone package or production-image startup.

## Browser and behavior checks

Used the agent-installed Chromium and an isolated profile under `/tmp/stellaris-rework`. No user browser or personal profile was used. Two visual inspection rounds covered desktop and mobile captures. Subsequent checks used DOM assertions to confirm the identified fixes.

Projects, Overview, Library, Experiments, Reports, Connections, and Activity were checked at 390, 768, 1024, and 1440px. Final assertions reported no document or workspace horizontal overflow, exactly one visible h1 per page, no browser page errors, and no API writes.

Verified interactions:

- New project dialog receives initial focus and restores focus when closed with Escape.
- Assistant draft text survives collapse, reopening, and transition from docked rail to sheet.
- Mobile project navigation opens, reaches Library, and closes after navigation.
- The existing `view=inputs` URL selects the visible Data tab.
- Library View changes preserve legacy query values while showing Sources, Notes, and All items labels.
- Name search updates the URL and clears after the debounce.
- Existing collection selection and clearing preserve scoped browsing.
- Library item inspection uses an inline region when there is room and a sheet when Assistant reduces the available space.
- At 1920px, docked Assistant and the inline Library inspector coexist without document overflow.
- New note remains reachable through Add without submitting a note.
- Fake-camera capture starts and stops locally. Leaving with an unsaved recording can be cancelled, or confirmed to discard it. No recording was uploaded.
- A browser-only archived project response disables Library Add.
- A browser-only foundation-catalog capability response retains Library and the shared 28px title size.

The initial browser pass exposed a width rule stretching the visually hidden live-status announcement. The content-width rule now excludes screen-reader-only elements. A separate review identified a mobile first-paint sidebar flash. Sidebar visibility and mobile header controls now use CSS rather than waiting for hydration.

Computed palette contrast ratios are 13.68:1 for primary text on the workspace, 5.28:1 for secondary text on the workspace, 4.78:1 for secondary text on the sidebar, 7.26:1 for white on the primary violet action, 8.74:1 for selected text, and 3.10:1 for control borders on the workspace. This is not a full accessibility audit.

Temporary browser scripts and results remain under `/tmp/stellaris-rework`, including `studio_check.py`, `library_check.py`, `layout_final.py`, `studio_supplement.py`, `studio_wide.py`, `studio-layout-result.json`, and `studio-supplement-result.json`. They are outside Git. Existing saved local test projects include explicitly identified synthetic or simulated data and are not scientific observations.

## Backend and provider boundary

The existing backend health endpoint returned HTTP 200. Browser checks read the real project catalog and capability endpoints. The checks made no API writes and did not rerun scientific analysis or generate a new report. API resources, route values, and backend behavior were not changed.

No live model-provider request was made. Live literature search, research chat, and experiment-design capabilities were unavailable in the local capability response. Provider verification remains deferred. No `.env` file or host AWS profile was inspected.
