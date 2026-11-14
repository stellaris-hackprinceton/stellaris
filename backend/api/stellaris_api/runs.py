"""Runs, results, measurements, and logs (Contracts.md sections 5-7).

Acceptance: POST /runs validates the request, builds the complete immutable input snapshot
(experiment revision, artifact hashes/metadata, parameters, executed pipeline code, selected
sources, calibration conversion, execution limits), and commits the queued Run, its
run.created event, and the idempotent response in one transaction. Only then is the run
handed to the in-process executor (executor.RunManager). Restart recovery re-enqueues runs
that never started and fails interrupted ones with WORKER_LOST.

All run changes go through save_run() inside a transaction: it enforces the section 7 state
machine, bumps the revision, refreshes output_artifact_ids, and emits run.updated.
"""

import hashlib
import json
import math
import os

from flask import Blueprint, current_app, g, request

from . import idempotency, worker
from .errors import ApiError, validation_error
from .events import record_event
from .http import (
    decode_cursor, dumps, encode_cursor, idempotency_key, json_body, json_response, new_id, now_ts, page_limit,
    project_page,
)
from .projects import load_visible, load_writable
from .refs import require_artifacts, require_one
from .validation import Validator, invalid_reference, is_finite, is_int

bp = Blueprint("runs", __name__, url_prefix="/api/v1/projects")

KINDS = ("agent", "analysis", "report", "paper_ingest")
STATUSES = ("queued", "running", "awaiting_approval", "cancelling", "succeeded", "failed", "cancelled")
ACTIVE = ("queued", "running", "awaiting_approval", "cancelling")
TERMINAL = ("succeeded", "failed", "cancelled")
TRANSITIONS = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"awaiting_approval", "cancelling", "succeeded", "failed"},
    "awaiting_approval": {"running", "cancelling", "cancelled", "failed"},
    "cancelling": {"cancelled", "failed"},
}
PIPELINES = {
    "bouncing_ball_v1": {"version": "1.0.0", "source_file": "bouncing_ball_v1.py"},
    "python_analysis_v1": {"version": "1.0.0", "source_file": None},
    "script_analysis_v1": {"version": "1.0.0", "source_file": None},
}
ANALYSIS_FIELDS = {"kind", "experiment_id", "experiment_revision", "input_artifact_ids", "pipeline",
                   "code_artifact_id", "parameters", "execution", "runtime"}
RESOURCE_FIELDS = {"partition", "wall_time_s", "memory_mb", "cpus", "gpus"}
REPORT_FIELDS = {"kind", "experiment_id", "evidence_run_ids", "source_ids", "title", "format"}
BOUNCING_PARAMETERS = {"start_time_s", "end_time_s", "object_hint"}
VIDEO_MIME_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
MAX_PARAMETERS_BYTES = 64 * 1024
MAX_EVIDENCE_RUNS = 20
MAX_REPORT_SOURCES = 100


class InvalidTransition(Exception):
    pass


# -- persistence ---------------------------------------------------------------------

def load_run_row(conn, project_id: str, run_id: str):
    row = conn.execute("SELECT * FROM runs WHERE id = ? AND project_id = ?", (run_id, project_id)).fetchone()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    return row


def save_run(conn, run_id: str, **changes) -> dict:
    """Apply changes to a run's public doc in the caller's transaction and emit run.updated.

    `status` changes must follow the section 7 transitions (InvalidTransition otherwise).
    Every save increases the revision. output_artifact_ids always lists the run's committed
    artifacts in creation order.
    """
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    run = json.loads(row["doc"])
    status = changes.get("status", run["status"])
    if status != run["status"] and status not in TRANSITIONS.get(run["status"], ()):
        raise InvalidTransition(f"{run['status']} -> {status}")
    updated = {**run, **changes, "revision": run["revision"] + 1}
    updated["output_artifact_ids"] = [r["id"] for r in conn.execute(
        "SELECT id FROM artifacts WHERE run_id = ? AND project_id = ? ORDER BY created_at, id",
        (run_id, run["project_id"]))]
    if status in TERMINAL and run["input"]["kind"] == "agent":
        finalize_agent_message(conn, updated)
    if status in TERMINAL or status == "cancelling":  # Section 7: outstanding approvals expire.
        for arow in conn.execute("SELECT doc FROM approvals WHERE run_id = ? AND status = 'pending'", (run_id,)).fetchall():
            approval = json.loads(arow["doc"])
            approval.update(status="expired", decided_at=now_ts())
            conn.execute("UPDATE approvals SET status = 'expired', doc = ? WHERE id = ?", (dumps(approval), approval["id"]))
            record_event(conn, run["project_id"], "approval.updated", {"approval": approval}, run_id=run_id)
    conn.execute("UPDATE runs SET status = ?, doc = ? WHERE id = ?", (updated["status"], dumps(updated), run_id))
    record_event(conn, run["project_id"], "run.updated", {"run": updated}, run_id=run_id)
    return updated


