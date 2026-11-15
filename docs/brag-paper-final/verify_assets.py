"""Verify only the explicit video-handoff assets using the standard library."""

import hashlib
import json
from pathlib import Path


def main():
    repository = Path(__file__).resolve().parents[2]
    manifest = json.loads(Path(__file__).with_name("asset-manifest.json").read_text(encoding="utf-8"))
    assets = manifest["assets"] + manifest.get("reference_assets", [])
    for asset in assets:
        path = (repository / asset["path_from_repo_root"]).resolve()
        if not path.is_relative_to(repository):
            raise ValueError("Asset path escapes the checkout")
        content = path.read_bytes()
        if len(content) != asset["bytes"]:
            raise ValueError(f"Size mismatch: {asset['filename']}")
        if hashlib.sha256(content).hexdigest() != asset["sha256"]:
            raise ValueError(f"Hash mismatch: {asset['filename']}")

    trials = [a for a in manifest["assets"] if a["role"] == "observed_trial_original"]
    if len(trials) != 9:
        raise ValueError("Expected nine trial originals")
    for condition in ("flat", "folded", "crumpled"):
        if sum(a["condition"] == condition for a in trials) != 3:
            raise ValueError(f"Expected three trials for {condition}")

    previous_end = 0
    output = manifest["output"]
    for scene in manifest["scenes"]:
        if scene["start_s"] != previous_end or scene["end_s"] <= scene["start_s"]:
            raise ValueError("Timeline has a gap, overlap, or empty scene")
        if scene["start_frame"] != scene["start_s"] * output["fps"]:
            raise ValueError("Incorrect start frame")
        if scene["end_frame_exclusive"] != scene["end_s"] * output["fps"]:
            raise ValueError("Incorrect end frame")
        previous_end = scene["end_s"]
    if previous_end != output["duration_s"] or output["frames"] != previous_end * output["fps"]:
        raise ValueError("Output duration or frame count mismatch")

    durations = {a["filename"]: a["container_duration_s_reported_rounded"] for a in trials}
    for window in manifest["featured_editorial_windows_not_measurement_events"]:
        if not 0 <= window["source_in_s"] < window["source_out_s"] <= durations[window["filename"]]:
            raise ValueError("Featured window is outside its source")
        duration = (window["source_out_s"] - window["source_in_s"]) / window["speed"]
        duration += window["pre_hold_s"] + window["post_hold_s"]
        if abs(duration - (window["scene_end_s"] - window["scene_start_s"])) > 1e-8:
            raise ValueError("Featured window does not fit its slot")
    print(f"Verified {len(assets)} asset hashes, nine trials, and {output['duration_s']} seconds / {output['frames']} frames.")


if __name__ == "__main__":
    main()
