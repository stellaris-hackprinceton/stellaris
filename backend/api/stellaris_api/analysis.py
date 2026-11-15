"""Analysis runs: bouncing_ball_v1 and python_analysis_v1 in isolated workers.

Flow per run (executor thread):
  1. Code: bouncing_ball_v1 publishes the exact pipeline source from the accepted snapshot as
     an immutable `code` artifact before execution; python_analysis_v1 uses the selected,
     already immutable code artifact.
  2. Inputs are streamed from the project volume into a tar archive and verified against the
     snapshot's sha256 and size (a mismatch fails the run; nothing unverified is executed).
     /input/manifest.json carries artifact IDs, hashes, worker-local paths, the experiment
     and calibration snapshot, and parameters.
  3. worker.run_worker() executes `python -I /input/artifacts/<code_artifact_id>`.
  4. /output/result.json is untrusted: validate_result() enforces the section 10 schema and
     evidence rules. Output files are staged (hashed + media-inspected by the backend) and,
     with measurements, claims, logs, and the provenance manifest, committed in one
     transaction by RunContext.finish().
A worker-reported INSUFFICIENT_EVIDENCE warning fails the run (INSUFFICIENT_EVIDENCE) while
keeping its committed partial evidence.
"""

import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
import threading
import time

from docker.errors import DockerException

from . import approvals, hpc, worker
from .db import transaction
from .artifacts import filename_error
from .errors import ApiError
from .executor import RunFailure
from .http import dumps, new_id, now_ts, strict_loads
from .media import ARTIFACT_KINDS, TYPES
from .research import publish_claim
from .runtime import ArtifactMissing, RuntimeUnavailable
from .validation import is_finite, is_int

log = logging.getLogger(__name__)

RESULT_KEYS = {"measurements", "claims", "artifacts", "warnings"}
ARTIFACT_KEYS = {"local_key", "path", "kind", "origin", "mime_type", "parents"}
MEASUREMENT_KEYS = {"local_key", "series", "quantity", "value", "unit", "time_s", "uncertainty", "status", "evidence",
                    "calibration_mode", "data_origin", "assumptions"}
CLAIM_KEYS = {"local_key", "kind", "text", "measurement_keys", "citations", "evidence", "assumptions", "limitations"}
EVIDENCE_KEYS = {"artifact", "frame_index", "time_s", "row_index"}
LOCAL_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
PATH_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
WARNING_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
UNITS = {"px", "s", "m", "m/s", "m/s^2", "1", "px/s", "px/s^2"}
# Script analyses of uploaded tables may keep the source columns' own short unit labels
# (for example "in", "lb", "kg/m^2", "%"); assumptions must still state them.
TABULAR_UNIT = re.compile(r"^[A-Za-z0-9%/^*().\-]{1,32}$")
METRIC_UNITS = {"m", "m/s", "m/s^2"}
WORKER_ARTIFACT_ORIGINS = {"derived", "simulated", "generated"}
RESERVED_OUTPUTS = {"result.json", "provenance.json"}
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_WORKER_PROVENANCE_BYTES = 1024 * 1024
MAX_DATASET_ROWS = 1_000_000
LIMITS = {"measurements": 5000, "claims": 100, "artifacts": 200, "warnings": 100, "evidence": 50, "strings": 50,
          "parents": 50}
EXECUTION_FAILURES = {
    "cancelled": None,
    "timeout": ("EXECUTION_TIMEOUT", False),
    "resource_limit": ("RESOURCE_LIMIT_EXCEEDED", False),
    "failed": ("WORKER_FAILED", False),
    "output_rejected": ("INVALID_OUTPUT", False),
}