def finalize_agent_message(conn, run):
    """Finalize chat before its terminal run event, including recovery and queued cancel."""
    row = conn.execute("SELECT doc FROM messages WHERE id = ? AND project_id = ?",
                       (run["input"]["assistant_message_id"], run["project_id"])).fetchone()
    if row is None:
        return
    message = json.loads(row["doc"])
    target = "complete" if run["status"] == "succeeded" else "interrupted"
    claims = [r["id"] for r in conn.execute("SELECT id FROM claims WHERE run_id = ? ORDER BY created_at,id", (run["id"],))]
    if message["status"] == target and message["claim_ids"] == claims:
        return
    message.update(status=target, claim_ids=claims, updated_at=now_ts())
    conn.execute("UPDATE messages SET doc = ? WHERE id = ?", (dumps(message), message["id"]))
    record_event(conn, run["project_id"], "message.updated", {"message": message}, run_id=run["id"])


def add_warnings(conn, run_id: str, warnings) -> None:
    row = conn.execute("SELECT warnings FROM runs WHERE id = ?", (run_id,)).fetchone()
    current = json.loads(row["warnings"])
    for w in warnings:
        if w not in current:
            current.append(w)
    conn.execute("UPDATE runs SET warnings = ? WHERE id = ?", (dumps(current), run_id))


def results(conn, project_id: str, run_id: str) -> dict:
    """RunResults computed from committed rows (so partial results appear as they commit)."""
    row = conn.execute("SELECT warnings FROM runs WHERE id = ? AND project_id = ?", (run_id, project_id)).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM measurements WHERE run_id = ? AND project_id = ?",
                         (run_id, project_id)).fetchone()[0]
    claim_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM claims WHERE run_id = ? AND project_id = ? ORDER BY created_at, id", (run_id, project_id))]
    by_kind = {}
    for r in conn.execute("SELECT id, kind FROM artifacts WHERE run_id = ? AND project_id = ? ORDER BY created_at, id",
                          (run_id, project_id)):
        by_kind.setdefault(r["kind"], []).append(r["id"])
    reports = by_kind.get("report", [])
    return {
        "run_id": run_id,
        "measurement_count": count,
        "claim_ids": claim_ids,
        "chart_artifact_ids": by_kind.get("chart", []),
        "annotated_media_artifact_ids": by_kind.get("image", []) + by_kind.get("video", []),
        "report_artifact_id": reports[-1] if reports else None,
        "warnings": json.loads(row["warnings"]) if row else [],
    }


def recover_after_restart(conn):
    """Runs before serving. Returns (queued_ids, lost_ids).

    Queued runs never started (a run becomes `running` before any side effect), so they are
    re-enqueued. Executing runs were interrupted: they become failed/WORKER_LOST (or cancelled
    if cancellation was already requested) and are not rerun.
    """
    queued, lost = [], []
    ts = now_ts()
    for row in conn.execute("SELECT id, status, doc FROM runs WHERE status IN ('queued', 'running', "
                            "'awaiting_approval', 'cancelling') ORDER BY created_at, id").fetchall():
        remote = json.loads(row["doc"]).get("execution_backend") == "slurm"
        if row["status"] == "queued":
            queued.append((row["id"], remote))
            continue
        if remote:
            # Slurm jobs outlive the backend: approvals stay pending, and executing runs reattach
            # to their job (found by its run-specific name) instead of becoming WORKER_LOST.
            if row["status"] in ("running", "cancelling"):
                queued.append((row["id"], "resume"))
            continue
        lost.append(row["id"])
        warning = {"code": "WORKER_LOST", "message": "The backend restarted while this run was executing. "
                                                     "It was not rerun; committed outputs and logs were kept."}
        add_warnings(conn, row["id"], [warning])
        if row["status"] == "cancelling":
            save_run(conn, row["id"], status="cancelled", finished_at=ts, phase="cancelled",
                     progress={"fraction": None, "message": "Cancelled (execution interrupted by a backend restart)."})
        else:
            save_run(conn, row["id"], status="failed", finished_at=ts, phase="failed",
                     progress={"fraction": None, "message": "Worker lost."},
                     error={"code": "WORKER_LOST", "message": warning["message"], "retryable": True})
    return queued, lost


