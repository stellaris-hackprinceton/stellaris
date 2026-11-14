#!/usr/bin/env python3
"""Focused regression checks for malformed, untrusted worker result JSON.

Run from the repository root with:

    python3 backend/scripts/check_worker_validation.py
"""

import json
import os
import sys

API_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api")
sys.path.insert(0, API_DIR)

from stellaris_api.analysis import (InvalidOutput, _validate_evidence_anchors,
                                    validate_result)  # noqa: E402


def empty_result():
    return {"measurements": [], "claims": [], "artifacts": [], "warnings": []}


def measurement(**changes):
    item = {
        "local_key": "m1", "series": "track", "quantity": "height", "value": 1.0, "unit": "px",
        "time_s": None, "uncertainty": {"absolute": None, "method": None}, "status": "valid",
        "evidence": [{"artifact": {"input_artifact_id": "input-1"}, "frame_index": None,
                      "time_s": None, "row_index": None}],
        "calibration_mode": "none", "data_origin": "observed", "assumptions": [],
    }
    return {**item, **changes}


def artifact(**changes):
    item = {"local_key": "a1", "path": "data.csv", "kind": "dataset", "origin": "generated",
            "mime_type": "text/csv", "parents": []}
    return {**item, **changes}


def expect_invalid(label, result, files=None):
    raw = json.dumps(result, allow_nan=True).encode("utf-8")
    try:
        validate_result(raw, files or {}, {}, input_ids={"input-1"}, calibration_mode="none",
                        simulated=False, source_ids=set())
    except InvalidOutput:
        print(f"ok: {label}")
    else:
        raise AssertionError(f"{label}: expected InvalidOutput")


def expect_bad_anchors(label, result, inputs, outputs, row_counts):
    try:
        _validate_evidence_anchors(result, inputs, outputs, row_counts)
    except InvalidOutput:
        print(f"ok: {label}")
    else:
        raise AssertionError(f"{label}: expected InvalidOutput")


def main():
    bad_ref = empty_result()
    bad_ref["measurements"] = [measurement(evidence=[{"artifact": {"input_artifact_id": []},
                                                     "frame_index": None, "time_s": None, "row_index": None}])]
    expect_invalid("array artifact reference", bad_ref)

    bad_parent = empty_result()
    bad_parent["artifacts"] = [artifact(parents=[{"output_artifact_key": {}}])]
    expect_invalid("object artifact parent reference", bad_parent, {"data.csv": "/unused"})

    expect_invalid("array measurement unit", {**empty_result(), "measurements": [measurement(unit=[])]})
    expect_invalid("object artifact MIME type", {**empty_result(), "artifacts": [artifact(mime_type={})]},
                   {"data.csv": "/unused"})

    nonfinite = empty_result()
    nonfinite["measurements"] = [measurement(value=float("inf"))]
    expect_invalid("non-finite measurement", nonfinite)

    giant_integer = empty_result()
    giant_integer["measurements"] = [measurement(value=10**1000)]
    expect_invalid("giant integer measurement", giant_integer)

    input_video = {"id": "input-1", "kind": "video", "mime_type": "video/mp4",
                   "metadata": {"frame_count": 10, "duration_ms": 1000}, "parent_artifact_ids": []}
    media_bad = empty_result()
    media_bad["measurements"] = [measurement(evidence=[{"ref": ("input", "input-1"), "frame_index": 10,
                                                         "time_s": 0.1, "row_index": None}])]
    expect_bad_anchors("frame index beyond input video", media_bad, {"input-1": input_video}, [], {})

    output_csv = artifact(parents=[("input", "input-1")], metadata={}, row_count=2)
    row_bad = empty_result()
    row_bad["measurements"] = [measurement(evidence=[{"ref": ("output", "a1"), "frame_index": None,
                                                       "time_s": None, "row_index": 2}])]
    expect_bad_anchors("row index beyond output CSV", row_bad, {"input-1": input_video}, [output_csv], {})

    json_dataset = artifact(mime_type="application/json", parents=[], row_count=None)
    json_bad = empty_result()
    json_bad["measurements"] = [measurement(evidence=[{"ref": ("output", "a1"), "frame_index": None,
                                                        "time_s": None, "row_index": 0}])]
    expect_bad_anchors("JSON dataset does not accept row indexes", json_bad, {}, [json_dataset], {})


if __name__ == "__main__":
    main()