class InvalidOutput(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


# -- result validation ---------------------------------------------------------------

def _strings(errors, value, path, *, max_items=LIMITS["strings"], max_len=2000, nonempty=False):
    if not isinstance(value, list) or len(value) > max_items or not all(
            isinstance(s, str) and 0 < len(s) <= max_len for s in value):
        errors.append(f"{path} must be an array of at most {max_items} nonempty strings (<= {max_len} chars)")
        return []
    if nonempty and not value:
        errors.append(f"{path} must not be empty")
    return list(value)


def _ref(errors, ref, path, input_ids, output_keys):
    if not isinstance(ref, dict) or len(ref) != 1:
        errors.append(f"{path} must be {{input_artifact_id}} or {{output_artifact_key}}")
        return None
    if "input_artifact_id" in ref:
        artifact_id = ref["input_artifact_id"]
        if not isinstance(artifact_id, str) or artifact_id not in input_ids:
            errors.append(f"{path} references an artifact that is not a declared input of this run")
            return None
        return ("input", artifact_id)
    if "output_artifact_key" in ref:
        artifact_key = ref["output_artifact_key"]
        if not isinstance(artifact_key, str) or artifact_key not in output_keys:
            errors.append(f"{path} references an unknown output artifact key")
            return None
        return ("output", artifact_key)
    errors.append(f"{path} must be {{input_artifact_id}} or {{output_artifact_key}}")
    return None


def _evidence(errors, items, path, input_ids, output_keys, *, required):
    if not isinstance(items, list) or len(items) > LIMITS["evidence"]:
        errors.append(f"{path} must be an array of at most {LIMITS['evidence']} evidence references")
        return []
    if required and not items:
        errors.append(f"{path} is empty: every measurement must link to evidence")
    out = []
    for i, ev in enumerate(items):
        p = f"{path}/{i}"
        if not isinstance(ev, dict) or set(ev) != EVIDENCE_KEYS:
            errors.append(f"{p} must have exactly the keys {sorted(EVIDENCE_KEYS)}")
            continue
        ref = _ref(errors, ev["artifact"], f"{p}/artifact", input_ids, output_keys)
        for key in ("frame_index", "row_index"):
            if not (ev[key] is None or (is_int(ev[key]) and ev[key] >= 0)):
                errors.append(f"{p}/{key} must be a nonnegative integer or null")
        if not (ev["time_s"] is None or (is_finite(ev["time_s"]) and ev["time_s"] >= 0)):
            errors.append(f"{p}/time_s must be a finite nonnegative number or null")
        if ref:
            out.append({"ref": ref, "frame_index": ev["frame_index"], "time_s": ev["time_s"],
                        "row_index": ev["row_index"]})
    return out


def _normalize_path(errors, path, p):
    if not isinstance(path, str) or not 0 < len(path) <= 255:
        errors.append(f"{p}/path must be a relative path string")
        return None
    parts = path.split("/")
    if path.startswith("/") or len(parts) > 4 or not all(PATH_SEGMENT.match(s) for s in parts):
        errors.append(f"{p}/path {path!r} must be a relative path of up to 4 plain segments (no '..', no absolute paths)")
        return None
    if path in RESERVED_OUTPUTS:
        errors.append(f"{p}/path {path!r} is reserved")
        return None
    return path


def validate_result(raw: bytes, files: dict, rejected: dict, *, input_ids: set, calibration_mode: str,
                    simulated: bool, source_ids: set, tabular_units: bool = False):
    """Validate an untrusted worker result. Returns a normalized dict; raises InvalidOutput."""
    errors, notes = [], []
    if len(raw) > MAX_RESULT_BYTES:
        raise InvalidOutput([f"result.json exceeds {MAX_RESULT_BYTES} bytes"])
    try:
        result = strict_loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise InvalidOutput([f"result.json is not valid UTF-8 JSON with finite numbers ({exc})"])
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise InvalidOutput([f"result.json must be an object with exactly the keys {sorted(RESULT_KEYS)}"])
    for key in RESULT_KEYS:
        if not isinstance(result[key], list) or len(result[key]) > LIMITS[key]:
            errors.append(f"/{key} must be an array of at most {LIMITS[key]} items")
    if errors:
        raise InvalidOutput(errors)

    # Artifacts.
    arts, keys, paths = [], set(), set()
    for i, a in enumerate(result["artifacts"]):
        p = f"/artifacts/{i}"
        if not isinstance(a, dict) or set(a) != ARTIFACT_KEYS:
            errors.append(f"{p} must have exactly the keys {sorted(ARTIFACT_KEYS)} (no public IDs)")
            continue
        if not isinstance(a["local_key"], str) or not LOCAL_KEY.match(a["local_key"]) or a["local_key"] in keys:
            errors.append(f"{p}/local_key must be a unique key matching {LOCAL_KEY.pattern}")
            continue
        keys.add(a["local_key"])
        path = _normalize_path(errors, a["path"], p)
        if path is not None:
            if path in paths:
                errors.append(f"{p}/path {path!r} is declared twice")
            elif path in rejected:
                errors.append(f"{p}/path {path!r} is a {rejected[path]}, not a regular file")
            elif path not in files:
                errors.append(f"{p}/path {path!r} does not exist in the output directory")
            paths.add(path)
        mime, kind, origin = a["mime_type"], a["kind"], a["origin"]
        if (not isinstance(mime, str) or not isinstance(kind, str) or mime not in TYPES
                or kind not in ARTIFACT_KINDS or kind == "report" or kind not in TYPES.get(mime, (None, None, None, ()))[3]):
            errors.append(f"{p} kind {kind!r} with mime_type {mime!r} is not an allowed worker output")
        if not isinstance(origin, str) or origin not in WORKER_ARTIFACT_ORIGINS:
            errors.append(f"{p}/origin must be one of {sorted(WORKER_ARTIFACT_ORIGINS)} (workers cannot produce "
                          f"observed or reference material)")
        elif simulated and kind != "code" and origin != "simulated":
            notes.append(f"Output {a['local_key']!r} was relabelled from {origin!r} to 'simulated' because the run's "
                         "inputs are simulated.")
            origin = "simulated"
        filename = path.split("/")[-1] if path else None
        if filename and filename_error(filename):
            errors.append(f"{p}/path has an invalid file name")
        if not isinstance(a["parents"], list) or len(a["parents"]) > LIMITS["parents"]:
            errors.append(f"{p}/parents must be an array of at most {LIMITS['parents']} references")
            continue
        arts.append({"local_key": a["local_key"], "path": path, "kind": kind, "origin": origin, "mime_type": mime,
                     "raw_parents": a["parents"], "filename": filename})
    for art in arts:
        art["parents"] = [r for j, ref in enumerate(art.pop("raw_parents"))
                          if (r := _ref(errors, ref, f"/artifacts/{art['local_key']}/parents/{j}", input_ids, keys))]
    order = _topological(errors, arts)

    # Measurements.
    measurements, mkeys = [], set()
    for i, m in enumerate(result["measurements"]):
        p = f"/measurements/{i}"
        if not isinstance(m, dict) or set(m) != MEASUREMENT_KEYS:
            errors.append(f"{p} must have exactly the keys {sorted(MEASUREMENT_KEYS)} (no public IDs)")
            continue
        if not isinstance(m["local_key"], str) or not LOCAL_KEY.match(m["local_key"]) or m["local_key"] in mkeys:
            errors.append(f"{p}/local_key must be unique and match {LOCAL_KEY.pattern}")
            continue
        mkeys.add(m["local_key"])
        for key in ("series", "quantity"):
            if not isinstance(m[key], str) or not 0 < len(m[key]) <= 200:
                errors.append(f"{p}/{key} must be a string of 1-200 characters")
        if not isinstance(m["unit"], str) or not (m["unit"] in UNITS or (tabular_units and TABULAR_UNIT.match(m["unit"]))):
            errors.append(f"{p}/unit must be one of {sorted(UNITS)}"
                          + (" or a short source-column unit label such as 'in' or 'lb'" if tabular_units else ""))
        elif tabular_units and m["unit"] not in UNITS and not m["assumptions"]:
            errors.append(f"{p}/assumptions must state the source column and its unit")
        elif m["unit"] in METRIC_UNITS and calibration_mode != "reference_length" and not tabular_units:
            errors.append(f"{p}/unit {m['unit']!r} needs a physical scale, but the run's calibration mode is 'none'")
        if m["calibration_mode"] != calibration_mode:
            errors.append(f"{p}/calibration_mode must equal the run snapshot's mode ({calibration_mode!r})")
        status = m["status"]
        assumptions = _strings(errors, m["assumptions"], f"{p}/assumptions")
        if tabular_units and m["unit"] in METRIC_UNITS and not assumptions:
            errors.append(f"{p}/assumptions must state the source units and any tabular conversion")
        if status == "valid":
            if not is_finite(m["value"]):
                errors.append(f"{p}/value must be a finite number for a valid measurement")
        elif status in ("missing", "rejected"):
            if m["value"] is not None:
                errors.append(f"{p}/value must be null for a {status} measurement")
            if not assumptions:
                errors.append(f"{p}/assumptions must explain why the measurement is {status}")
        else:
            errors.append(f"{p}/status must be valid, missing, or rejected")
        if not (m["time_s"] is None or is_finite(m["time_s"])):
            errors.append(f"{p}/time_s must be finite or null")
        unc = m["uncertainty"]
        if not isinstance(unc, dict) or set(unc) != {"absolute", "method"}:
            errors.append(f"{p}/uncertainty must be {{absolute, method}}")
        else:
            if not (unc["absolute"] is None or (is_finite(unc["absolute"]) and unc["absolute"] >= 0)):
                errors.append(f"{p}/uncertainty/absolute must be a finite nonnegative number or null")
            if not (unc["method"] is None or (isinstance(unc["method"], str) and 0 < len(unc["method"]) <= 2000)):
                errors.append(f"{p}/uncertainty/method must be a string or null")
            if unc["absolute"] is not None and unc["method"] is None:
                errors.append(f"{p}/uncertainty/method is required when an uncertainty is given")
        data_origin = m["data_origin"]
        if data_origin not in ("observed", "derived", "simulated"):
            errors.append(f"{p}/data_origin must be observed, derived, or simulated")
        elif simulated and data_origin != "simulated":
            notes.append(f"Measurement {m['local_key']!r} was relabelled as simulated because the run's inputs are simulated.")
            data_origin = "simulated"
        evidence = _evidence(errors, m["evidence"], f"{p}/evidence", input_ids, keys, required=True)
        measurements.append({**{k: m[k] for k in ("local_key", "series", "quantity", "unit", "time_s", "status")},
                             "value": m["value"], "uncertainty": unc, "data_origin": data_origin,
                             "assumptions": assumptions, "evidence": evidence})

    # Claims.
    claims, ckeys = [], set()
    for i, c in enumerate(result["claims"]):
        p = f"/claims/{i}"
        if not isinstance(c, dict) or set(c) != CLAIM_KEYS:
            errors.append(f"{p} must have exactly the keys {sorted(CLAIM_KEYS)} (no public IDs)")
            continue
        if not isinstance(c["local_key"], str) or not LOCAL_KEY.match(c["local_key"]) or c["local_key"] in ckeys:
            errors.append(f"{p}/local_key must be unique and match {LOCAL_KEY.pattern}")
            continue
        ckeys.add(c["local_key"])
        if c["kind"] not in ("observation", "inference", "hypothesis"):
            errors.append(f"{p}/kind must be observation, inference, or hypothesis")
        if not isinstance(c["text"], str) or not 0 < len(c["text"].strip()) <= 10000:
            errors.append(f"{p}/text must be 1-10000 characters")
        mrefs = _strings(errors, c["measurement_keys"], f"{p}/measurement_keys", max_items=1000, max_len=100)
        for k in mrefs:
            if k not in mkeys:
                errors.append(f"{p}/measurement_keys references unknown measurement {k!r}")
        if not isinstance(c["citations"], list) or len(c["citations"]) > 100:
            errors.append(f"{p}/citations must be an array")
        else:
            for j, cit in enumerate(c["citations"]):
                if not isinstance(cit, dict) or set(cit) != {"source_id", "locator", "excerpt"}:
                    errors.append(f"{p}/citations/{j} must have exactly source_id, locator, excerpt")
                elif not isinstance(cit["source_id"], str) or cit["source_id"] not in source_ids:
                    errors.append(f"{p}/citations/{j} cites a source outside the run's accepted snapshot")
        evidence = _evidence(errors, c["evidence"], f"{p}/evidence", input_ids, keys, required=False)
        text = c["text"].strip() if isinstance(c["text"], str) else ""
        if simulated and "SIMULATED" not in text.upper():
            text = "[SIMULATED INPUT] " + text
        claims.append({"local_key": c["local_key"], "kind": c["kind"], "text": text, "measurement_keys": mrefs,
                       "citations": c["citations"] if isinstance(c["citations"], list) else [], "evidence": evidence,
                       "assumptions": _strings(errors, c["assumptions"], f"{p}/assumptions"),
                       "limitations": _strings(errors, c["limitations"], f"{p}/limitations")})

    warnings = []
    for i, w in enumerate(result["warnings"]):
        if (not isinstance(w, dict) or set(w) != {"code", "message"} or not isinstance(w["code"], str)
                or not WARNING_CODE.match(w["code"]) or not isinstance(w["message"], str) or not 0 < len(w["message"]) <= 2000):
            errors.append(f"/warnings/{i} must be {{code: UPPER_SNAKE, message: 1-2000 chars}}")
        else:
            warnings.append({"code": w["code"], "message": w["message"]})
    if errors:
        raise InvalidOutput(errors)
    by_key = {a["local_key"]: a for a in arts}
    return {"artifacts": [by_key[k] for k in order], "measurements": measurements, "claims": claims,
            "warnings": warnings, "notes": notes}


def _topological(errors, arts):
    graph = {a["local_key"]: [r[1] for r in a["parents"] if r[0] == "output"] for a in arts}
    order, state = [], {}

    def visit(key, depth=0):
        if state.get(key) == 2:
            return
        if state.get(key) == 1 or depth > len(graph):
            raise ValueError(key)
        state[key] = 1
        for parent in graph.get(key, []):
            visit(parent, depth + 1)
        state[key] = 2
        order.append(key)

    try:
        for key in graph:
            visit(key)
    except ValueError as exc:
        errors.append(f"output artifact parents form a cycle (involving {exc.args[0]!r})")
        return []
    return order


def _count_csv_rows(path: str):
    """Count CSV data rows (excluding the header), with a bounded scan."""
    try:
        count = 0
        with open(path, encoding="utf-8", newline="") as fh:
            for _ in csv.reader(fh):
                count += 1
                if count > MAX_DATASET_ROWS + 1:
                    return None
        return max(0, count - 1)
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


def _validate_evidence_anchors(result, input_artifacts, outputs, input_row_counts):
    """Reject anchors that cannot point into the referenced artifact or its media parent."""
    errors = []
    output_by_key = {a["local_key"]: a for a in outputs}

    def get(ref):
        kind, key = ref
        return input_artifacts.get(key) if kind == "input" else output_by_key.get(key)

    def parents(entry, is_input):
        if is_input:
            return [("input", aid) for aid in entry.get("parent_artifact_ids", []) if aid in input_artifacts]
        return entry.get("parents", [])

    def media_lineage(ref, visited=None):
        visited = set() if visited is None else visited
        if ref in visited:
            return []
        visited.add(ref)
        entry = get(ref)
        if entry is None:
            return []
        is_input = ref[0] == "input"
        if entry.get("kind") in ("video", "image"):
            return [entry]
        found = []
        for parent in parents(entry, is_input):
            found.extend(media_lineage(parent, visited))
        return found

    evidence_items = []
    for item in result["measurements"] + result["claims"]:
        evidence_items.extend(item["evidence"])
    for index, ev in enumerate(evidence_items):
        ref = ev["ref"]
        entry = get(ref)
        if entry is None:
            # The structural validator already reports unknown references.
            continue
        if ev["row_index"] is not None:
            if entry.get("kind") != "dataset" or entry.get("mime_type") != "text/csv":
                errors.append(f"evidence/{index}/row_index requires a CSV dataset artifact")
            else:
                if ref[0] == "input":
                    row_count = input_row_counts.get(ref[1])
                else:
                    row_count = entry.get("row_count")
                if row_count is None:
                    errors.append(f"evidence/{index}/row_index cannot be verified against a bounded CSV row count")
                elif ev["row_index"] >= row_count:
                    errors.append(f"evidence/{index}/row_index is outside the referenced CSV data rows")

        if ev["frame_index"] is not None or ev["time_s"] is not None:
            lineage = media_lineage(ref)
            video = next((a for a in lineage if a.get("kind") == "video"), None)
            image = next((a for a in lineage if a.get("kind") == "image"), None)
            if ev["frame_index"] is not None:
                if video is None and image is None:
                    errors.append(f"evidence/{index}/frame_index requires an image/video artifact or media-derived artifact")
                elif video is not None:
                    frame_count = video.get("metadata", {}).get("frame_count")
                    if frame_count is not None and ev["frame_index"] >= frame_count:
                        errors.append(f"evidence/{index}/frame_index is outside the source video's frames")
                elif ev["frame_index"] != 0:
                    errors.append(f"evidence/{index}/frame_index must be 0 for an image")
            if ev["time_s"] is not None:
                if video is not None:
                    duration_ms = video.get("metadata", {}).get("duration_ms")
                    if duration_ms is not None and ev["time_s"] * 1000 > duration_ms + 1:
                        errors.append(f"evidence/{index}/time_s is after the source video's duration")
                elif image is not None:
                    if ev["time_s"] != 0:
                        errors.append(f"evidence/{index}/time_s must be null or 0 for an image")
                else:
                    errors.append(f"evidence/{index}/time_s requires an image/video artifact or media-derived artifact")
    if errors:
        raise InvalidOutput(errors)


# -- execution -----------------------------------------------------------------------

def _hash_reader(reader, digest, mirror=None):
    class Reader:
        def read(self, n=-1):
            data = reader.read(n)
            digest.update(data)
            if mirror is not None and data:
                mirror.write(data)
            return data
    return Reader()


def _build_inputs(ctx, work_dir, code_doc, code_bytes):
    """Write the input tar and count bounded CSV data rows. Returns tar, manifest, row counts."""
    snap = ctx.snapshot
    entries = list(snap["inputs"])
    if code_doc is not None and code_doc["id"] not in {a["id"] for a in entries}:
        entries.append(code_doc)
    manifest = {
        "schema": "stellaris.worker_manifest.v1",
        "pipeline": snap["pipeline"]["name"], "pipeline_version": snap["pipeline"]["version"],
        "runtime": snap.get("runtime", "python"),
        "run_id": ctx.run_id,
        "experiment": {k: snap["experiment"][k] for k in ("id", "revision", "title", "hypothesis", "method",
                                                          "protocol_markdown", "variables", "success_criteria",
                                                          "limitations")},
        "calibration": snap["experiment"]["calibration"],
        "calibration_conversion": snap["calibration_conversion"],
        "parameters": snap["parameters"],
        "inputs": [{"artifact_id": a["id"], "kind": a["kind"], "mime_type": a["mime_type"], "origin": a["origin"],
                    "filename": a["filename"], "sha256": a["sha256"], "size_bytes": a["size_bytes"],
                    "metadata": a["metadata"], "path": f"/input/artifacts/{a['id']}"} for a in snap["inputs"]],
        "code": {"artifact_id": code_doc["id"], "sha256": code_doc["sha256"],
                 "path": f"/input/artifacts/{code_doc['id']}"},
        "sources": [],
        "output_dir": "/output", "result_path": "/output/result.json",
        "limits": snap["limits"],
    }
    tar_path = os.path.join(work_dir, "input.tar")
    input_row_counts = {}
    now = int(time.time())
    with tarfile.open(tar_path, mode="w", format=tarfile.PAX_FORMAT) as tar:
        directory = tarfile.TarInfo("artifacts")
        directory.type, directory.mode, directory.mtime = tarfile.DIRTYPE, 0o555, now
        tar.addfile(directory)
        for a in entries:
            member = tarfile.TarInfo(f"artifacts/{a['id']}")
            member.size, member.mode, member.mtime = a["size_bytes"], 0o444, now
            digest = hashlib.sha256()
            if code_bytes is not None and a["id"] == code_doc["id"]:
                tar.addfile(member, _hash_reader(io.BytesIO(code_bytes), digest))
            else:
                try:
                    size, reader, close = ctx.runtime.open_artifact(ctx.project_id, a["id"])
                except (RuntimeUnavailable, ArtifactMissing) as exc:
                    raise RunFailure("INPUT_UNAVAILABLE", f"Input artifact {a['id']} could not be read: {exc}", True)
                try:
                    if size != a["size_bytes"]:
                        raise RunFailure("INPUT_INTEGRITY_FAILED", f"Stored bytes of {a['id']} differ in size from the "
                                                                   "accepted snapshot.")
                    if a["mime_type"] == "text/csv":
                        row_path = os.path.join(work_dir, f"input-csv-{len(input_row_counts):03d}.tmp")
                        try:
                            with open(row_path, "wb") as mirror:
                                tar.addfile(member, _hash_reader(reader, digest, mirror))
                            input_row_counts[a["id"]] = _count_csv_rows(row_path)
                        finally:
                            try:
                                os.remove(row_path)
                            except FileNotFoundError:
                                pass
                    else:
                        tar.addfile(member, _hash_reader(reader, digest))
                finally:
                    close()
            if digest.hexdigest() != a["sha256"]:
                raise RunFailure("INPUT_INTEGRITY_FAILED", f"Stored bytes of {a['id']} do not match the sha256 "
                                                           "recorded in the accepted snapshot.")
        data = json.dumps(manifest, indent=1, allow_nan=False).encode("utf-8")
        member = tarfile.TarInfo("manifest.json")
        member.size, member.mode, member.mtime = len(data), 0o444, now
        tar.addfile(member, io.BytesIO(data))
    return tar_path, manifest, input_row_counts


def _provenance(ctx, *, outcome, code_doc, outputs, log_staged, status_note, worker_reported, partial):
    snap = ctx.snapshot
    exp = snap["experiment"]
    image = outcome.image if outcome else None
    remote = getattr(outcome, "remote", None) if outcome else None
    execution = {
        "backend": "isolated_python",
        "worker_image": image,
        "user": worker.ANALYSIS_USER, "network": "none", "read_only_root": True, "read_only_input": True,
    }
    if snap.get("execution", {}).get("backend") == "slurm":
        execution = {
            "backend": "slurm", "cluster": snap["execution"]["cluster"], "resources": snap["execution"]["resources"],
            "scheduler_job": remote, "worker_image": image,
            "container": "apptainer exec --containall --cleanenv --no-home --net --network none"
                         + (" --unsquash" if ctx.config.slurm_unsquash else ""),
            "network": "none (Apptainer network namespace"
                       + ("; local simulated cluster on an internal Docker network)"
                          if snap["execution"]["cluster"]["kind"] == "local_simulated" else ")"),
            "read_only_input": True,
            "not_enforced": ["tmp and output size are bounded only at collection",
                             "pids and open-file limits are not set by the job"],
        }
    execution.update({
        "started_at": _iso(outcome.started_at) if outcome else None,
        "finished_at": _iso(outcome.finished_at) if outcome else None,
        "wall_time_s": outcome.wall_time_s if outcome else None,
        "exit_code": outcome.exit_code if outcome else None,
        "outcome": outcome.status if outcome else None,
        "note": status_note,
    })
    return {
        "schema": "stellaris.provenance.v1",
        "run_id": ctx.run_id, "project_id": ctx.project_id, "generated_at": now_ts(),
        "accepted_snapshot": {
            "accepted_at": snap["accepted_at"], "input": ctx.input,
            "experiment": exp, "inputs": snap["inputs"], "parameters": snap["parameters"],
            "runtime": snap.get("runtime", "python"),
            "selected_sources": snap["sources"], "execution_limits": snap["limits"],
            "simulated_inputs": snap["simulated"],
            **({"report_calculation": snap["report_calculation"]} if snap.get("report_calculation") else {}),
        },
        "code": {"artifact_id": code_doc["id"], "sha256": code_doc["sha256"], "filename": code_doc["filename"],
                 "pipeline": snap["pipeline"]["name"], "pipeline_version": snap["pipeline"]["version"],
                 "runtime": snap.get("runtime", "python")},
        "execution": execution,
        "environment": outcome.versions if outcome else None,
        "calibration": {"mode": exp["calibration"]["mode"], "assumptions": exp["calibration"]["assumptions"]
                        + snap.get("calibration_assumptions", []), "conversion": snap["calibration_conversion"]},
        "seeds": ("bouncing_ball_v1 samples background residuals with numpy default_rng(0)"
                  if snap["pipeline"]["name"] == "bouncing_ball_v1" else "not controlled by the backend"),
        "model_provider": None,
        "worker_reported": worker_reported,
        "outputs": [{"artifact_id": s["id"], "filename": s["filename"], "kind": s["kind"], "origin": s["origin"],
                     "mime_type": s["mime_type"], "sha256": s["sha256"], "size_bytes": s["size_bytes"]} for s in outputs],
        "log_artifact_id": log_staged["id"] if log_staged else None,
        "partial_outputs": partial,
        "warnings": ctx.warnings,
        "reproducibility_limits": [
            "The Run resource's status is authoritative; this manifest records the execution outcome.",
            "Worker image is pinned by local image ID; rebuilding the image produces a different ID.",
            "Transitive Python package versions are recorded, not hash-pinned.",
            "Video decoding depends on the FFmpeg libraries bundled with PyAV (versions recorded in environment).",
        ],
    }


def _iso(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch)) if epoch else None