# -- acceptance --------------------------------------------------------------------------

def _require_run_doc(conn, project_id, run_id, path):
    row = None
    if isinstance(run_id, str):
        row = conn.execute("SELECT * FROM runs WHERE id = ? AND project_id = ?", (run_id, project_id)).fetchone()
    if row is None:
        raise invalid_reference([{"path": path, "message": "Run not found in this project."}])
    return row


def _validate_structure(body: dict) -> str:
    kind = body.get("kind")
    if kind == "agent":
        raise validation_error([{"path": "/kind", "message": "Agent runs are created through chat messages."}])
    if kind == "paper_ingest":
        from . import papers
        papers.validate_structure(body)
        return kind
    v = Validator()
    if kind not in ("analysis", "report"):
        v.error("/kind", "kind must be 'analysis', 'report', or 'paper_ingest'.")
        v.check()
    if kind == "analysis":
        v.unknown(body, ANALYSIS_FIELDS)
        v.string(body, "experiment_id", min_len=1, max_len=100)
        if not is_int(body.get("experiment_revision")) or body["experiment_revision"] < 1:
            v.error("/experiment_revision", "experiment_revision must be a positive integer.")
        pipeline = v.enum(body, "pipeline", tuple(PIPELINES))
        ids = v.strings(body, "input_artifact_ids", max_items=50, min_len=1, max_len=100, unique=True)
        if pipeline != "script_analysis_v1" and "input_artifact_ids" in body and isinstance(body["input_artifact_ids"], list) and not ids:
            v.error("/input_artifact_ids", "At least one input artifact is required.")
        v.enum(body, "runtime", ("python", "javascript", "shell"), required=False)
        if "code_artifact_id" not in body:
            v.error("/code_artifact_id", "code_artifact_id is required (string or null).")
        else:
            v.string(body, "code_artifact_id", nullable=True, min_len=1, max_len=100)
        execution = body.get("execution")
        if execution is not None:
            if not isinstance(execution, dict):
                v.error("/execution", "execution must be an object.")
            else:
                v.unknown(execution, {"backend", "resources"}, "/execution")
                v.enum(execution, "backend", ("isolated_python", "slurm"), "/execution")
                res = execution.get("resources")
                if res is not None:
                    if execution.get("backend") != "slurm" or not isinstance(res, dict):
                        v.error("/execution/resources", "resources are accepted only for the slurm backend.")
                    else:
                        v.unknown(res, RESOURCE_FIELDS, "/execution/resources")
                        v.string(res, "partition", "/execution/resources", required=False, min_len=1, max_len=64)
                        for key in ("wall_time_s", "memory_mb", "cpus", "gpus"):
                            if key in res and (not is_int(res[key]) or res[key] < (0 if key == "gpus" else 1)):
                                v.error(f"/execution/resources/{key}", f"{key} must be a positive integer.")
        if not isinstance(body.get("parameters"), dict):
            v.error("/parameters", "parameters must be a JSON object.")
        elif len(dumps(body["parameters"]).encode()) > MAX_PARAMETERS_BYTES:
            v.error("/parameters", "parameters must be at most 64 KiB of JSON.")
    else:
        v.unknown(body, REPORT_FIELDS)
        v.string(body, "experiment_id", min_len=1, max_len=100)
        ids = v.strings(body, "evidence_run_ids", max_items=MAX_EVIDENCE_RUNS, min_len=1, max_len=100, unique=True)
        if "evidence_run_ids" in body and isinstance(body["evidence_run_ids"], list) and not ids:
            v.error("/evidence_run_ids", "At least one evidence run is required.")
        v.strings(body, "source_ids", max_items=MAX_REPORT_SOURCES, min_len=1, max_len=100, unique=True)
        v.string(body, "title", min_len=1, max_len=200, strip=True)
        v.enum(body, "format", ("markdown",))
    v.check()
    return kind


