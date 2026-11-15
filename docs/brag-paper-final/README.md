# Stellaris video production handoff

Start here after cloning the branch `feature/brag-paper-experiment-video-demo`. All footage needed from the user is tracked alongside this brief. No access to the original author's device, Downloads directory, prior chat, or ignored `.local` directory is required.

## Read in this order

1. Repository `AGENTS.md`, especially secret handling, provider authorization, and isolated application testing.
2. [Final Brag plan](brag-plan.md), including the 118-second scene sequence and factual limits.
3. [Animation proposal](animation-plan.md). The user wants distinct section entrances/exits, soft typing, faded paper textures, and non-corporate music. Selected: the default motion family and the original score in [music/](music/).
4. [Composition brief](composition-brief.md), including portrait geometry, HDR conversion, colors, and audio targets.
5. [Capture prompts](capture-prompts.md) for genuine app actions and evidence mapping.
6. [Asset manifest](asset-manifest.json) for hashes, source windows, metadata, and unresolved production inputs.

The older documents in `docs/brag-paper-drop-plan.md` and `docs/paper-drop-experiment-plan.md` are planning history. Their proposed recording controls do not prove what happened in the supplied footage. This directory is authoritative for the actual edit.

## Media included

`media/` contains `flat_01.MOV` through `flat_03.MOV`, `folded_01.MOV` through `folded_03.MOV`, `crumpled_01.MOV` through `crumpled_03.MOV`, and `3feet-10inches-height-reference.PNG`.

`media/reference/previous-brag.mp4` and `media/reference/previous-brag.jpg` preserve the earlier video's context and visual style. They are style references, not new paper-experiment evidence. The old dataset's figures and claims must not appear as paper results.

The ten supplied original assets total 65,875,321 bytes. Every file is below GitHub's individual-file limit. Git stores the actual media, not Git LFS pointers or expiring chat/download links. The previous video is approximately 37.5 MB and already exists as a Git object in the source branch's history.

The user explicitly requested publishing these production materials. Do not upload unrelated project data, credentials, environment files, or personal application profiles. Repository access and public visibility depend on the destination chosen by the user, not on the presence of these files.

## Verify a fresh clone

From the repository root, run:

```text
python docs/brag-paper-final/verify_assets.py
```

The verifier uses Python's standard library. It checks hashes and byte counts for all supplied originals, both prior-video references, featured windows, and the 118-second timeline. It reads only the explicitly listed media and manifest. It does not read `.env`, access a provider, run Docker, or render a video.

Then inspect decoding locally with your available FFmpeg toolchain. iPhone video is HEVC Main 10 with HLG/BT.2020 and rotation metadata. Preserve originals. Create separate SDR Rec.709 presentation proxies and record their conversion/timestamp mapping. Scientific event annotation must use the original timestamps, not a 30 fps presentation proxy.

## Output folder

Production work for this video goes in its own ignored folder, `brag-output-paper-drop-20261115/`, never in `brag-output/`. That folder holds the earlier video on the `brag` branch and must stay as it is. The recorded app session (`work/capture/`), the local analysis runs, and the music render are kept locally under `brag-output-paper-drop-20261115/work/` and are not tracked. The selected music and its generator are tracked in [music/](music/).

## What remains to do

- Animation family and music are selected (see the animation plan's Selected music section).
- Check source retrieval/import, custom paper-analysis code, input selection, and report paths without provider requests first.
- Obtain the live-provider authorization required by the repository instructions before spending application credits. This publishing task does not grant it.
- Record an actual coherent app session. No app capture or successful paper analysis has yet been supplied.
- Save event annotations, measured trial data, simulation outputs, actual agent interpretation, and source-to-scene references. No fall-time measurements have been fabricated or accepted in the current manifest.
- Build and validate the edit using Brag/Hyperframes, then follow the user's preview/render instructions. Do not substitute animated mock interactions for missing app functionality.

Use the real workflow narrative: idea → experiment instructions → physical recording → upload → analysis. The physical protocol was prepared before collection. The later in-app scene reconstructs that workflow using the same protocol. Keep factual provenance in these records and the prepared-recordings note in accompanying copy, without a Codex making-of segment in the film.

## Skill availability on another device

This repository contains a complete production brief, not a bundled installation of Brag or Hyperframes. If Brag is unavailable, use its upstream source at [latent-spaces/brag](https://github.com/latent-spaces/brag) and the receiving agent's normal skill installation workflow. Read the installed Brag instructions and load the Hyperframes composition skills it calls for. Do not assume the original device's temporary FFmpeg installation or global skill folder exists.

Respect repository delegation instructions. Do not recursively launch agents or inspect secrets. Test applications and browser profiles must be isolated as required by `AGENTS.md`.

## Pasteable receiving-agent brief

> Work on the Stellaris paper-experiment promotional video using `docs/brag-paper-final/README.md` as the entrypoint. Read the repository instructions, verify the included media, and review the final plan, composition brief, animation proposal, capture prompts, and manifest. Keep the 118-second workflow-focused story, the earlier video's violet visual language and useful technical context, soft typing, and faded paper textures. Avoid generic business music. First help me select the proposed animation family and actual music before implementing the motion studies. Preserve real evidence and app interactions. Paper-analysis measurements and app recordings are still pending. Do not inspect `.env` or host credentials, invent successful runs, or spend live-provider credits without the required authorization. The footage and reference video are tracked in this branch.
