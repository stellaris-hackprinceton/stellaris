# Hyperframes composition brief: Stellaris paper experiment

Read [brag-plan.md](brag-plan.md) as the narrative contract. This is a user-requested 118-second demonstration, overriding the short Brag default. Do not render from this document until the real app captures and analysis artifacts exist.

Motion proposal: [animation-plan.md](animation-plan.md) is authoritative for section entrances/exits and audio treatment. The default animation family was selected on 2026-11-15. The public film focuses on Stellaris's workflow, without Codex or production-process commentary.

## Paths and output

Project root: `<checkout-root>`.

Primary evidence: `docs/brag-paper-final/media/`, mapped in [asset-manifest.json](asset-manifest.json). Keep the tracked originals untouched. Store generated proxies and renders in an ignored local output directory. Create presentation proxies and composition assets in a new ignored local output directory, with authored production records in root `docs/` as required by repository conventions.

Output: 1920 × 1080, 30 fps, 118 s, H.264 MP4 with SDR Rec.709 video and AAC audio. Use yuv420p for compatibility. Audio target around −16 LUFS integrated with true peak no higher than −1 dBTP. These are production targets, not recorded-media measurements.

No synthetic app screenshots, animated fake agent responses, invented source cards, or fabricated successful progress states. Editorial titles, captions, technical cards, and tool-fragmentation diagrams are permitted. Use real captured app interactions in all demonstration scenes.

## Look

LOOK: dark continuous research studio, soft violet edge light, white scientific figures, readable Geist typography, quiet evidence-first editing.

Use the implemented dark tokens in `frontend/styles/tokens.css`:

- Background `#111318`, canvas `#171a20`, surface `#1e2129`, border `#2e323d`.
- Primary text `#e6e8ee`, secondary text `#a0a6b4`, accent `#a68eff`.
- Optional editorial violet haze: `#a68eff` at 8–12% opacity, diffuse, confined near edges. Do not recolor real footage or scientific plots with it.
- Geist Sans for main text, Geist Mono for short labels. Use locally available bundled font assets if present, otherwise obtain the actual fonts through the normal composition dependency workflow. Do not silently replace the type system with a decorative display face.
- Actual mark: `frontend/public/brand/stellaris-mark.svg`.

Main headline 64 px / 1.08, scene caption 34 px / 1.2, secondary line 28 px / 1.25, short mono label 24 px / 1.25. At most one headline and one explanatory line per scene. Source attribution minimum 22 px. Keep all essential captions at least 80 px from the canvas edges. If app text is unreadable, crop to the relevant real region or re-record at suitable scale, without altering scientific text.

Prior visual reference: `docs/brag-paper-final/media/reference/previous-brag.mp4`, derived from `origin/brag:brag-output/brag.mp4`. Its poster and storyboard are references only. Keep the mood and added context, replace its screenshot montage with genuine execution.

## Exact layout presets

All coordinates are final-canvas pixels, x/y from the top-left.

**App view:** actual screen capture contained inside x=80, y=120, w=1760, h=824, with a subtle 16 px corner mask only outside meaningful content. Caption baseline region y=968–1030. Keep required app controls visible. A 16:9 recording fits at 1465 × 824 within that area, with unused space available for a short explanatory line. Do not stretch it to fill. Prefer deliberate crops where the source session permits readable chat and evidence together.

**Portrait plus context:** portrait video x=120, y=108, w=450, h=800, preserving 9:16. Context x=680, y=220, w=1080, h=520. Scene caption y=962. Keep release hand and floor within the full portrait view. Use “contain”, never a landscape cover crop or blurred duplicate background. The copy area can show a shape/trial label and the height. No numeric fall-time callout until independently measured.

**Three-shape hook:** portrait panels at x=165, 705, 1245, y=210, each 450 × 800, with labels above. Headline x=120, y=52, w=1680, h=90, centered. Use the same full-frame portrait aspect in each panel. The 9:16 panels end at y=1010. Keep shape labels around y=165. This is three separate pre-release stills, not simultaneous physical trials.

**Figure plus interpretation:** original plot contained inside x=100, y=170, w=1120, h=700. Text at x=1320, y=250, w=500, h=540. Keep a light plate behind scientific plots when needed. Do not invert them in dark mode. Use one evidence-backed finding and one limitation.