def _limits(config) -> dict:
    return {"max_wall_time_s": config.worker_wall_time_s, "max_memory_mb": config.worker_memory_mb,
            "max_cpu_cores": config.worker_cpus, "max_pids": config.worker_pids_limit,
            "max_output_mb": config.worker_output_mb, "max_tmp_mb": config.worker_tmp_mb, "network_access": False}


def calibration_conversion(cal: dict):
    if cal["mode"] != "reference_length":
        return None
    (ax, ay), (bx, by) = cal["point_a_px"], cal["point_b_px"]
    distance = math.hypot(bx - ax, by - ay)
    unc = cal["reference_uncertainty_m"]
    scale = cal["reference_length_m"] / distance
    relative = (unc / cal["reference_length_m"]) if unc is not None else None
    if not is_finite(scale) or scale <= 0 or (relative is not None and not is_finite(relative)):
        raise validation_error([{"path": "/calibration", "message": "Calibration conversion exceeds the numeric range."}])
    return {
        "calibration_artifact_id": cal["artifact_id"], "frame_index": cal["frame_index"],
        "pixel_distance": distance, "reference_length_m": cal["reference_length_m"],
        "reference_uncertainty_m": unc, "meters_per_pixel": scale,
        "relative_uncertainty": relative,
        "note": "Relative uncertainty includes only the stated reference-length uncertainty; point placement "
                "uncertainty is not included. Null means unknown, not zero.",
    }


def _artifact_snapshot(a: dict) -> dict:
    return {k: a[k] for k in ("id", "kind", "origin", "filename", "mime_type", "size_bytes", "sha256",
                              "parent_artifact_ids", "metadata", "created_at")}


