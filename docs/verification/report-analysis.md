# Agent-led report analysis verification

November 14, 2026. Canonical requirements: [Reports](../reports-spec.md#required-agent-led-analysis).

Status: **Implementation accepted by the user.** The follow-ups below remain recorded
and do not block delivery.

## Implemented behavior

New report runs call the configured LangChain Deep Agent in the project's container.
The agent reads accepted experiment snapshots, measurements, claims, source content,
warnings, and failures through bounded tools. Its instructions require hypothesis
evaluation, meaningful comparisons, contradictions, alternative explanations, and
explicitly inconclusive conclusions when evidence is insufficient.

Saved Markdown places AI interpretation before the original scientific record.
Observations, computed datasets, and AI interpretation remain distinct. A calculation
publishes immutable Python source and a JSON evidence dataset, then executes a child
analysis in the existing network-disabled worker. It does not change the experiment
or publish new scientific measurements/claims. It uses recorded units rather than
inheriting a camera conversion from the first evidence run.

The backend validates required evidence reads and structured result references.
Provenance records model/runtime identity, evidence-page hashes, limitations, and
calculation runs. Incrementally committed logs preserve that audit trail if the API
restarts before final provenance publication. Interrupted report agent processes use
the existing run-specific orphan cleanup. Provider failure and cancellation do not
publish a deterministic replacement. Existing saved reports remain readable.

## Checks actually run

- API, project-runtime, and worker Docker images built successfully.
- `report_runtime_test.py` passed inside a disposable network-disabled project-runtime
  image. It exercises the real Deep Agents graph with a fixture model, evidence-tool
  dispatch, restricted tools, final JSON extraction, and exclusion of reasoning blocks.
- `check_report_analysis.py --docker` passed inside an API image with no provider
  credentials. It exercises evidence scoping, required reads, bad references, omitted
  pages, insufficient measurements, partial failures, simulation, missing calibration,
  historical rendering, and the real event/tool stream parser with fixture transport.
- The same script saved a report and provenance through real project-volume storage
  with a fixture agent response. Simulated provider failure, absent configuration,
  and cancellation produced no report artifact. Failed analysis retained its evidence
  read audit. This is persistence/orchestration verification, not live model reasoning.
- A real isolated Python calculation read the saved simulated evidence dataset and
  saved its computed output with code, input, and execution provenance. The experiment
  record remained unchanged. Final integration project:
  `prj_2471988971c14dd88cbc782fb504072c`. Test containers were stopped and data preserved.
- `check_report_calculations.py` passed for source bounds, duplicate IDs, and evidence
  selection boundaries. Existing worker-output validation checks passed.
- Python compilation and `git diff --check` passed.
- Recreated the idle local API and reconciled active project runtimes to the new image.
  Compose reported the API and frontend healthy. The current capability response reports
  `model_configured: false` and `markdown_reports: false`, so new generation remains
  disabled until the user supplies valid runtime model configuration.

The test fixtures and fixture responses are simulated and do not establish scientific
results. Test tools never inspected `.env` files or host credential profiles.

## Remaining limits

### Recorded follow-ups

- [ ] Evaluate real report narratives once runtime model configuration is available.
- [ ] Revisit narrative grounding and citation coverage after live usage. Structural
  validation checks supplied record IDs and required evidence reads, but does not
  establish scientific correctness or claim-by-claim citation support. A synthetic
  adversarial fixture passed validation while falsely describing failed, simulated,
  uncalibrated evidence as a proven physical result. This was injected test text,
  not actual model output. The user accepted this limitation and did not require
  additional hallucination guards for delivery.

### Verification boundaries

No live Bedrock or other model request was made for this feature. Real hypothesis
reasoning, contradictory-run interpretation, numerical grounding, and source use still
require live-provider evaluation against reviewed evidence. Structural validation
cannot independently establish that an AI conclusion is scientifically correct.

Evidence pages and saved full-text excerpts are bounded. Missing pages and truncated
or unavailable source/calculation text become report limitations. A report with an
oversized indivisible evidence record fails rather than pretending that it was read.
Live restart stress testing and browser inspection were not performed in this pass.
The frontend uses its existing immutable Markdown reader and report-run controls.
The older general `agent_runtime_test.py` was stopped after its experiment fixture
waited on the synchronous backend tool protocol. That legacy fixture still expects
fire-and-forget proposals. It was not counted as a passed regression check. The new
report-specific Deep Agents graph and stream tests passed independently.

`pipeline_test.py` requires `--live-reports` to request report generation. Its default
path does not make model calls. That option requires separate live-provider authorization.
