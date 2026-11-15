# Stellaris: From an idea to an experiment

Production status: ready as an edit specification. Physical media is inspected and available locally. App session, scientific runs, measurements, and report remain to be captured and verified. This document does not claim those steps have occurred.

This is the canonical final brief for Brag. It supersedes the earlier 114-second [draft](../brag-paper-drop-plan.md). Pair it with [composition-brief.md](composition-brief.md), [asset-manifest.json](asset-manifest.json), and [capture-prompts.md](capture-prompts.md).

Latest creative direction: [animation-plan.md](animation-plan.md) specifies proposed section-specific entrances/exits, beat-sync strategy, soft typing, faded paper accents, and non-corporate electronic music. Its audio/motion directions supersede earlier defaults. Animation and track selection remain proposals for user review before production.

## Purpose and narrative

Stellaris connects a research question, sources, experimental instructions, physical observations, code execution, and an evidence-grounded explanation in one project. The audience is hackathon judges, students, and independent researchers.

Story: **We had an idea. We developed an experiment. We followed its instructions and filmed the drops. We uploaded the evidence and investigated what happened.**

The user followed the prepared protocol before supplying the recordings. The filmed app session should turn that same protocol into a saved in-app experiment. This is a reconstruction of the workflow, not a basis for claiming that a later app response caused an earlier recording. Keep production provenance in these records and “Workflow demonstration uses prepared recordings” in the accompanying description. The film focuses on the app workflow without a making-of discussion. Do not falsify dates or recording metadata.

Question: **How does paper shape affect fall time, and how well does a simple drag model explain what we observe?**

Hook: three portrait views of the paper shapes and “Three shapes. One question.” The paper experiment is the centerpiece. Preserve the earlier video's useful context about fragmented tools, LangChain, Bedrock, isolated computation, provenance, and honest conclusions.

## Output

- 1920 × 1080 landscape, 30 fps, exactly 118 seconds / 3540 frames.
- No narration and no spoken identification. Short captions, quiet music, real paper sounds if useful, synchronized typing effects.
- Brag's 15–25 second default is explicitly overridden by this user-requested full demonstration.
- Keep raw portrait evidence at its original timing and orientation. Presentation conversion is separate from scientific evidence.
- Create a new timestamped output directory when producing the video. Do not overwrite the prior video on `origin/brag` or the supplied recordings.

## Verified materials

Archive: `stellaris brag video data-20261115T035544Z-1-001.zip`.

Extracted originals: `docs/brag-paper-final/media/`. These originals are included in Git for the user-authorized public production handoff. The archive contains nine MOV recordings and one height-reference PNG. No app recording, report, measurement CSV, or simulation output was supplied.

All nine videos have a 1920 × 1080 encoded raster, a −90° display rotation, and an upright display size of 1080 × 1920. They are HEVC Main 10, 10-bit, BT.2020 with HLG transfer, and approximately 59.95–59.97 fps. Rotation metadata must be respected exactly once. Do not describe them as landscape or exactly constant 60 fps.

The height is user-reported as **3 ft 10 in = 46 in = 1.1684 m**. The reference PNG shows the iPhone Measure app's 3′10″ reading. Use **“3 ft 10 in · ≈1.17 m”** in the video. This is a nominal phone-assisted measurement with unquantified uncertainty, not a ruler-verified scale or exact center-of-mass release height.

Sampled frames from all nine clips show the paper release region and landing region. Flat sheets visibly change orientation during descent. These samples establish edit suitability, not measured event timestamps. No fall-time estimates have been accepted yet. Event frames require separate review using actual timestamps.

The earlier recording timestamps group clips by shape and do not match trial-number order within every group. Suffixes are trial identifiers, not proven collection chronology. Do not describe the supplied collection as randomized or interleaved. Paper dimensions, weighed masses, room airflow, and exact release alignment have not been supplied. Treat matching stock/mass as an assumption pending confirmation.

## Timeline and exact copy