def _slurm_gate(ctx):
    """Return the approved remote_compute action, or request approval and suspend (None)."""
    approved = approvals.approved_action(ctx.conn, ctx.run_id, "remote_compute")
    if approved is not None:
        return approved
    snap = ctx.snapshot
    execution = snap["execution"]
    if ctx.cluster is None:
        raise RunFailure("REMOTE_UNAVAILABLE", "No Slurm cluster is configured.", True)
    image = worker.image_info(ctx.runtime, ctx.config)
    if image is None:
        raise RunFailure("WORKER_UNAVAILABLE", "The worker image is not available.", True)
    ctx.progress("preparing cluster image", None, "Preparing the Apptainer image on the cluster.", force=True)
    try:
        sif = ctx.cluster.ensure_sif(image)
    except hpc.ClusterUnavailable as exc:
        raise RunFailure("REMOTE_UNAVAILABLE", str(exc), True) from exc
    res = execution["resources"]
    action = {
        "backend": "slurm", "cluster": execution["cluster"], "resources": res,
        "pipeline": snap["pipeline"]["name"], "pipeline_version": snap["pipeline"]["version"],
        "pipeline_source_sha256": snap["pipeline"]["source_sha256"],
        "code_artifact": {"id": snap["code"]["id"], "sha256": snap["code"]["sha256"]} if snap["code"] else None,
        "inputs": [{"id": a["id"], "filename": a["filename"], "sha256": a["sha256"]} for a in snap["inputs"]],
        "worker_image_id": image["image_id"], "sif_sha256": sif["sha256"], "network": "none",
    }
    summary = (f"Run {snap['pipeline']['name']} on {execution['cluster']['label']} (partition {res['partition']}: "
               f"{res['cpus']} CPU, {res['memory_mb']} MiB, {res['wall_time_s']} s"
               + (f", {res['gpus']} GPU" if res["gpus"] else "") + ").")
    with transaction(ctx.conn):
        status = ctx.conn.execute("SELECT status FROM runs WHERE id = ?", (ctx.run_id,)).fetchone()["status"]
        if status != "running":
            raise RunFailure("CANCELLED", "The run was cancelled before approval was requested.")
        approvals.request(ctx.conn, ctx.config.approval_ttl_s, project_id=ctx.project_id, run_id=ctx.run_id,
                          action_type="remote_compute", summary=summary, action_snapshot=action)
    ctx.log.system(f"Approval requested: {summary}")
    ctx.log.flush()
    ctx.suspended = True
    return None


