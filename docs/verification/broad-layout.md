# Broad layout verification

Verified November 14, 2026 on the local Compose application.

The shared frame uses graphite navigation, a central workspace that scrolls independently on desktop, and right-hand chat. Chat drafts are retained in memory across collapse and responsive rail/sheet changes, with a new state owner for each project. Narrow screens use navigation and chat sheets.

Studio has URL-backed Plan, Inputs, Analysis, and Results task views. Plan and analysis remain mounted while hidden to preserve drafts. Leaving Inputs unmounts camera capture and warns that unuploaded recordings are discarded. Upload state stays in the parent. Accepted launches open Results with the run selected.

## Completed checks

- Production Docker build and TypeScript passed. Targeted ESLint passed for changed shell, chat, and Studio components.
- Isolated Chromium verified task navigation, keyboard arrows, plan and analysis draft retention, chat draft retention on collapse and resizing, and task restoration after refresh.
- Checked 1440, 1024, 390, and 320 CSS pixel widths without document horizontal overflow. Desktop and mobile screenshots were visually inspected.
- Browser checks used the existing synthetic verification project. No messages, new scientific runs, or model-provider requests were submitted.

The harness and screenshots remain outside Git under `C:/tmp/stellaris-rework/`. Physical recording and a full accessibility audit were not performed. Camera cleanup was reviewed in source. Shared layout and Studio navigation changed. Detailed content interfaces in the other product areas retain their existing behavior.

## Interface detail pass

The subsequent November 14 detail pass names primary views Research, Experiments, Activity, and Files, without changing routes. Launch controls use Python script and Input files. Scientific method identifiers remain available in a disclosure. Blocked launches offer direct navigation to review the plan or add inputs. Research source panes use available container width, and shared tab panels can receive keyboard focus.

Activity uses readable run kinds and statuses. File-type filter labels retain their original wire values and have explicit accessible names. Report creation is a closed disclosure on Files. Healthy connection feedback remains available to assistive technology without duplicating the header's visible indicator. Report and execution wording retains scientific qualifications.

The final production build, TypeScript, and targeted lint passed. Isolated Chromium verified the four navigation names, Question tab, Open experiment link, unselected launch method, Python script label, disabled incomplete launch, Files code filter value, report disclosure opening and closing, and Activity heading. Desktop and narrow layouts were checked through 320 pixels and screenshots inspected. These checks submitted no messages, runs, uploads, or provider requests. Report generation itself was not re-executed.

## Connected frame refinement (superseded)

The user rejected this broader styling change and clarified that the original inset rounded selection should be retained. The following records historical checks, not the current design.

Following the user's screenshot feedback, navigation rows now extend to the sidebar edges and header actions form joined cells. The sidebar brand, project header, and chat heading share a 64px desktop height. Research and experiment tabs have continuous 1px outer borders and shared dividers, fill their strip, and close at the right edge. The connection indicator uses compact text rather than a pill.

The production build and TypeScript passed, and targeted ConnectionStatus lint passed. Isolated Chromium measured the three header bottom edges within 1px, checked a 1px tab frame and the final tab endpoint, and verified navigation and fit at 1440, 1280, 1024, 390, and 320 pixels without document or workspace overflow. Final desktop and mobile screenshots were inspected. No provider requests or research mutations were made.

## Original selection restored

The user's clarification supersedes the connected-frame changes. The original inset navigation, brand spacing, header controls, chat heading, and tab treatment were restored. The only intended visual correction to the selected navigation item is a rectangular 2px blue accent clipped by the item's existing outer radius. Its inner edge remains straight, with no inset-shadow curvature.

The restored frontend production build and TypeScript passed and Compose reported healthy. Isolated Chromium verified the selection's 2px outer radius, zero-radius accent, hidden overflow, absence of inset shadow and row dividers, and fit through 320px. High-resolution sidebar and accent captures were visually inspected. No provider requests or research mutations were made.