Intervals use inclusive start and exclusive end. Cuts are at integer seconds. Scene frame boundaries equal time × 30. Longer typing takes may be shortened with visible edits, followed by a readable completed-prompt hold. Agent response latency is removed with direct cuts.

### 00:00–00:04 / frames 0–120 — The physical question

Three portrait panels show the pre-release state of `flat_01.MOV`, `folded_01.MOV`, and `crumpled_01.MOV`, using source time 0.00 as a still. Labels: “Flat”, “Folded”, “Crumpled”. Headline: **“Three shapes. One question.”** Small line: **“How does shape change a fall?”** No fabricated motion or timing comparison.

### 00:04–00:10 / frames 120–300 — Why this app exists

Carry forward the earlier video's tool-fragmentation concept. Small labels “Papers”, “Videos”, “Scripts”, “Plots”, “Reports” gather into one research workspace motif. Headline: **“Research gets scattered.”** Follow with **“Keep the question and evidence together.”** This is an editorial diagram, not a product screenshot. Subtle violet light, no arbitrary particles.

### 00:10–00:13 / frames 300–390 — Stellaris

Use the repository's real mark. Copy: **“Stellaris”**, **“From question to discovery.”** Transition directly into the app without a long logo animation.

### 00:13–00:25 / frames 390–750 — Ask a real question

Actual app capture of the first research prompt in [capture-prompts.md](capture-prompts.md). Entry 13–18, Send 18–19, completed response 19–25. Quiet typing at visible keystrokes. At the first latency cut show **“Waiting time omitted”** in a small readable caption for at least two seconds. Main caption: **“Start with an idea.”** Response must genuinely belong to this request and project.

### 00:25–00:36 / frames 750–1080 — Find the basis

25–30: genuine source discovery or import interaction. 30–36: opened retrieved material and its saved citation. Caption: **“Find sources. Keep the references.”** Use the actual source action. No fake NASA search through an arXiv-only tool. If retrieved, show the drag relationship from NASA with attribution. If only an abstract is available, label that material as an abstract.

### 00:36–00:46 / frames 1080–1380 — Turn the idea into a protocol

Open/save the actual experiment matching the procedure used here. Readable facts: **“3 shapes · 3 trials each”**, **“3 ft 10 in · ≈1.17 m”**, **“Measure release → first contact”**. Caption: **“Make the question testable.”** A small height-reference insert may appear for two seconds. It must retain its provenance as a phone measurement. Do not claim randomized trials or measured equal masses.

### 00:46–00:59 / frames 1380–1770 — Execute the model

46–51: real script request entry and Send. 51–54: actual simulation launch. 54–59: genuinely generated simulation plot. Caption: **“Run a simple model.”** Persistent plot label: **“Simulation · assumed drag values”**. The plot may show sensitivity to effective drag-to-mass values. Do not assign invented coefficients to the observed shapes or show fitted results as prior predictions.

### 00:59–01:11 / frames 1770–2130 — Follow the procedure

59–63: `flat_01.MOV`, source 0.00–2.80 s at 1× speed, centered in a four-second slot. Pre/post holds fill the remaining 1.20 s.

63–67: `folded_01.MOV`, source 0.00–2.15 s at 1× speed, with 1.85 s of pre/post holds.

67–71: `crumpled_01.MOV`, source 0.00–2.30 s at 1× speed, with 1.70 s of pre/post holds.

Allocate 0.30 s of each hold before motion, and the remainder after. Keep the last source frame visible during the post-hold and label holds in the asset timeline. These are editorial holds, not extra elapsed fall time. Do not place an elapsed-time counter over the whole slot. All three selected windows contain the visible descent and landing in the inspected samples.

Headline: **“Follow the procedure. Collect the evidence.”** Label each shape and trial. Small footer: **“Selected trials shown · 9 recordings collected”**. Use the portrait-plus-copy layout. No simultaneous-release comparison unless actual release frames have been separately validated and the edit is labeled “Aligned to release · separate trials.”

### 01:11–01:20 / frames 2130–2400 — Bring the evidence into the project

