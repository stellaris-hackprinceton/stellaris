# Virtual desk implementation and verification

November 14, 2026. The [approved direction](../design/virtual-desk.md) is implemented in the frontend. Verification below distinguishes browser fixtures from the connected application.

## Implemented interface

- Project home uses responsive visual cards and a labelled New project tile. Previews load near the viewport, use bounded project-scoped requests, preserve chart axes, and fall back to the research question after missing or failed media. The question remains visible when media is shown.
- Research uses full-width Literature, Experiments, Measurements and results, Findings, and Writing shelves. Shared shelf and add-tile components use the existing palette with rounded surfaces. Card columns respond to available content width. Findings and Writing now expand from three to nine cards.
- Experiments opens a card gallery before a plan is selected. Studio retains its four task views, adds saved input previews, and protects unsaved plans and recordings when leaving.
- Foundation Materials defaults to content cards, with an optional list presentation, existing filters and bulk selection. The catalog fills the working area until an inspector is opened. Narrow working areas use a sheet. Curated views remain capability-gated.
- Report cards lazily read bounded saved Markdown excerpts. Tracker retains active work before grouped history. Graph, chat, terminal, scientific labels, and provenance remain available through existing routes.

## Completed checks

- Frontend lint, TypeScript checking, and all ten existing focused tests passed inside the Compose frontend container. The final recording, focus, and preview changes also received targeted lint and TypeScript checks.
- Isolated agent-installed Chromium checked all six workspace destinations and project home at 1440, 1024, 768, 390, and 320 CSS pixels without document or workspace overflow.
- Browser interactions verified the home creation dialog's initial focus and Escape, Research shelf order, chat draft retention through collapse and rail/sheet transitions, experiment selection, return to the gallery, dirty-plan guards, and the creation tile's dialog.
- Synthetic browser fixtures verified three/two/one shelf columns, bounded expansion, source-inspector focus return, saved report excerpts, and contained chart previews. Fixtures are interface data and were never written to Stellaris.
- Those browser checks reported no JavaScript errors, application writes, or provider requests. The existing clearly labelled test project was read without changing its evidence.

- Production frontend Docker image `stellaris-frontend:desk-verified` built successfully, including compilation, TypeScript, and static-page generation. It was not separately launched. Browser checks used the hot-reloading Compose frontend.
- Final focused browser checks forced only the views capability off to exercise the foundation fallback against the connected backend. They verified a full-width catalog, a side inspector only with sufficient content width, a sheet with chat open, responsive transitions, and focus restoration.
- An isolated Chromium synthetic camera verified that idle Inputs navigation has no warning, an unuploaded recording prevents task/input-source changes when discard is declined, and confirmation allows leaving. No recording was uploaded and no physical camera was opened.

## Limits

The connected backend initially did not advertise the curated workspace views extension and later advertised it during verification. Both interfaces remain capability-gated. The foundation fallback was checked explicitly with only that capability disabled. Synthetic report and chart fixtures test interface presentation and are not scientific outputs.

On extension-capable backends, home previews use a sorted catalog lookup for the newest matching artifact. Older backends return an ascending artifact list, so the bounded fallback can show an older saved artifact. The card does not claim that preview is latest.

Browser tests use isolated tools, binaries, profiles, and screenshots under `C:/tmp/stellaris-rework/`. Harnesses include `desk_verify.py` and `desk_final.py`. Real application captures use `desk-real-*`, and mocked captures use `desk-fixture-*`.

No live model-provider request or new full research-to-report scientific workflow was executed for this layout change. Physical camera hardware and a full accessibility audit were not tested. Recording guards cover Studio task, input-source, experiment-selection, and creation controls. Navigation away through the project sidebar still has the existing client-side route-guard gap. No dependencies or public API schemas changed.