def handle_analysis(ctx):
    snap = ctx.snapshot
    approved = None
    if snap.get("execution", {}).get("backend") == "slurm":
        if ctx.cancel_requested():
            ctx.finish("cancelled", summary="Cancelled.")
            return
        try:
            approved = _slurm_gate(ctx)
        except RunFailure as exc:
            if exc.code == "CANCELLED":
                ctx.finish("cancelled", summary="Cancelled.")
                return
            raise
        if approved is None:
            return  # Suspended until the approval decision.
    # code_doc: the executed code artifact (bouncing_ball_v1's is set once committed).
    state = {"code_doc": snap["code"], "outcome": None, "approved": approved}
    work_dir = tempfile.mkdtemp(prefix=f"{ctx.run_id}-", dir=_run_tmp(ctx.config))
    try:
        _run_analysis(ctx, snap, snap["pipeline"]["name"], work_dir, state)
    except RunFailure as exc:
        if state["code_doc"] is None:
            raise  # Nothing was published yet; the executor records the failure with the logs.
        ctx.log.system(f"Run failed: {exc.code}: {exc.message}")
        _finish_without_results(ctx, state["outcome"], state["code_doc"], "failed",
                                {"code": exc.code, "message": exc.message, "retryable": exc.retryable})
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def execute_saved_analysis(ctx, experiment_id, code_artifact_id, *, input_artifact_ids=None, parameters=None, runtime=None,
                           cancelled=None, expected_revision=None):
    """Create and synchronously execute a normal immutable script run from an agent action.

    The caller's agent run already holds an executor slot, so execute_now avoids queue deadlock.
    Returns only persisted run/output identifiers and bounded text feedback.
    """
    from . import runs
    from .db import transaction
    from .projects import load_writable

    row = ctx.conn.execute("SELECT doc FROM experiments WHERE id = ? AND project_id = ?",
                           (experiment_id, ctx.project_id)).fetchone()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    experiment = json.loads(row["doc"])
    if expected_revision is not None and (not is_int(expected_revision) or expected_revision < 1):
        raise ApiError(422, "VALIDATION_FAILED", "expected_revision must be a positive integer.")
    target_revision = experiment["revision"] if expected_revision is None else expected_revision
    if experiment["revision"] != target_revision:
        raise ApiError(412, "REVISION_CONFLICT", "The experiment changed since the agent loaded it. Reload and reconcile edits.",
                       details={"current_revision": experiment["revision"]})
    implementation = experiment.get("implementation") or {}
    code_artifact_id = code_artifact_id or implementation.get("code_artifact_id")
    runtime = runtime or implementation.get("runtime", "python")
    input_artifact_ids = list(experiment["input_artifact_ids"] if input_artifact_ids is None else input_artifact_ids)
    if any(aid not in experiment["input_artifact_ids"] for aid in input_artifact_ids):
        # Materials are project-scoped inputs, not chat attachments. Save the selected
        # references on the plan before freezing this execution's immutable snapshot.
        from .experiments import update_experiment
        with transaction(ctx.conn):
            experiment = update_experiment(ctx.conn, ctx.project_id, experiment_id,
                {"input_artifact_ids": list(dict.fromkeys([*experiment["input_artifact_ids"], *input_artifact_ids]))},
                expected_revision=target_revision)
        target_revision = experiment["revision"]
    body = {"kind": "analysis", "experiment_id": experiment_id, "experiment_revision": experiment["revision"],
            "input_artifact_ids": input_artifact_ids, "pipeline": "script_analysis_v1",
            "code_artifact_id": code_artifact_id, "runtime": runtime, "parameters": parameters or {},
            "execution": {"backend": "isolated_python"}}
    try:
        snapshot = runs._analysis_snapshot(ctx.conn, ctx.config, ctx.project_id, body, manager=ctx.manager)
    except ApiError as exc:
        if exc.code == "EXPERIMENT_REVISION_CONFLICT":
            raise ApiError(412, "REVISION_CONFLICT", "The experiment changed since the agent loaded it. Reload and reconcile edits.",
                           details={"current_revision": experiment["revision"]}) from exc
        raise
    run_input = {"kind": "analysis", "experiment_id": experiment_id, "experiment_revision": experiment["revision"],
                 "input_artifact_ids": input_artifact_ids, "pipeline": "script_analysis_v1",
                 "code_artifact_id": code_artifact_id, "runtime": runtime, "parameters": snapshot["parameters"],
                 "execution": {"backend": "isolated_python"}}
    with transaction(ctx.conn):
        load_writable(ctx.conn, ctx.project_id)
        current_row = ctx.conn.execute("SELECT doc FROM experiments WHERE id = ? AND project_id = ?",
                                       (experiment_id, ctx.project_id)).fetchone()
        if current_row is None:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
        current_experiment = json.loads(current_row["doc"])
        if current_experiment["revision"] != target_revision:
            raise ApiError(412, "REVISION_CONFLICT", "The experiment changed before the analysis run was accepted.",
                           details={"current_revision": current_experiment["revision"]})
        run = runs.insert_run(ctx.conn, ctx.project_id, run_input, snapshot, experiment_id=experiment_id,
                              config=ctx.config)
    finished = threading.Event()

    def cancel_child_with_parent():
        while not finished.wait(0.1):
            if (cancelled or ctx.cancel_requested)():
                ctx.manager.request_cancel(run["id"])
                return

    cancel_watcher = threading.Thread(target=cancel_child_with_parent,
                                      name=f"cancel-child-{run['id'][-8:]}", daemon=True)
    cancel_watcher.start()
    try:
        ctx.manager.execute_now(run["id"])
    finally:
        finished.set()
        cancel_watcher.join(timeout=1)
        with ctx.manager._lock:
            ctx.manager._cancel_events.pop(run["id"], None)
    saved = runs.load_run_row(ctx.conn, ctx.project_id, run["id"])
    public = json.loads(saved["doc"])
    log_text = "".join(json.loads(item["doc"])["text"] for item in ctx.conn.execute(
        "SELECT doc FROM run_logs WHERE run_id = ? ORDER BY sequence", (run["id"],)).fetchall())
    return {"run_id": run["id"], "status": public["status"], "experiment_revision": target_revision,
            "output_artifact_ids": public["output_artifact_ids"], "error": public["error"],
            "result_summary": public["result_summary"], "log": log_text[-12_000:]}


