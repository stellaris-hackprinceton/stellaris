# Stellaris paper-drop video · production record

This is a separate output folder from the earlier video's `brag-output/` (which lives on the `brag` branch and is unchanged).

- Brief followed: `docs/brag-paper-final/` (brag-plan.md timeline, animation-plan.md motion, composition-brief.md layout and look).
- Format: 1920 × 1080, 30 fps, 118 s / 3540 frames, H.264 + AAC, Rec.709 tags.
- Motion: precise motion with a few spatial transitions (selected 2026-11-15).
- Music (revision 2, at the user's request): "Voxel Revolution" by Kevin MacLeod, CC BY 4.0, the same track as the earlier video on main (`audio/voxel-revolution.m4a`, from main's `brag-output/work/music2.m4a`). It is padded to 118 s with a 1.4 s fade. The first cut used the original score "Release to Contact". Soft typing taps are placed at the logged real keystrokes and at the animated chat typing, and quiet tonal cues at each Send.
- Provider spend for the edit: none. The two agent prompts were run earlier in the recorded session. The analysis ran our own script in the isolated worker, and no report was generated.

## Source-to-scene map

| Time | Scene | Source |
|---|---|---|
| 0–13.5 s | Intro | Ported from main's `brag-output/composition2` (hook chips, the two statements, collapse into the purple mark, the "Stellaris" reveal), with the same timings |
| 13.5–19 s | Question → chat | Editorial animation, not a capture: the research question is typed into a stylized Assistant window and sent (requested by the user) |
| 19–23 s | Three shapes | First frames of flat_01, folded_01 and crumpled_01 (SDR proxies) |
| 23–30 s | Prompt 1 | `work/capture` 216.9–218.9 s (typing), 281.3–282.1 s (Send), 290 s (agent running), then shot 08 (response) |
| 30–37 s | Sources and assumptions | Shot 09: the agent's real report that arXiv was unavailable and no sources were saved, with drag equations kept as modeling assumptions |
| 37–44 s | Protocol | Shot 32 (saved experiment plan and hypothesis) with fact chips |
| 44–54 s | Simulation request | `work/capture` 479.8–534.7 s (typing, Send, running), then shot 20 (the real simulation response) |
| 54–66 s | Drops | flat_01 0–2.80 s, folded_01 0–2.15 s, crumpled_01 0–2.30 s at 1×, with a 0.3 s pre-hold and a post-hold on the last frame |
| 66–73.4 s | Uploads | `work/capture` 3787–3796.4 s (pick, Upload, Attach), then two list holds showing all nine files |
| 73.4–78.4 s | Event frames | `work/capture2` (Library, crumpled_02_events.png), then that artifact itself |
| 78.4–86.4 s | Analysis | `work/capture` 4794.3–4809.1 s (setup, Start), then 4962–4966 s (9 valid, 0 missing) |
| 86.4–103.4 s | Evidence | `work/capture2` finding view, then fall_times.png (the run's output) with the saved observation and limitation, verbatim |
| 103.4–110.4 s | Under the hood | Cards over the dimmed Overview results (capture2 shot f7-run). Claims checked in code: deepagents in project_runtime, Bedrock configured, worker network_mode none |
| 110.4–118 s | Outro | Ported from main's outro: purple mark, "Stellaris", "From question to discovery.", "HACKPRINCETON FALL ’26 · SCIENCE & DISCOVERY" |

Per-frame app sources: `composition/timeline.json`. The cut list is in `work/scripts/build_timeline.py`.

## Revision 2 (2026-11-15, user request)

- The intro and ending are copied from the earlier video on main, with its purple mark (`assets/mark-template.html`, from main's `#mark-svg`), plus main's background and ambient glows.
- New: an animated chat window that turns the research question into the experiment. This is editorial animation, not a capture, and it is clearly stylized.
- Music: main's track. The app story was tightened by about 14 s to fit.

## Departures from the brief, and why

- **Sources (25–36 s):** the agent's arXiv searches failed and nothing was saved. The scene shows that honestly, under the caption "Keep sources and assumptions apart.", with no invented source card.
- **Simulation plot:** the generated SVG stayed in the agent workspace and cannot be opened in the app. The scene shows the real response (model, reproduce command, outputs list) under the label "Simulation · assumed drag values".
- **Report (93–107 s):** no report was generated, to keep provider spend at zero. The scene uses the analysis run's saved observation and its recorded limitation, both quoted verbatim from the app.
- **Event review (80–85 s):** labelled "Automatic frame detection", since there were no manual annotations.
- **Omitted:** the height-reference insert (optional) and source paper audio (not checked for incidental speech).
- **Supplemental capture:** `work/capture2` is a second, view-only session recorded on 2026-11-15 (Library, finding, event strip, Overview). It made no changes and no provider calls.

## Drop proxies

The originals are HEVC Main 10, HLG / BT.2020, with a −90° display matrix. ffmpeg 4.4.2 in the brag-toolbox container applied that rotation once, then converted with zscale (HLG → linear, npl 203), a Hable tone map, and BT.709 output, at 30 fps and 540 × 960 (`work/scripts/proxies.sh`). These proxies are for presentation only. Fall times were measured from the originals' own timestamps by the in-app analysis.
