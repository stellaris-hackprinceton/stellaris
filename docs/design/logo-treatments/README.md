# Sketch-derived Stellaris logo candidates

The user rejected these candidates because they changed the central mandala and outer rays. They are retained for reference. Continue with the [reconstruction from the actual source S](../logo-reconstruction/README.md).

The three candidates share one continuous S-shaped lightning bolt. Eight copies rotate around the same center at 45° intervals. Opposite copies share their endpoints but separate along the tails, forming narrow outer eyes. The central mandala and its opening emerge from the repeated paths without a central clipping mask.

Open the [interactive comparison](http://localhost:3000/brand/candidates/index.html) while the local frontend is running. It includes the original artwork, enlarged blue/black previews, actual 36px and 24px samples, the single master S, and SVG downloads.

## Treatments

- **A, Faithful:** constant-width strokes with smoothed curves and regularized spacing. This is the strongest starting point for the application header.
- **B, Calligraphic:** filled vector outlines follow the same centerline, widening around the bends and tapering toward pointed ends. The finest tails become faint at small sizes.
- **C, Ornamental:** the same even-width construction adds one fine contour inside each outer eye and a repeated transparent gap at a central crossing to suggest weaving. Prefer 96px and larger so the extra detail remains legible.

These are cleaned vector interpretations of the sketch. They preserve its construction and proportions rather than reproduce every hand-drawn irregularity. The central rosette is approximately one-third of the full mark's diameter. The small, naturally formed central opening remains transparent. No candidate has been installed as the live app logo.

## Files and regeneration

Assets and the standalone comparison are in `frontend/public/brand/candidates/`. `original-sketch.png` is an unchanged copy of the supplied `Untitled_Artwork.png`. Its whitespace is cropped only by the preview's SVG viewport.

Run `python docs/design/logo-treatments/generate.py` from the repository root to regenerate the three SVGs and `master-s.svg`. The generator uses the Python standard library. An optional image path copies the original artwork into the candidate directory without modifying it.

The generator owns the master Bézier geometry, rotation angles, outline width profile, inset geometry, and repeated weave crossing. Change the master geometry there to keep every copy and treatment coordinated. The HTML comparison is maintained separately. Each candidate is a standalone SVG with a transparent background and a default Stellaris blue color. The comparison's black mode changes presentation without changing the downloadable assets.

## Verification

Verified November 14, 2026 with agent-installed isolated Chromium against the local Compose frontend:

- All SVGs parse and contain exactly eight uses of one master shape at 45° intervals. None contains a central clip path or background rectangle.
- Canvas pixel sampling confirmed transparent corners and central openings for all three treatments. The original artwork's SHA-256 matches the supplied file.
- Comparing the central region with a 45°-rotated rendering confirmed rotational consistency. A and C had zero mean alpha difference. B differed by less than 0.0001 on the 0–255 alpha scale.
- All preview images loaded, the blue/black control worked, and small-size samples measured exactly 36px and 24px.
- The comparison fit 1440, 1024, 390, and 320 CSS pixel widths without document horizontal overflow. No browser script errors occurred.
- Enlarged and small-size desktop previews, the original comparison, and mobile screenshots were inspected. The center remains identifiable at small sizes, but the eyes and fine details compress. This limit is disclosed on the comparison page.
- An independent Luna review found no material issues in A, B, or the comparison layout. Its concern about C's mask rotation was addressed with explicit rotated groups. The follow-up review confirmed that fix was resolved.

The browser harness and captures remain outside Git in `C:/tmp/stellaris-rework/`, including `logo_candidates_check.py` and `logo-comparison-*.png`. No application logic or dependencies changed, so verification focused on the actual static assets and browser preview rather than rebuilding the application. No research, scientific execution, or model-provider requests were made.