def _run_analysis(ctx, snap, pipeline, work_dir, state):
    ctx.progress("preparing inputs", 0.02, "Publishing executed code and verifying inputs.", force=True)
    existing = ctx.conn.execute("SELECT doc FROM artifacts WHERE run_id = ? AND kind = 'code' ORDER BY created_at",
                                (ctx.run_id,)).fetchone()
    if pipeline == "bouncing_ball_v1" and existing is not None:  # Resumed run: code already published.
        code_bytes = snap["pipeline"]["source"].encode("utf-8")
        code_doc = json.loads(existing["doc"])
    elif pipeline == "bouncing_ball_v1":
        code_bytes = snap["pipeline"]["source"].encode("utf-8")
        path = os.path.join(work_dir, "pipeline.py")
        with open(path, "wb") as fh:
            fh.write(code_bytes)
        staged = ctx.stage(local_path=path, filename=f"{pipeline}.py", mime_type="text/x-python", kind="code",
                           origin="generated")
        code_doc = ctx.commit_now([staged])[0]  # Immutable executed code, visible as a partial output.
        ctx.log.system(f"Executed pipeline code published as artifact {code_doc['id']} (sha256 {code_doc['sha256']}).")
    else:
        code_doc, code_bytes = snap["code"], None
    state["code_doc"] = code_doc
    tar_path, _manifest, input_row_counts = _build_inputs(ctx, work_dir, code_doc, code_bytes)
    if ctx.cancel_requested():
        ctx.log.system("Cancelled before the worker started.")
        _finish_without_results(ctx, None, code_doc, "cancelled", None)
        return

    if state["approved"] is not None:
        on_remote = lambda stream, data: ctx.log.write(stream, data)  # noqa: E731
        outcome = hpc.run_slurm(ctx, approved=state["approved"], tar_path=tar_path, code_doc=code_doc,
                                work_dir=work_dir, on_output=on_remote)
        state["outcome"] = outcome
        ctx.log.system(f"Slurm job finished: {outcome.status} (exit code {outcome.exit_code}, "
                       f"{outcome.wall_time_s} s)." + (f" {outcome.message}" if outcome.message else ""))
    else:
        outcome = _run_local(ctx, pipeline, tar_path, code_doc, work_dir, snap.get("runtime", "python"))
        state["outcome"] = outcome
    _after_execution(ctx, snap, pipeline, work_dir, code_doc, outcome, input_row_counts)


