# Original-source logo reconstruction

## Current live code refinement

The user subsequently requested direct SVG edits using the source-based mandala: shorter curved outer rays, removal of the rough doubled outer contour and disconnected accents, round-brush linework, and graphite grey. The live home-page logo now references `frontend/public/brand/stellaris-mark.svg` through the reusable `StellarisMark` component.

Run `python docs/design/logo-reconstruction/refine.py` to regenerate the current asset. It retains the source's middle bends between image y coordinates 785 and 1215, repeated eight times, and rounds their trimmed ends. Each copy receives one shorter smooth primary ray with a constant 26-unit stroke and round cap. The long secondary tail is removed. The retained source iris still carries the original overlapping contour geometry. Its central opening is not cut out artificially.

The standalone asset defaults to graphite `#41464E`. The live SVG reference inherits the same color from its scoped header style. The earlier source reconstruction below is retained as provenance, rather than the current outer-ray design.

Isolated Chromium verified the standalone asset and the external SVG reference in the live project home, including a nonempty rendered bounding box and layouts through 320px without overflow. Targeted ESLint passed for the changed component. Full-size and native-size screenshots were inspected. An independent Luna review found no material visual bugs or disconnected details in the generator, asset, and screenshots. This verification did not rebuild the application or submit provider requests. Captures remain outside Git under `C:/tmp/stellaris-rework/refined-eye-*.png`.

This replaces the earlier A/B/C direction, which the user rejected because the invented S changed the central mandala and outer rays. The intended mark is a focused starry eye. The dense mandala forms the eye, surrounded by curved rays.

Open the [source-based comparison](http://localhost:3000/brand/reconstruction/index.html) for the historical reconstruction or the [current SVG](http://localhost:3000/brand/stellaris-mark.svg) for the installed refinement.

## Construction

The outline was extracted directly from the ink in `Untitled_Artwork_2.png`, rather than redrawing a substitute S centerline. The image was inspected at its original 2752 × 2064 resolution. Pixels with alpha above 127 and combined RGB below 384 defined the ink boundary. The main boundary was traced and simplified with a 0.85px tolerance, producing 978 vector vertices. Those points and the unsmoothed path are retained in `trace.json`.

Eight copies rotate at 45° intervals around image coordinate (1390, 983). That shared center was fitted against the original assembled sketch. The hand-assembled placements are not identical to this regular rotation, so the reconstruction does not claim an exact match to every ray position. The original S's broad hook, narrow bend, pressure variation, and tail curvature remain present.

`generate.py` produces a direct reconstruction and a lightly smoothed reconstruction from the same contour. Edge cleanup averages neighboring boundary vertices and interpolates them with cubic curves. It does not replace the source centerline, join ray tips, remove central openings, or introduce decorative details. There are no masks or clipping cutouts.

Run `python docs/design/logo-reconstruction/generate.py` from the repository root to regenerate the SVGs in `frontend/public/brand/reconstruction/`. The PNG references are unchanged copies of the user's two source images. The preview crops whitespace through SVG viewports without modifying either image.

## Verification

Verified November 14, 2026 in agent-installed isolated Chromium against the local frontend:

- Both reference PNGs match their supplied originals by SHA-256.
- The direct single-S trace has 98.95% binary ink intersection-over-union against the original S. The edge-cleaned single S has 98.19%. These measure contour fidelity, not aesthetic approval or exact agreement of the assembled mandala.
- Both reconstructed SVGs contain eight uses with 45° rotation increments. Neither contains a mask or clip path.
- Pixel sampling confirmed transparent backgrounds and an open center.
- All preview images loaded without browser script errors. The comparison fits 1440, 1024, 390, and 320 CSS pixel widths without document horizontal overflow.
- Full-size comparisons and enlarged centers were visually inspected. Small inner details compress at 24px, which the preview explicitly notes.
- An independent Luna source and screenshot review found no material bugs or false claims and confirmed that the source-based trace restores the missing center detail. Its metadata consistency note was corrected so the generator reads the fitted pivot directly from `trace.json`.

Browser extraction, fitting, and verification scripts and captures remain outside Git under `C:/tmp/stellaris-rework/`. Relevant files include `extract_logo.py`, `fit_logo_pivot.py`, `reconstruction_check.py`, and `eye-reconstruction-*.png`. No research messages, model requests, or scientific runs were submitted. Changes are confined to candidate assets, their comparison, and documentation.
