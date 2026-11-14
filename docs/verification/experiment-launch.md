# Experiment launch selection verification

Verified November 14, 2026 against the local Compose application. This checks software behavior using explicitly simulated input data. It does not establish scientific findings.

## Corrected behavior

The frontend previously submitted `bouncing_ball_v1` for every experiment launch and silently substituted `ball` for an empty object hint. Launch configuration now begins with no analysis method selected. Users explicitly choose the built-in ball tracker or the existing `python_analysis_v1` path. Python analysis executes a selected uploaded script against selected saved-plan inputs. It does not generate code from the experiment plan.

The launch summary reflects the chosen method, input filenames, code artifact, parameters, and saved plan revision. Unsaved or stale plans remain blocked. An ambiguous submission retains its original request and idempotency key. Its configuration stays disabled until retry or dismissal.

Python upload normalization applies both to the upload declaration and the transferred Blob's media type. Browsers reporting `.py` files as plain text or an unknown type no longer cause a declaration/transfer mismatch. The backend still validates the uploaded bytes.

Studio's inner columns now depend on the available workspace width. A desktop window with the right-hand chat open can stack the plan and launch panels rather than squeezing them into narrow columns. The broader visual direction in the frontend specification remains proposed.

## Checks completed

- Nine Node tests passed, including the existing HTTP/session checks and Python upload media-type regression checks.
- TypeScript checking and targeted ESLint checks passed for the changed frontend code.
- The frontend production Docker build passed. The updated frontend was started through Compose and became healthy.
- An isolated, agent-installed Chromium browser under `C:/tmp/stellaris-rework/` verified that no method is preselected and that launch is initially disabled.
- A `.py` file reported by the browser as `text/plain` was uploaded and attached through the real API. The backend stored it as a Python code artifact.
- Invalid array parameters were rejected in the interface. Valid JSON object parameters, the selected code, and a simulated CSV input enabled launch.
- The first launch request was deliberately interrupted before reaching the backend. Configuration became disabled. Manual retry reused the identical body and idempotency key.
- The real retried request selected `python_analysis_v1`, the intended experiment and saved revision, the selected CSV input, the uploaded code artifact, and the supplied JSON parameters. It contained no ball-tracking parameters.
- The real isolated worker executed the uploaded verification script successfully. The script checked its manifest and returned no scientific measurements, claims, or data artifacts, with an explicit verification-only warning.
- At 1440 pixels, chat remained on the right and Studio's inner panels stacked within the constrained center. At 390 pixels, launch controls remained reachable without document overflow. Screenshots were visually inspected. The desktop capture was repeated from the document top to avoid a misleading full-page rendering of sticky elements at a retained scroll position.

## Evidence and limits

The dedicated local project is `TEST launch selection regression`. Its successful test run is `run_a01382be64e04459990eb18c7779af90`. Test files, the isolated browser, screenshots, and the request-checking harness remain outside Git under `C:/tmp/stellaris-rework/`.

No model-provider request was made. This pass did not rerun the bouncing-ball scientific pipeline, test physical camera capture, or perform a comprehensive accessibility audit. It verifies explicit method selection, the generic Python launch, upload handling, retry identity, and the specified responsive layout behavior. Existing API schemas and worker isolation were retained.