def _analysis_snapshot(conn, config, project_id: str, body: dict, *, manager=None) -> dict:
    experiment = require_one(conn, "experiments", project_id, body["experiment_id"], "/experiment_id")
    if experiment["revision"] != body["experiment_revision"]:
        raise ApiError(409, "EXPERIMENT_REVISION_CONFLICT",
                       "The experiment changed since this run was prepared. Reload it and resubmit.",
                       details={"current_revision": experiment["revision"]})
    errors = [{"path": f"/input_artifact_ids/{i}", "message": "Not one of the experiment's input artifacts."}
              for i, aid in enumerate(body["input_artifact_ids"]) if aid not in experiment["input_artifact_ids"]]
    if errors:
        raise validation_error(errors)
    inputs = require_artifacts(conn, project_id, body["input_artifact_ids"], "/input_artifact_ids")
    pipeline, params = body["pipeline"], body["parameters"]
    runtime_name = body.get("runtime", "python")
    if pipeline in ("bouncing_ball_v1", "python_analysis_v1") and runtime_name != "python":
        raise validation_error([{"path": "/runtime", "message": "Legacy pipelines require runtime 'python'."}])
    cal = experiment["calibration"]
    conversion = calibration_conversion(cal)
    code = None
    pipeline_source = None
    assumptions = []

    if pipeline == "bouncing_ball_v1":
        if body["code_artifact_id"] is not None:
            raise validation_error([{"path": "/code_artifact_id", "message": "bouncing_ball_v1 requires code_artifact_id: null."}])
        if len(inputs) != 1:
            raise validation_error([{"path": "/input_artifact_ids", "message": "bouncing_ball_v1 requires exactly one video."}])
        video = next(iter(inputs.values()))
        if video["kind"] != "video" or video["mime_type"] not in VIDEO_MIME_TYPES:
            raise validation_error([{"path": "/input_artifact_ids/0", "message": "Input must be a supported video."}])
        v = Validator()
        v.unknown(params, BOUNCING_PARAMETERS, "/parameters")
        start = params.get("start_time_s", 0)
        end = params.get("end_time_s")
        hint = params.get("object_hint", "ball")
        duration = (video["metadata"].get("duration_ms") or 0) / 1000.0
        if not (is_finite(start) and start >= 0):
            v.error("/parameters/start_time_s", "start_time_s must be a finite number >= 0.")
        elif start >= duration:
            v.error("/parameters/start_time_s", f"start_time_s must be before the video end ({duration:.3f} s).")
        if end is not None and not is_finite(end):
            v.error("/parameters/end_time_s", "end_time_s must be a finite number or null.")
        elif end is not None and is_finite(start) and (end <= start or end > duration + 1e-3):
            v.error("/parameters/end_time_s", f"end_time_s must be after start_time_s and at most {duration:.3f} s.")
        if not isinstance(hint, str) or not 1 <= len(hint.strip()) <= 100:
            v.error("/parameters/object_hint", "object_hint must be a nonempty string of at most 100 characters.")
        v.check()
        params = {"start_time_s": start, "end_time_s": end, "object_hint": hint.strip()}
        if cal["mode"] == "reference_length" and cal["artifact_id"] != video["id"]:
            cal_art = require_one(conn, "artifacts", project_id, cal["artifact_id"], "/calibration/artifact_id")
            dims = lambda a: (a["metadata"].get("width_px"), a["metadata"].get("height_px"))  # noqa: E731
            if dims(cal_art) != dims(video):
                raise validation_error([{"path": "/experiment_id", "message":
                                         "The experiment's calibration artifact has a different frame size than the "
                                         "analysed video, so its scale cannot be applied."}])
            assumptions.append("Calibration comes from a different artifact of the same frame size; the camera position "
                               "and zoom are assumed unchanged.")
        path = os.path.join(config.pipelines_dir, PIPELINES[pipeline]["source_file"])
        try:
            with open(path, encoding="utf-8", newline="") as fh:  # Byte-exact text.
                pipeline_source = fh.read()
        except OSError:
            raise ApiError(409, "FEATURE_UNAVAILABLE", "The bouncing_ball_v1 pipeline is not installed.")
    elif pipeline == "python_analysis_v1":
        code_id = body["code_artifact_id"]
        if code_id is None:
            raise validation_error([{"path": "/code_artifact_id", "message": "python_analysis_v1 requires a Python code artifact."}])
        code = require_one(conn, "artifacts", project_id, code_id, "/code_artifact_id")
        if code["kind"] != "code" or code["mime_type"] != "text/x-python":
            raise validation_error([{"path": "/code_artifact_id", "message": "code_artifact_id must be a text/x-python code artifact."}])
        code = _artifact_snapshot(code)

    else:  # script_analysis_v1
        if (body.get("execution") or {}).get("backend", "isolated_python") != "isolated_python":
            raise validation_error([{"path": "/execution/backend", "message": "script_analysis_v1 currently supports isolated workers only."}])
        if body["code_artifact_id"] is None:
            raise validation_error([{"path": "/code_artifact_id", "message": "script_analysis_v1 requires a saved code artifact."}])
        code = require_one(conn, "artifacts", project_id, body["code_artifact_id"], "/code_artifact_id")
        expected_mimes = {"python": {"text/x-python", "text/plain"},
                          "javascript": {"text/javascript", "application/javascript", "text/plain"},
                          "shell": {"text/x-shellscript", "text/plain"}}[runtime_name]
        if code["kind"] != "code" or code["mime_type"] not in expected_mimes:
            raise validation_error([{"path": "/code_artifact_id", "message": "code artifact MIME type does not match runtime."}])
        code = _artifact_snapshot(code)
        supported = worker.available_runtimes((manager or _manager()).runtime, config)
        if runtime_name not in supported:
            raise ApiError(409, "FEATURE_UNAVAILABLE", f"The configured worker image does not advertise runtime {runtime_name!r}.")

    data_inputs = [_artifact_snapshot(inputs[aid]) for aid in body["input_artifact_ids"]]
    return {
        "version": 1, "kind": "analysis", "runtime": runtime_name,
        "project": {"id": project_id, "research_question": load_visible(conn, project_id)["research_question"]},
        "experiment": experiment,
        "inputs": data_inputs,
        "code": code,
        "pipeline": {"name": pipeline, "version": PIPELINES[pipeline]["version"],
                     "source": pipeline_source,
                     "source_sha256": (hashlib.sha256(pipeline_source.encode("utf-8")).hexdigest()
                                       if pipeline_source else None)},
        "parameters": params,
        "calibration_conversion": conversion,
        "calibration_assumptions": assumptions,
        "sources": [],
        "simulated": any(a["origin"] == "simulated" for a in data_inputs),
        "execution": resolve_execution(body.get("execution"), config, (manager or _manager()).cluster),
        "limits": _limits(config),
        "accepted_at": now_ts(),
    }