Real upload, completion, attachment, and save actions. Show all nine file identities through readable lists or two holds. Caption: **“Upload the observations.”** Keep setup/reference media separate from scientific trial inputs. No drag/drop animation substituting for an actual upload.

### 01:20–01:33 / frames 2400–2790 — Produce measurements

80–85: actual event-frame review or verified extraction process. Caption: **“Release → first contact.”** If manually marked, **“Manual frame annotations”** stays visible.

85–89: actual paper script and exact input selection, Run, real progress. 89–93: newly produced chart with all accepted trial values, any unresolved trial clearly indicated, and group summaries. Caption: **“Measured fall times.”** All nine recordings must remain accounted for, even if a measurement is missing. No guessed points or use of the ball pipeline.

### 01:33–01:47 / frames 2790–3210 — Explain the result

93–98: actual report prompt entry and Send. 98–104: generated finding beside evidence. 104–107: one real limitation. Caption: **“What does the evidence support?”** The finding and numeric callout remain conditional until a real run and report exist. Show an inconclusive result when warranted. Include the difference between a model's assumptions and observed orientation changes only as supported by the evidence.

### 01:47–01:54 / frames 3210–3420 — Under the hood

Carry forward the old video's technical context. Use three restrained cards, visible together for the full seven seconds:

- **“LangChain Deep Agents”** / “Research and interpretation”
- **“Amazon Bedrock”** / “Configured model provider”
- **“Isolated execution”** / “Reproducible code and saved evidence”

Caption: **“The work stays connected.”** Verify provider and execution claims against the actual demo session before final export. Do not imply a specific successful provider run from configuration presence alone. If space permits, keep a genuine evidence/run view behind the cards, with sufficient contrast.

### 01:54–01:58 / frames 3420–3540 — Close

Real report and chart recede into the dark studio field. Repository mark and **“Stellaris”**, **“From question to discovery.”** Small line: **“HackPrinceton · Science & Discovery”** based on project context, not an award claim. Hold settled text for at least two seconds and fade the music.

## Visual references to preserve

Previous video: Git ref `origin/brag`, commit `fe70c5f`, path `brag-output/brag.mp4`. Local inspection copy: `docs/brag-paper-final/media/reference/previous-brag.mp4`.

- At 2 s: scattered tools with central copy and soft violet illumination.
- At 10 s: Stellaris mark, strong white wordmark, small tagline.
- At 30 s: framed dark app view and violet focus on the chat composer. Preserve the framing, replace the source with actual new interactions.
- At 55 s: chat/analysis context. Use as a composition reference, not as paper-demo evidence.
- At 109 s: “Under the hood” transition. Inspect 107–114 s for the technical-context segment.
- At 115 s: clean branded close.

The old 25,000-person dataset, fitted equation, improvement statistic, and run/artifact counts are excluded from this paper demonstration. They are not new experimental evidence. Do not reuse old screenshots as a new successful paper session.

## Evidence and delivery gates

Scientific event times are not given by promotional edit windows. Review release/contact frame brackets from original presentation timestamps before calculating fall times. Preserve manual annotations and uncertainty. Keep phone-assisted height uncertainty, shape/orientation changes, grouped collection, and the exploratory three-trial sample in the report.

Verify source retrieval/import, paper-script execution, input mapping, saved outputs, and genuine model report generation before composing success scenes. This specification alone does not verify the app workflow. Missing assets remain unresolved, not opportunities for generated substitutes.

Use the composition brief's layout/audio/media rules. Run the Brag/Hyperframes checks, including actually audited text contrast. Verify the final video at full speed, upright orientation, SDR color, legibility, real-time drop motion, audible but quiet typing, and 118 s duration. Export MP4, poster, share copy, and source-to-scene manifest only after production is authorized.

Suggested accompanying copy: “We started with a question about falling paper. Stellaris brings the sources, experiment, code, observations, and explanation together. Workflow demonstration uses prepared recordings. Built with LangChain Deep Agents on Amazon Bedrock.” Confirm the actual provider session before using the final sentence.
