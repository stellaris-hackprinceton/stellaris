# Experiment pipeline mismatch: test1 and test2

Status: diagnosed on 2026-11-14. No live model requests made for this investigation.

## Observed failures

The project named `test` was found as `test1` in the running API. These existing public run
records were inspected directly; no old application log files were used.

| Project | Experiment | Run | Submitted pipeline | Target hint | Failure |
|---|---|---|---|---|---|
| test1 | Simple number counting on fingers | `run_9ab8eede2a014fc19b23025f37968cbd` | `bouncing_ball_v1` | `hand` | No bounce apex heights |
| test1 | Simple number counting on fingers | `run_57486da4205e48948d69a4941017a408` | `bouncing_ball_v1` | `hand` | Only one bounce apex height |
| test2 | Extracting a Small Set of Hand Gestures from Webcam Video | `run_9c81db9066df4865b63fa6994ca4bcdb` | `bouncing_ball_v1` | `hand` | No bounce apex heights |

The errors are `INSUFFICIENT_EVIDENCE`. The runs preserve partial outputs; they must remain
failed rather than be relabeled or overwritten.

## Confirmed cause

- `frontend/features/studio/launch/AnalysisSetup.tsx` always submits
  `pipeline: "bouncing_ball_v1"`, with `code_artifact_id: null`.
- `AnalysisLaunchSummary.tsx` also hardcodes that pipeline label. The UI offers an editable
  "Object to track" field, creating the impression that changing it changes the detector.
- The backend accepts an arbitrary nonempty `object_hint` for the bouncing-ball pipeline.
- `backend/worker/bouncing_ball_v1.py` reads `object_hint` and records it in output metadata,
  but it does not select a detector or change the algorithm. It still measures bounce
  heights and energy ratios. Setting the hint to `hand` cannot count fingers or classify gestures.
- The research agent may propose broader camera experiments. A valid experiment plan does
  not mean a matching executable analysis pipeline exists.
- The backend already supports `python_analysis_v1` with a committed Python code artifact,
  but the current frontend launcher does not expose that path. The agent has no tool that
  publishes a custom analysis implementation for arbitrary plans.

This is a pipeline-selection/capability mismatch. Adjusting ball thresholds cannot make the
ball pipeline perform hand-pose estimation or finger counting.

## Repair choices

1. Small backend correction: reject unsupported bouncing-ball target hints before accepting
   or enqueueing a run, with a clear validation message directing the client to a matching
   analysis implementation. Document the built-in pipeline limits in capabilities and the
   shared contract, and clarify the agent's prompt. Preserve existing failed runs. This
   prevents misleading execution but does not implement gesture recognition.
2. Broader correction: design explicit pipeline selection and a custom-analysis/code
   workflow, then wire it into the frontend launcher. Gesture recognition still needs a
   real implementation, suitable dependencies and an evaluation dataset; it must not be
   presented as implemented merely because a plan was proposed.

The current backend-only instruction excludes frontend edits. The choice of strict target
validation changes which previously accepted requests are valid, so it needs an explicit
product/contract decision before implementation. The file-workspace implementation proceeds
independently.

## Clarification implementation note

Additive clarification only; the repair decision above remains pending.

- `/capabilities.execution.analysis_pipelines` is an optional list of descriptors
  (`id`, `description`, `requires_code_artifact`) for `bouncing_ball_v1` and
  `python_analysis_v1`. It is `[]` when workers are unavailable. `allowed_backends` is unchanged.
- The bouncing-ball descriptor states that the object hint does not select a detector.
- The agent's experiment-scope prompt now states the built-in pipeline's limits and that a plan
  is not an executable analysis without a matching `python_analysis_v1` implementation.
- No validation guard, required field, frontend change, or analysis algorithm was added.
  Previously accepted requests are still accepted, and the FAILED runs above are unchanged.