def _report_snapshot(conn, project_id: str, body: dict) -> dict:
    experiment = require_one(conn, "experiments", project_id, body["experiment_id"], "/experiment_id")
    evidence, errors = [], []
    for i, rid in enumerate(body["evidence_run_ids"]):
        row = _require_run_doc(conn, project_id, rid, f"/evidence_run_ids/{i}")
        run = json.loads(row["doc"])
        if run["input"]["kind"] != "analysis":
            errors.append({"path": f"/evidence_run_ids/{i}", "message": "Evidence runs must be analysis runs."})
        elif run["status"] not in TERMINAL:
            errors.append({"path": f"/evidence_run_ids/{i}", "message": "Evidence runs must be terminal."})
        elif run["input"]["experiment_id"] != experiment["id"]:
            errors.append({"path": f"/evidence_run_ids/{i}", "message": "Evidence run belongs to a different experiment."})
        evidence.append({"id": rid, "status": run["status"], "revision": run["revision"],
                         "provenance_artifact_id": run["provenance_artifact_id"]})
    if errors:
        raise validation_error(errors)
    sources = [require_one(conn, "sources", project_id, sid, f"/source_ids/{i}")
               for i, sid in enumerate(body.get("source_ids", []))]
    return {
        "version": 1, "kind": "report",
        "project": {"id": project_id, "research_question": load_visible(conn, project_id)["research_question"]},
        "experiment_current": experiment,
        "evidence_runs": evidence,
        "sources": sources,
        "title": body["title"].strip(),
        "format": "markdown",
        "accepted_at": now_ts(),
    }


def _new_run(project_id: str, run_input: dict) -> dict:
    backend = (run_input.get("execution") or {}).get("backend", "isolated_python")
    run = {
        "id": new_id("run"), "project_id": project_id, "input": run_input, "status": "queued", "phase": "queued",
        "progress": {"fraction": None, "message": "Waiting for an execution slot."},
        "execution_backend": backend, "output_artifact_ids": [], "result_summary": None, "error": None,
        "provenance_artifact_id": None, "created_at": now_ts(), "started_at": None, "finished_at": None, "revision": 1,
    }
    if backend == "slurm":
        run["remote_job"] = None
    return run


def resolve_execution(execution, config, cluster) -> dict:
    """Validate a requested execution against capabilities; returns the snapshot form."""
    execution = execution or {"backend": "isolated_python"}
    if execution["backend"] == "isolated_python":
        return {"backend": "isolated_python"}
    caps = cluster.capabilities() if cluster is not None else None
    if caps is None:
        raise ApiError(409, "FEATURE_UNAVAILABLE", "Slurm execution is not available (no reachable cluster).")
    requested = execution.get("resources") or {}
    partitions = {p["name"]: p for p in caps["partitions"]}
    name = requested.get("partition") or caps["partitions"][0]["name"]
    if name not in partitions:
        raise validation_error([{"path": "/execution/resources/partition", "message": f"Unknown partition {name!r}."}])
    part = partitions[name]
    resources = {
        "partition": name,
        "wall_time_s": requested.get("wall_time_s", min(config.worker_wall_time_s, part["max_wall_time_s"])),
        "memory_mb": requested.get("memory_mb", min(config.worker_memory_mb, part["max_memory_mb"])),
        "cpus": requested.get("cpus", max(1, min(math.ceil(config.worker_cpus), part["max_cpus"]))),
        "gpus": requested.get("gpus", 0),
    }
    limits = {"wall_time_s": part["max_wall_time_s"], "memory_mb": part["max_memory_mb"], "cpus": part["max_cpus"],
              "gpus": part["max_gpus"]}
    errors = [{"path": f"/execution/resources/{k}", "message": f"{k} exceeds the partition limit ({limits[k]})."}
              for k in limits if resources[k] > limits[k]]
    if errors:
        raise validation_error(errors)
    return {"backend": "slurm", "resources": resources,
            "cluster": {"label": caps["cluster_label"], "kind": caps["cluster_kind"], "scheduler": "slurm",
                        "container_runtime": "apptainer"}}


