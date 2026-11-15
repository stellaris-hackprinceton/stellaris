# App-session prompts and evidence mapping

Purpose: capture genuine Stellaris work around the experiment protocol already developed with the user. These prompts are inputs, not scripted responses. Do not claim a later in-app design response preceded the physical footage. The public narrative can follow idea → protocol → filming → import → analysis, with the prepared-recording disclosure in the accompanying description.

Do not start paid application requests as part of writing this specification. Verify provider-free paths first. Do not inspect `.env` or host AWS profiles. App/Compose may load runtime configuration normally without exposing it.

## Source set

- [NASA: Slowing Down in Space activity](https://www.nasa.gov/stem-content/slowing-down-in-space-hands-on-activity/), a flat/crumpled-paper experiment starting point.
- [NASA Glenn: Drag Equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/), basis for the simplified drag model.
- [NASA Glenn: Shape Effects on Drag](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/shape-effects-on-drag/), context for shape dependence, not transferable coefficients for our exact sheets.

These are suggested educational references. App retrieval has not been performed for this demo. Use actual enabled retrieval/import paths. Never turn a supplied URL into a claim that its contents were read. If only arXiv metadata/abstract retrieval is available, retrieve relevant material or import the NASA content through a supported method with clear provenance. Do not pretend imported sources were live search results.

## Prompt 1: research and experiment

> I want to investigate how changing paper shape changes its fall time. Help me turn this idea into an experiment in this project: flat paper, accordion-folded paper, and crumpled paper, three trials of each, with an iPhone recording and a nominal drop height of 3 ft 10 in, approximately 1.17 m. Use our prepared protocol as the basis. Find relevant sources using the tools actually available, save only retrieved material, and distinguish source findings from assumptions. Save a testable hypothesis and an experiment plan. Measure elapsed time from release to first floor contact. Treat paper dimensions, matching stock/mass, and exact release alignment as unconfirmed where not supplied. Do not claim randomized collection or a calibrated height. Explain what a simplified drag model can test and what needs real observations. Keep the outcome open.

Hold a genuine response and saved plan. If the agent makes assumptions inconsistent with the files, correct the actual plan before launch and retain that correction. Do not regenerate repeatedly to obtain predetermined findings.

## Prompt 2: simulation

Replace the experiment identifier with the actual saved identity, not a guessed title.

> For experiment [EXPERIMENT_ID], prepare a reproducible vertical-fall simulation with gravity and quadratic drag. Include a no-drag baseline and an explicit range of assumed effective drag-to-mass values. Use 1.1684 m only as the numerical representation of the nominal user-reported height, not as a claim of measurement precision. Do not assign arbitrary model coefficients as measured properties of our paper shapes. Save the implementation to this existing experiment through the supported script workflow. Label all simulation outputs and preserve assumptions. Do not execute until I launch the run. Tell me if a dependency or required capability is missing.

Launch through the real supported UI and capture its generated figure. Preserve the simulation code, run and inputs. If the simulation uses ideal point-mass clearance, disclose the difference from a finite sheet and uncertain release reference. The timing-only observation does not require a spatial calibration, but any metre-valued app outputs must obey the app's calibration contract. Do not bypass validation to get an attractive chart.

## Upload and exact evidence selection

Complete uploads for all nine original MOVs. Record the map from original filename and SHA-256 to returned project artifact ID. Attach them to the intended experiment and save. Attach the height PNG as supporting reference and do not pass it as a tenth trial. Simulation artifacts are separate.

Before a scientific run, record its accepted experiment ID/revision, code artifact, selected input artifact IDs, parameters, and runtime. Verify that all selected trial IDs map to these supplied originals. Resolve rotation/decoding support before measurement. Chat attachment alone does not supply evidence to the in-app agent.

## Event annotation and observed analysis

For each original, inspect the last supported/first unsupported frames and last airborne/first floor-contact frames using presentation timestamps. Save frame references and event brackets in an annotation dataset. This can be manual, and the video must label it accordingly. The brief's source trims are not annotations. No model should guess measurements from a filename or an unsupported video attachment.

If frame extraction or annotation must happen outside Stellaris, import that dataset with explicit provenance and show the actual import rather than implying native automatic tracking. If there is no viable paper-analysis path, stop production of success scenes and report the gap. A ball pipeline cannot measure paper fall times.

Suggested script request if the implementation needs the app agent:

> For existing experiment [EXPERIMENT_ID], prepare an analysis of the nine supplied trial originals [VERIFIED_ARTIFACT_IDS] and their saved event annotations [ANNOTATION_ARTIFACT_ID]. Use timestamp brackets for release and first contact. Save each central fall-time estimate, timing bounds, shape, trial identifier, file reference, and ambiguity flags. Plot individual trial points and shape means, with trial spread clearly distinguished from measurement uncertainty. Account for every trial. Do not invent missing times or infer a precise drag coefficient. Use the supported custom analysis workflow and preserve the earlier simulation run. Do not execute until I launch it.

If an adequate script is already prepared and locally checked, use the actual Run action instead of an unnecessary extra model request. Selection and immutable inputs still need verification.

## Prompt 3: evidence-grounded interpretation

> Analyze the saved observed run [OBSERVED_RUN_ID] for experiment [EXPERIMENT_ID], the original video evidence and event annotations, the simulation [SIMULATION_RUN_ID], and our genuinely retrieved sources. Evaluate the hypothesis and explain measured differences, trial variability, uncertainty, and alternative explanations. Separate direct observations, reproducible calculations, and AI interpretation. Discuss the nominal phone-assisted height, release/orientation differences, grouped collection, and the small three-trial sample. Explain where a constant-drag model is inadequate if the evidence shows that. Do not describe fitted values as independent predictions or assume the paper masses were weighed. Cite exact saved evidence, give an inconclusive assessment if appropriate, and save the Markdown report.

## Capture manifest and claim review

For every app excerpt save source recording path, source in/out time, request/action identity, actual run/artifact links, and final-video scene. Use one project throughout. Full waiting periods stay in source recordings. Cut them in the edit without replacing the response.

Replace report placeholders only after checking numerical callouts against saved calculations. Do not reuse the prior video's people dataset, equation, error reduction, counts, or report finding. Provider/model and execution cards must agree with the actual captured session. Keep credentials and `.env` out of all recording and review material.
