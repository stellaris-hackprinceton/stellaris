"""Provider-free boundary checks for report calculation input validation.

Run from the API image with ``python scripts/check_report_calculations.py``. These checks
do not start Docker or execute user code. The report-calculation worker path needs a separate
Docker integration check.
"""

from types import SimpleNamespace

from stellaris_api.errors import ApiError
from stellaris_api.report_calculations import execute_calculation


def rejects(call, code):
    try:
        call()
    except ApiError as exc:
        assert exc.code == code, (exc.code, exc.message)
    else:
        raise AssertionError(f"expected {code}")


ctx = SimpleNamespace(snapshot={"evidence_runs": [{"id": "run-selected"}]}, cancel_requested=lambda: False)
evidence = [{"run": {"id": "run-selected"}, "snapshot": {}, "artifacts": []}]
rejects(lambda: execute_calculation(ctx, "", [], evidence), "VALIDATION_FAILED")
rejects(lambda: execute_calculation(ctx, "x" * (256 * 1024 + 1), [], evidence), "VALIDATION_FAILED")
rejects(lambda: execute_calculation(ctx, "\ud800", [], evidence), "VALIDATION_FAILED")
rejects(lambda: execute_calculation(ctx, "print(1)", ["a", "a"], evidence), "VALIDATION_FAILED")
rejects(lambda: execute_calculation(ctx, "print(1)", ["a"],
                                     [{"run": {"id": "other"}, "snapshot": {}, "artifacts": []}]),
        "VALIDATION_FAILED")
print("PASS: report calculation source limits, duplicate inputs, and report evidence scoping")