def insert_run(conn, project_id: str, run_input: dict, snapshot: dict, experiment_id=None, config=None) -> dict:
    """Persist a queued run with its snapshot and run.created event (caller's transaction).

    Used by POST /runs, chat (agent runs), and agent-requested paper ingestion (which passes
    `config` because it runs outside a request context).
    """
    from .artifacts import _used_bytes, _quota_error
    config = config or current_app.config["STELLARIS"]
    audit_budget = config.max_run_log_bytes + 16 * 1024 * 1024
    if _used_bytes(conn, project_id) + audit_budget > config.max_project_bytes:
        raise _quota_error()
    snapshot = {**snapshot, "audit_reserve_bytes": audit_budget}
    run = _new_run(project_id, run_input)
    conn.execute("INSERT INTO runs (id, project_id, kind, experiment_id, status, created_at, doc, snapshot) "
                 "VALUES (?, ?, ?, ?, 'queued', ?, ?, ?)",
                 (run["id"], project_id, run_input["kind"], experiment_id, run["created_at"], dumps(run),
                  dumps(snapshot)))
    record_event(conn, project_id, "run.created", {"run": run}, run_id=run["id"])
    return run


# -- routes ------------------------------------------------------------------------------

def _manager():
    return current_app.extensions["stellaris_runs"]


@bp.post("/<project_id>/runs")
def create_run(project_id):
    config = current_app.config["STELLARIS"]
    body = json_body()
    key = idempotency_key()
    kind = _validate_structure(body)
    if kind in ("analysis", "paper_ingest") and not _manager().worker_available():
        raise ApiError(409, "FEATURE_UNAVAILABLE", "Isolated analysis workers are not available (worker image missing).")
    created = []

    def build(conn):
        load_writable(conn, project_id)
        if kind == "paper_ingest":
            from . import papers
            run_input, snapshot = papers.build_snapshot(conn, config, project_id, body)
            run = insert_run(conn, project_id, run_input, snapshot)
            created.append(run["id"])
            return 202, run, {"Location": f"/api/v1/projects/{project_id}/runs/{run['id']}"}, run["id"]
        if kind == "analysis":
            snapshot = _analysis_snapshot(conn, config, project_id, body)
            run_input = {"kind": "analysis", "experiment_id": body["experiment_id"],
                         "experiment_revision": body["experiment_revision"],
                         "input_artifact_ids": list(body["input_artifact_ids"]), "pipeline": body["pipeline"],
                         "code_artifact_id": body["code_artifact_id"], "parameters": snapshot["parameters"],
                         "runtime": snapshot["runtime"],
                         "execution": {k: v for k, v in snapshot["execution"].items() if k != "cluster"}}
        else:
            snapshot = _report_snapshot(conn, project_id, body)
            run_input = {"kind": "report", "experiment_id": body["experiment_id"],
                         "evidence_run_ids": list(body["evidence_run_ids"]),
                         "source_ids": list(body.get("source_ids", [])), "title": snapshot["title"],
                         "format": "markdown"}
        run = insert_run(conn, project_id, run_input, snapshot, experiment_id=body["experiment_id"])
        created.append(run["id"])
        return 202, run, {"Location": f"/api/v1/projects/{project_id}/runs/{run['id']}"}, run["id"]

    response = idempotency.run_command(g.db, key, body, build)
    if created:  # Committed (snapshot persisted) before the executor sees it.
        _manager().enqueue(created[0], remote=(body.get("execution") or {}).get("backend") == "slurm")
    return response