**Technical context:** three equal cards x=100, 690, 1280, y=360, w=540, h=280, 28 px headings and 26 px descriptions. “Under the hood” at x=100, y=180. All cards remain readable through 107–114 s. No sequential reveal that steals their reading time.

## iPhone HDR and rotation handling

Originals are HEVC Main 10 / HLG / BT.2020 with −90° display rotation. Respect the display matrix once to get upright 1080 × 1920. Do not apply an extra transpose after automatic rotation. Verify the decoded first frame and a landing frame against the original contact sheets.

Produce SDR Rec.709 presentation proxies with an explicit HLG-to-linear conversion, tone mapping, and Rec.709 output encoding using a toolchain that supports those operations. Simply changing tags or forcing `yuv420p` is insufficient. Check for washed highlights, crushed paper, gray blacks, and color shifts. Preserve time correspondence and record the conversion command, tool version, original hash, proxy hash, and timestamp mapping.

Original timestamps are authoritative for scientific measurement. If a 30 fps constant-rate proxy is used for composition, it is presentation-only. Never measure fall times from that proxy. Do not remove audio tracks or metadata from the preserved originals.

Use the approved original source intervals in the plan only after conversion correspondence is checked. Source in/out points are editorial windows, not release/contact annotations. Full-decoding reliability beyond the sampled inspection and browser compatibility still need to be verified during production.

## Height image

`3feet-10inches-height-reference.PNG` is a screenshot of iPhone Measure, not a calibrated laboratory scale. Use it only as a brief supporting insert. A crop may remove unrelated top and bottom phone controls while preserving the measurement line, both endpoints, and the 3′10″ label. Preserve the full original as evidence. Do not place an exact 1.1684 m scientific calibration badge on a frame.

The reference is not needed as public full-screen footage. Avoid emphasizing incidental background people. Do not crop the measurement endpoints to hide what was measured.

## Audio and motion

No narration, TTS, dialogue requirement, or automatic transcription. Inspect source audio before inclusion and omit incidental speech from the public edit if present. The trials are identified by filenames.

Music: use the selected original score "Release to Contact" ([music/release-to-contact.m4a](music/release-to-contact.m4a), 116 BPM, cue sheet alongside). It is generated by this repository's own script, so no third-party licence applies; credit it as original music. Do not substitute the happy-business bundled tracks. Detect real beats and phrase cues, then map major entrances and selected motion accents to them. Physical motion and text reading time retain their timing. See the animation proposal for the selection process.

Keyboard effects accompany genuine visible entry at 13–18 s, 46–51 s, and 93–98 s. Use short varied key bursts with pauses, no loud mechanical clatter. Align sound burst onset/offset within two output frames of the visible action. A paste gets one small cue. Add a low-key Send cue at the actual Send action. Do not place typing sounds under agent-generated response text.

Music leads the rhythm. Typing is soft and lightly audible, with reduced sharpness. Added paper sounds are low background texture with 80–120 ms fade-ins and 250–400 ms fade-outs, or omitted if distracting. Crossfade natural source sound gently without modifying originals. No artificial impact used as measurement evidence. Judge balance by listening rather than making music conspicuously quieter than every effect.

Transitions use the proposed section-specific motion in the animation plan, ranging from short masked slides to restrained spatial moves. Direct cuts handle omitted latency. No aggressive zoom loops. Keep key text settled for at least 0.3 s per word. Do not animate measured chart values from zero or introduce fabricated extrapolations.

## Brag/Hyperframes execution

Load the composition-related Hyperframes skills as directed by Brag. Use this plan and brief instead of a generic storyline workflow. Resolve media references, check actual source availability, create the real capture manifest, then compose. If required skills or rendering dependencies are missing, report that concrete gap. This brief does not install or execute them.

Run `hyperframes check` and fix all errors, including actual text contrast/overflow coverage. Inspect representative frames at 2, 7, 12, 21, 32, 42, 56, 61, 65, 69, 76, 84, 91, 102, 110, and 116 s. Review the complete edit at playback speed. Verify 3540 output frames, 118 s duration, Rec.709 tags, upright uncut trajectories, correct file labels, typing sync, no private data in captures, and citations tied to actual retrieval.

Deliver MP4, a settled poster baked into frame 0 without changing timing, share copy with disclosure and music attribution, and final source-to-scene mapping. All scientific results stay conditional until the app run succeeds honestly.