def _run_local(ctx, pipeline, tar_path, code_doc, work_dir, runtime_name="python"):
    ctx.progress("running isolated worker", 0.1, "Executing in an isolated container.", force=True)
    ctx.log.system(f"Starting isolated worker for {pipeline} (network none, read-only inputs).")
    try:
        executable = {"python": ["python", "-I", "-B"], "javascript": ["node"], "shell": ["bash"]}[runtime_name]
        outcome = worker.run_worker(
            ctx.runtime, ctx.config, project_id=ctx.project_id, run_id=ctx.run_id, input_tar=tar_path,
            argv=[*executable, f"/input/artifacts/{code_doc['id']}"], work_dir=work_dir,
            on_output=lambda stream, data: (ctx.log.write(stream, data),
                                            ctx.progress("running isolated worker", None, "Worker is running.")),
            cancel_requested=ctx.cancel_requested)
    except worker.WorkerUnavailable as exc:
        log.error("Run %s: %s", ctx.run_id, exc)
        raise RunFailure("WORKER_UNAVAILABLE", "The isolated worker could not be started.", True)
    except DockerException as exc:
        log.error("Run %s: Docker failure during execution: %s", ctx.run_id, exc)
        raise RunFailure("WORKER_LOST", "Contact with the isolated worker was lost.", True)
    ctx.log.system(f"Worker finished: {outcome.status} (exit code {outcome.exit_code}, {outcome.wall_time_s} s)."
                   + (f" {outcome.message}" if outcome.message else ""))
    return outcome