@bp.get("/<project_id>/runs")
def list_runs(project_id):
    load_visible(g.db, project_id)
    rows, next_cursor = project_page(g.db, "runs", project_id, {
        "experiment_id": ("experiment_id", None), "status": ("status", STATUSES), "kind": ("kind", KINDS)})
    return json_response({"items": [json.loads(r["doc"]) for r in rows], "next_cursor": next_cursor})


@bp.get("/<project_id>/runs/<run_id>")
def get_run(project_id, run_id):
    load_visible(g.db, project_id)
    return json_response(json.loads(load_run_row(g.db, project_id, run_id)["doc"]))


@bp.post("/<project_id>/runs/<run_id>/cancel")
def cancel_run(project_id, run_id):
    body = json_body()
    key = idempotency_key()
    if body:
        raise validation_error([{"path": f"/{k}", "message": "Unknown field."} for k in sorted(body)])
    signal = []

    def build(conn):
        load_visible(conn, project_id)  # Accepted runs of archived projects may still be cancelled.
        run = json.loads(load_run_row(conn, project_id, run_id)["doc"])
        if run["status"] in TERMINAL:
            return 200, run, {}, run_id
        if run["status"] in ("queued", "awaiting_approval"):
            run = save_run(conn, run_id, status="cancelled", finished_at=now_ts(), phase="cancelled",
                           progress={"fraction": None, "message": "Cancelled before execution finished."})
        elif run["status"] == "running":
            run = save_run(conn, run_id, status="cancelling", phase="cancelling",
                           progress={"fraction": None, "message": "Stopping the worker."})
        signal.append(run_id)
        return 202, run, {}, run_id

    response = idempotency.run_command(g.db, key, body, build)
    if signal:
        _manager().request_cancel(run_id)
    return response


@bp.get("/<project_id>/runs/<run_id>/results")
def get_results(project_id, run_id):
    load_visible(g.db, project_id)
    load_run_row(g.db, project_id, run_id)
    return json_response(results(g.db, project_id, run_id))


@bp.get("/<project_id>/runs/<run_id>/measurements")
def list_measurements(project_id, run_id):
    load_visible(g.db, project_id)
    load_run_row(g.db, project_id, run_id)
    rows, next_cursor = project_page(g.db, "measurements", project_id, {"series": ("series", None)},
                                     fixed={"run_id": run_id})
    return json_response({"items": [json.loads(r["doc"]) for r in rows], "next_cursor": next_cursor})


@bp.get("/<project_id>/runs/<run_id>/logs")
def list_logs(project_id, run_id):
    """Log entries ordered by per-run sequence; ?after_sequence=N selects entries after N."""
    load_visible(g.db, project_id)
    load_run_row(g.db, project_id, run_id)
    limit = page_limit()
    raw_after = request.args.get("after_sequence")
    after = None
    if raw_after is not None:
        try:
            after = int(raw_after)
        except ValueError:
            raise ApiError(400, "INVALID_QUERY", "after_sequence must be an integer.")
        if after < 0:
            raise ApiError(400, "INVALID_QUERY", "after_sequence must be >= 0.")
    position = after or 0
    cursor = request.args.get("cursor")
    if cursor:
        state = decode_cursor(cursor)
        if (state.get("v") != 1 or state.get("t") != "run_logs" or state.get("p") != project_id
                or state.get("r") != run_id or not is_int(state.get("s"))):
            raise ApiError(400, "INVALID_CURSOR", "cursor is invalid.")
        if raw_after is not None and state.get("a") != after:
            raise ApiError(400, "INVALID_QUERY", "Query filters must match the filters used to create the cursor.")
        after = state.get("a")
        position = state["s"]
    rows = g.db.execute("SELECT doc, sequence FROM run_logs WHERE run_id = ? AND project_id = ? AND sequence > ? "
                        "ORDER BY sequence LIMIT ?", (run_id, project_id, position, limit + 1)).fetchall()
    next_cursor = None
    if len(rows) > limit:
        next_cursor = encode_cursor({"v": 1, "t": "run_logs", "p": project_id, "r": run_id,
                                     "s": rows[limit - 1]["sequence"], "a": after})
    return json_response({"items": [json.loads(r["doc"]) for r in rows[:limit]], "next_cursor": next_cursor})
