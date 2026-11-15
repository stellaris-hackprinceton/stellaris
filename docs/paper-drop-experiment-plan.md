# Paper-drop experiment: filming checklist

Collection update: the user has supplied nine named portrait iPhone clips and a phone-assisted height reference, reporting a 3 ft 10 in drop. Use [the final production brief](brag-paper-final/brag-plan.md) and its asset manifest for actual media facts. This checklist records the proposed protocol, not proof that all suggested controls, recording order, or dimensions were followed.

Question: **How does paper shape affect the time it takes to fall?**

You will record **nine silent clips: three drops each of flat, accordion-folded, and crumpled paper.** No speaking is needed. Rename each original file after recording. All nine recordings become experimental evidence, while the promotional video shows selected excerpts.

## 1. Gather the supplies

- Three equal sheets from the same pack. Use the same size and paper type, with no pieces removed or added.
- An iPhone and a stable support, such as a tripod or a secure stack of books.
- A ruler or tape measure and a visible height marker beside the drop area.
- A clear indoor floor area with good light and little airflow. Keep fans away.

## 2. Prepare three shapes

- **Flat:** leave the first sheet flat.
- **Folded:** fold the second into an accordion with roughly eight equal panels. Alternate the fold direction like a paper fan. Keep it in the same folded configuration for each drop and photograph that configuration.
- **Crumpled:** compress the third sheet into a compact ball by hand. Keep that same ball for all three drops.

Photograph the three shapes together. Record the original sheet dimensions, approximate folded dimensions, and approximate crumpled-ball diameter. Equal paper stock and size give nominally equal mass. We are not claiming the masses were weighed.

## 3. Set up the camera and release reference

1. Use landscape, normal Video mode, preferably 1080p at 60 fps if available. Avoid slow-motion and cinematic modes for the measurement originals.
2. Secure the phone. Keep its position fixed for all nine drops. Film from the side, with your release hand and the floor contact area visible throughout.
3. Put a visible release-height reference beside the drop area, approximately 1.2 m above the floor if space permits. Measure and record the actual height. Do not hold a ruler in the paper's path.
4. Before each release, align the **lowest part of the paper** with that height mark. This makes the initial clearance to first floor contact reproducible. It does not make the centers of mass identical across shapes. Record that geometric limitation.
5. Start the flat sheet horizontal. Start the folded shape in the same orientation each time, using the setup photo as a reference. Let go without throwing, pushing, or adding spin.
6. Make one practice recording. Check that the paper remains visible and that release and first floor contact can be identified. A practice drop is not a recorded trial unless explicitly designated before collection.

Record the actual camera mode and nominal fps in your note. Later analysis should use the file's real timestamps, not assume every frame is exactly 1/60 second apart.

## 4. Record and rename nine clips

Each clip contains **one drop only**. Start recording, wait about two seconds, release, let the paper reach the floor, wait another two seconds, then stop. Keep your hands from blocking the release and do not catch the paper before contact.

Record in this order, which alternates conditions and changes their position within each round:

1. `flat_01.MOV`
2. `folded_01.MOV`
3. `crumpled_01.MOV`
4. `folded_02.MOV`
5. `crumpled_02.MOV`
6. `flat_02.MOV`
7. `crumpled_03.MOV`
8. `flat_03.MOV`
9. `folded_03.MOV`

**Preserve the actual extension.** If your iPhone exports `.mp4`, use `flat_01.mp4`, and so on. Renaming `.MOV` to `.mp4` does not convert the video. Do not trim, accelerate, apply effects, or export through a messaging service that compresses the measurement originals.

Check the filename after each transfer. Maintain the mapping from the phone's original filename to the renamed file. The shape and trial number in the new name identify the condition. Later frame review identifies the event times. No spoken labels or cards in each recording are required.

If a trial goes wrong, preserve it with a note, for example `flat_02_obstructed.MOV`. Record a replacement with a distinct name such as `flat_02_repeat01.MOV` and document why. Do not silently discard a slow, fast, or surprising drop. Choose repeat/exclusion rules based on visibility or procedure failure, not the desired result.

## 5. Optional promotional footage

Record one 6–10 second landscape shot of the three finished shapes on a desk. A short shot of your hands folding or crumpling spare paper is also useful. Name these `setup_shapes` and `setup_hands`, preserving their extensions. These are promotional inserts, not extra experimental trials. Keep them separate from measurement inputs.

## 6. Include a short protocol note

Save a plain text file called `protocol.txt` with these fields filled in:

```text
Recording date:
Paper type and original dimensions:
Release reference height above floor:
Reference used: lowest point of each shape
Folded shape dimensions and initial orientation:
Approximate crumpled diameter:
Camera mode, resolution, nominal fps:
Camera position changed between trials? If yes, explain:
Airflow and floor conditions:
Original phone filenames -> renamed filenames:
Procedural mistakes, obscured events, repeats, or other notes:
```

Keep a setup photograph showing the height reference. We primarily measure elapsed time, so a spatial calibration is not needed just to report seconds. Height is still relevant to the protocol and any physical simulation.

## 7. Hand off the files

Put the nine originals, protocol note, and setup photographs into one local folder, with promotional inserts in a separate subfolder. Keep this footage outside Git. Share the absolute folder path in the Codex chat, or attach originals if supported. Tell me when transfer is complete.

The files must then be imported into the intended **Stellaris project and attached to the saved experiment**. Sending them to this chat does not make them accessible to the research agent inside Stellaris. Before a run, verify its selected files match these nine trials and that it uses a paper-timing script rather than the bouncing-ball pipeline.

If the app cannot decode the iPhone originals, retain them and create a documented compatible copy that preserves timing. Verify that copy before measurement. Do not assume a filename extension proves format compatibility.

## 8. What analysis will measure

For each trial, review the last frame still supported by the hand and the first clearly unsupported frame, then the last airborne frame and the first contact frame. Save those event brackets and their actual timestamps. Compute a central fall-time estimate and timing bounds from the brackets, flagging unclear cases. Keep screenshots or event frames as evidence. Any manual annotations must be labeled as manual.

The final figure should show every trial, with three groups, group means, and trial spread. The report will compare observations with a clearly labeled simplified drag simulation and discuss flutter, orientation, geometry, release differences, and the small sample. It will not claim a precise drag coefficient or a universal ordering from nine drops.

## Recording chronology

You can record now for a session that analyzes a previously recorded experiment. If the promotional story is specifically that you followed the in-app agent's proposed method, capture that design step before recording the final drops. We can prepare the technical workflow and prompts without spending application model credits first.