def _after_execution(ctx, snap, pipeline, work_dir, code_doc, outcome, input_row_counts):
    if outcome.status != "completed":
        failure = EXECUTION_FAILURES[outcome.status]
        error = None if failure is None else {"code": failure[0], "message": outcome.message, "retryable": failure[1]}
        _finish_without_results(ctx, outcome, code_doc, "cancelled" if failure is None else "failed", error)
        return

    ctx.progress("validating output", 0.85, "Validating the worker result.", force=True)
    try:
        if "result.json" not in outcome.files:
            kind = outcome.rejected.get("result.json")
            raise InvalidOutput(["/output/result.json is missing" + (f" (it is a {kind})" if kind else "")])
        with open(outcome.files["result.json"], "rb") as fh:
            raw = fh.read(MAX_RESULT_BYTES + 1)
        input_ids = {a["id"] for a in snap["inputs"]}
        if pipeline != "script_analysis_v1":  # Preserve legacy code-reference behavior.
            input_ids.add(code_doc["id"])
        result = validate_result(raw, outcome.files, outcome.rejected, input_ids=input_ids,
                                 calibration_mode=snap["experiment"]["calibration"]["mode"],
                                 simulated=snap["simulated"], source_ids={s["id"] for s in snap["sources"]},
                                 tabular_units=pipeline == "script_analysis_v1" and bool(snap["inputs"])
                                 and all(a["kind"] == "dataset" and a["mime_type"] in {"text/csv", "application/json", "text/plain"}
                                         for a in snap["inputs"]))
        if snap.get("report_calculation"):
            if result["measurements"] or result["claims"]:
                raise InvalidOutput(["Report calculations publish computed datasets and charts only, not new scientific measurements or claims."])
        if (pipeline == "script_analysis_v1" and not snap["inputs"]
                and (any(row.get("data_origin") == "observed" for row in result["measurements"])
                     or any(row.get("kind") == "observation" for row in result["claims"]))):
            raise InvalidOutput(["script_analysis_v1 cannot publish observations without declared input artifacts"])
        if pipeline == "script_analysis_v1":
            unsupported_inferences = [claim["local_key"] for claim in result["claims"]
                                      if claim["kind"] == "inference" and
                                      (not (claim["evidence"] or claim["measurement_keys"] or claim["citations"])
                                       or not any(value.strip() for value in claim["assumptions"]))]
            if unsupported_inferences:
                raise InvalidOutput(["inference claims require evidence, measurements, or citations and at least one assumption: "
                                     + ", ".join(unsupported_inferences[:10])])
    except InvalidOutput as exc:
        for line in exc.errors[:50]:
            ctx.log.system(f"invalid output: {line}")
        _finish_without_results(ctx, outcome, code_doc, "failed", {
            "code": "INVALID_OUTPUT", "message": "The worker result was rejected: " + str(exc)[:900],
            "retryable": False})
        return
    for note in result["notes"]:
        ctx.warn("ORIGIN_RELABELLED", note)
    for w in result["warnings"]:
        ctx.warn(w["code"], w["message"])

    ctx.progress("publishing results", 0.9, "Storing outputs.", force=True)
    staged_by_key = {}
    try:
        for art in result["artifacts"]:
            parents = [p[1] for p in art["parents"] if p[0] == "input"]
            staged = ctx.stage(local_path=outcome.files[art["path"]], filename=art["filename"],
                               mime_type=art["mime_type"], kind=art["kind"], origin=art["origin"],
                               parent_artifact_ids=parents)
            staged["parent_artifact_ids"] = list(dict.fromkeys(
                [p[1] if p[0] == "input" else staged_by_key[p[1]]["id"] for p in art["parents"]]
                + ([code_doc["id"]] if art["kind"] != "code" else [])))
            staged_by_key[art["local_key"]] = staged
        output_descriptors = []
        for art in result["artifacts"]:
            staged = staged_by_key[art["local_key"]]
            descriptor = {**art, "metadata": staged["metadata"], "row_count": None}
            if staged["mime_type"] == "text/csv":
                descriptor["row_count"] = _count_csv_rows(outcome.files[art["path"]])
            output_descriptors.append(descriptor)
        input_descriptors = {a["id"]: a for a in snap["inputs"]}
        input_descriptors[code_doc["id"]] = code_doc
        _validate_evidence_anchors(result, input_descriptors, output_descriptors, input_row_counts)
    except InvalidOutput as exc:
        for line in exc.errors[:50]:
            ctx.log.system(f"invalid output: {line}")
        ctx.discard_staged()
        _finish_without_results(ctx, outcome, code_doc, "failed", {
            "code": "INVALID_OUTPUT", "message": "The worker result was rejected: " + str(exc)[:900],
            "retryable": False})
        return
    except ApiError as exc:
        ctx.log.system(f"invalid output: an output file failed server-side validation ({exc.code}: {exc.message})")
        ctx.discard_staged()
        _finish_without_results(ctx, outcome, code_doc, "failed", {
            "code": "INVALID_OUTPUT" if exc.status in (415, 422) else exc.code,
            "message": f"An output file was rejected: {exc.message}", "retryable": False})
        return

    worker_reported = None
    if pipeline == "bouncing_ball_v1" and "provenance.json" in outcome.files:
        try:
            with open(outcome.files["provenance.json"], "rb") as fh:
                worker_reported = strict_loads(fh.read(MAX_WORKER_PROVENANCE_BYTES).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            ctx.warn("WORKER_PROVENANCE_UNREADABLE", "The pipeline's provenance details could not be parsed.")

    insufficient = next((w for w in result["warnings"] if w["code"] == "INSUFFICIENT_EVIDENCE"), None)
    valid = sum(m["status"] == "valid" for m in result["measurements"])
    missing = sum(m["status"] == "missing" for m in result["measurements"])
    rejected_count = sum(m["status"] == "rejected" for m in result["measurements"])
    summary = (f"{valid} valid, {missing} missing, {rejected_count} rejected measurements; "
               f"{len(result['claims'])} claims; {len(staged_by_key)} output artifacts.")
    mean = next((m for m in result["measurements"] if m["quantity"] == "mean_apex_height_ratio"
                 and m["status"] == "valid"), None)
    if mean:
        summary += f" Mean apex-height ratio {mean['value']:.3f}."
    if snap["simulated"]:
        summary += " Inputs are SIMULATED."
    status, error = "succeeded", None
    if insufficient:
        status, error = "failed", {"code": "INSUFFICIENT_EVIDENCE", "message": insufficient["message"],
                                   "retryable": False}
        summary = "Insufficient evidence. " + summary

    ctx.log.system(f"Result accepted: {summary}")
    log_staged = ctx.stage_text(ctx.log.text(), filename="run-log.txt", mime_type="text/plain", kind="log",
                                origin="generated")
    prov = _provenance(ctx, outcome=outcome, code_doc=code_doc, outputs=list(staged_by_key.values()),
                       log_staged=log_staged, status_note=summary, worker_reported=worker_reported, partial=[])
    prov_staged = ctx.stage_text(json.dumps(prov, indent=1, allow_nan=False), filename="provenance.json",
                                 mime_type="application/json", kind="environment", origin="generated")

    def publish(conn):
        _publish_results(conn, ctx, result, staged_by_key)

    ctx.finish(status, error=error, summary=summary, publish=publish, retained=[log_staged], provenance=prov_staged)


def _finish_without_results(ctx, outcome, code_doc, status, error):
    """Terminal state without worker results: keep logs, executed code, and provenance."""
    ctx.log.flush()
    retained = []
    log_staged = None
    try:
        log_staged = ctx.stage_text(ctx.log.text() or "(no output)\n", filename="run-log.txt", mime_type="text/plain",
                                    kind="log", origin="generated")
        retained.append(log_staged)
        prov = _provenance(ctx, outcome=outcome, code_doc=code_doc, outputs=[], log_staged=log_staged,
                           status_note=(error or {}).get("message") or status, worker_reported=None,
                           partial=[{"artifact_id": code_doc["id"], "kind": "code"}])
        prov_staged = ctx.stage_text(json.dumps(prov, indent=1, allow_nan=False), filename="provenance.json",
                                     mime_type="application/json", kind="environment", origin="generated")
    except (ApiError, RuntimeUnavailable, OSError) as exc:
        log.warning("Run %s: could not stage partial outputs: %s", ctx.run_id, exc)
        prov_staged = None
    summary = "Cancelled." if status == "cancelled" else f"Failed: {error['code']}."
    ctx.finish(status, error=error, summary=summary, retained=retained, provenance=prov_staged)


def _publish_results(conn, ctx, result, staged_by_key):
    """Commit output artifacts, measurements, and claims (inside finish()'s transaction)."""
    from .artifacts import commit_artifact

    for art in result["artifacts"]:
        commit_artifact(conn, staged_by_key[art["local_key"]])

    def resolve(ev):
        kind, ref = ev["ref"]
        return {"artifact_id": ref if kind == "input" else staged_by_key[ref]["id"], "frame_index": ev["frame_index"],
                "time_s": ev["time_s"], "row_index": ev["row_index"]}

    cal_mode = ctx.snapshot["experiment"]["calibration"]["mode"]
    batch, ts = new_id("b")[2:18], now_ts()
    ids = {}
    for i, m in enumerate(result["measurements"]):
        mid = f"msr_{batch}{i:08x}"  # Sorts in worker order within one commit.
        ids[m["local_key"]] = mid
        doc = {"id": mid, "project_id": ctx.project_id, "experiment_id": ctx.experiment_id, "run_id": ctx.run_id,
               "series": m["series"], "quantity": m["quantity"], "value": m["value"] if m["status"] == "valid" else None,
               "unit": m["unit"], "time_s": m["time_s"],
               "uncertainty": {"absolute": m["uncertainty"]["absolute"], "method": m["uncertainty"]["method"]},
               "status": m["status"], "evidence": [resolve(e) for e in m["evidence"]], "calibration_mode": cal_mode,
               "data_origin": m["data_origin"], "assumptions": m["assumptions"], "created_at": ts}
        conn.execute("INSERT INTO measurements (id, project_id, run_id, series, created_at, doc) VALUES (?, ?, ?, ?, ?, ?)",
                     (mid, ctx.project_id, ctx.run_id, m["series"], ts, dumps(doc)))
    for c in result["claims"]:
        publish_claim(conn, ctx.project_id, run_id=ctx.run_id, kind=c["kind"], text=c["text"],
                      measurement_ids=[ids[k] for k in c["measurement_keys"]], citations=c["citations"],
                      evidence=[resolve(e) for e in c["evidence"]], assumptions=c["assumptions"],
                      limitations=c["limitations"], allow_archived=True)


def _run_tmp(config):
    os.makedirs(config.run_tmp_dir, mode=0o700, exist_ok=True)
    return config.run_tmp_dir


def cleanup_run_tmp(config) -> None:
    """Startup: no run is executing yet, so every run scratch directory is abandoned."""
    os.makedirs(config.run_tmp_dir, mode=0o700, exist_ok=True)
    for name in os.listdir(config.run_tmp_dir):
        shutil.rmtree(os.path.join(config.run_tmp_dir, name), ignore_errors=True)
