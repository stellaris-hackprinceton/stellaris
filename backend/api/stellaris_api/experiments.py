"""Experiment plans with revisions and ETags (docs/frontend-backend-contract.md sections 5-6).

An experiment is a plan, not an execution record. Every save validates that referenced
artifacts are ready and belong to the project, and that reference-length calibration
points lie inside the referenced frame. Agent tools use create_experiment() and
update_experiment() with the same rules.
"""

import json
import os
import tempfile
from contextlib import nullcontext

from flask import Blueprint, current_app, g

from . import idempotency
from .db import transaction
from .errors import ApiError, validation_error
from .events import record_event
from .http import (
    dumps, etag, idempotency_key, json_body, json_response, new_id, now_ts, parse_if_match, project_page,
)
from .projects import load_visible, load_writable
from .refs import require_artifacts, require_one
from .research import get_doc
from .validation import MAX_TEXT, Validator, is_finite, is_int

bp = Blueprint("experiments", __name__, url_prefix="/api/v1/projects")

FIELDS = ("title", "hypothesis", "method", "protocol_markdown", "variables", "success_criteria",
          "input_artifact_ids", "calibration", "limitations", "implementation")
METHODS = ("physical", "computational", "hybrid")
ROLES = ("independent", "dependent", "controlled")
CAL_REFERENCE_FIELDS = {"mode", "artifact_id", "frame_index", "point_a_px", "point_b_px",
                        "reference_length_m", "reference_uncertainty_m", "assumptions"}


# -- validation -------------------------------------------------------------------

def validate_fields(body: dict, *, partial: bool) -> dict:
    """Structural validation of experiment fields (all required unless partial). Raises 422."""
    v = Validator()
    v.unknown(body, FIELDS)
    values = {}
    for key in FIELDS:
        if partial and key not in body:
            continue
        if key == "implementation" and key not in body:
            values[key] = None
            continue
        if key == "title":
            values[key] = v.string(body, key, min_len=1, max_len=200, strip=True)
        elif key == "hypothesis":
            values[key] = v.string(body, key, max_len=MAX_TEXT)
        elif key == "method":
            values[key] = v.enum(body, key, METHODS)
        elif key == "protocol_markdown":
            values[key] = v.string(body, key, max_len=200_000)
        elif key == "variables":
            values[key] = _variables(v, body)
        elif key == "input_artifact_ids":
            values[key] = v.strings(body, key, max_items=50, min_len=1, max_len=100, unique=True)
        elif key == "calibration":
            values[key] = _calibration(v, body)
        elif key == "implementation":
            implementation = body[key]
            if implementation is not None and (not isinstance(implementation, dict) or
                    set(implementation) != {"runtime", "code_artifact_id", "pipeline"}):
                v.error("/implementation", "implementation must be null or contain runtime, code_artifact_id, and pipeline.")
                values[key] = None
            elif implementation is None:
                values[key] = None
            else:
                runtime = v.enum(implementation, "runtime", ("python", "javascript", "shell"), "/implementation")
                code_id = v.string(implementation, "code_artifact_id", "/implementation", min_len=1, max_len=100)
                pipeline = v.enum(implementation, "pipeline", ("script_analysis_v1",), "/implementation")
                values[key] = {"runtime": runtime, "code_artifact_id": code_id, "pipeline": pipeline}
        else:  # success_criteria, limitations
            values[key] = v.strings(body, key)
    v.check()
    return values


def _variables(v: Validator, body: dict):
    items = body.get("variables")
    if not isinstance(items, list) or len(items) > 100:
        v.error("/variables", "variables must be an array of at most 100 objects.")
        return []
    out = []
    for i, item in enumerate(items):
        p = f"/variables/{i}"
        if not v.object(item, p):
            continue
        v.unknown(item, {"name", "role", "description", "unit"}, p)
        out.append({
            "name": v.string(item, "name", p, min_len=1, max_len=200, strip=True),
            "role": v.enum(item, "role", ROLES, p),
            "description": v.string(item, "description", p, max_len=MAX_TEXT),
            "unit": v.string(item, "unit", p, nullable=True, min_len=1, max_len=50),
        })
    return out


def _calibration(v: Validator, body: dict):
    cal, p = body.get("calibration"), "/calibration"
    if not v.object(cal, p):
        return None
    mode = cal.get("mode")
    if mode == "none":
        v.unknown(cal, {"mode", "assumptions"}, p)
        return {"mode": "none", "assumptions": v.strings(cal, "assumptions", p)}
    if mode != "reference_length":
        v.error(f"{p}/mode", "mode must be 'none' or 'reference_length'.")
        return None
    v.unknown(cal, CAL_REFERENCE_FIELDS, p)
    v.string(cal, "artifact_id", p, min_len=1, max_len=100)
    if not (is_int(cal.get("frame_index")) and cal["frame_index"] >= 0):
        v.error(f"{p}/frame_index", "frame_index must be a nonnegative integer.")
    points = []
    for key in ("point_a_px", "point_b_px"):
        point = cal.get(key)
        if isinstance(point, list) and len(point) == 2 and all(is_finite(x) for x in point):
            points.append(point)
        else:
            v.error(f"{p}/{key}", f"{key} must be [x, y] with finite numbers.")
    if len(points) == 2 and points[0] == points[1]:
        v.error(f"{p}/point_b_px", "Calibration points must be distinct.")
    length = cal.get("reference_length_m")
    if not (is_finite(length) and length > 0):
        v.error(f"{p}/reference_length_m", "reference_length_m must be a finite positive number.")
    if "reference_uncertainty_m" not in cal:
        v.error(f"{p}/reference_uncertainty_m", "reference_uncertainty_m is required (number or null).")
    elif cal["reference_uncertainty_m"] is not None and not (
            is_finite(cal["reference_uncertainty_m"]) and cal["reference_uncertainty_m"] >= 0):
        v.error(f"{p}/reference_uncertainty_m", "reference_uncertainty_m must be a finite nonnegative number or null.")
    v.strings(cal, "assumptions", p)
    return {key: cal.get(key) for key in ("mode", "artifact_id", "frame_index", "point_a_px", "point_b_px",
                                          "reference_length_m", "reference_uncertainty_m", "assumptions")}


def check_references(conn, project_id: str, doc: dict) -> None:
    """Referenced artifacts must be ready and in this project; calibration must fit its frame."""
    inputs = require_artifacts(conn, project_id, doc["input_artifact_ids"], "/input_artifact_ids")
    implementation = doc.get("implementation")
    if implementation:
        code = require_one(conn, "artifacts", project_id, implementation["code_artifact_id"], "/implementation/code_artifact_id")
        if code["kind"] != "code" or code["mime_type"] not in ("text/x-python", "text/javascript", "application/javascript", "text/x-shellscript", "text/plain"):
            raise validation_error([{"path": "/implementation/code_artifact_id", "message": "implementation must reference a supported code artifact."}])
        expected = {"python": {"text/x-python", "text/plain"}, "javascript": {"text/javascript", "application/javascript", "text/plain"}, "shell": {"text/x-shellscript", "text/plain"}}[implementation["runtime"]]
        if code["mime_type"] not in expected:
            raise validation_error([{"path": "/implementation/runtime", "message": "runtime does not match the code artifact MIME type."}])
    cal = doc["calibration"]
    if cal["mode"] != "reference_length":
        return
    p = "/calibration"
    artifact = inputs.get(cal["artifact_id"])
    if artifact is None:
        require_one(conn, "artifacts", project_id, cal["artifact_id"], f"{p}/artifact_id")
        raise validation_error([{"path": f"{p}/artifact_id", "message": "Calibration must reference one of input_artifact_ids."}])
    errors = []
    meta = artifact["metadata"]
    if artifact["kind"] not in ("video", "image"):
        errors.append({"path": f"{p}/artifact_id", "message": "Calibration must reference a video or image."})
    elif artifact["kind"] == "image" and cal["frame_index"] != 0:
        errors.append({"path": f"{p}/frame_index", "message": "frame_index must be 0 for an image."})
    elif meta.get("frame_count") is not None and cal["frame_index"] >= meta["frame_count"]:
        errors.append({"path": f"{p}/frame_index", "message": "frame_index is beyond the video's frame count."})
    width, height = meta.get("width_px"), meta.get("height_px")
    if width is None or height is None:
        errors.append({"path": f"{p}/artifact_id", "message": "The artifact has no known frame dimensions."})
    else:
        for key in ("point_a_px", "point_b_px"):
            x, y = cal[key]
            if not (0 <= x < width and 0 <= y < height):
                errors.append({"path": f"{p}/{key}", "message": f"Point must lie inside the {width}x{height} frame."})
    if errors:
        raise validation_error(errors)


# -- helpers for routes and agent tools ----------------------------------------------

def create_experiment(conn, project_id: str, fields: dict) -> dict:
    """Validate and create an Experiment (revision 1) plus experiment.updated event.

    Call inside db.transaction(conn). `fields` holds every creation field. Raises ApiError.
    """
    values = validate_fields(fields, partial=False)
    load_writable(conn, project_id)
    check_references(conn, project_id, values)
    ts = now_ts()
    experiment = {"id": new_id("exp"), "project_id": project_id, **values,
                  "revision": 1, "created_at": ts, "updated_at": ts}
    conn.execute("INSERT INTO experiments (id, project_id, revision, created_at, doc) VALUES (?, ?, ?, ?, ?)",
                 (experiment["id"], project_id, 1, ts, dumps(experiment)))
    record_event(conn, project_id, "experiment.updated", {"experiment": experiment})
    return experiment


def update_experiment(conn, project_id: str, experiment_id: str, changes: dict, *, expected_revision) -> dict:
    """Apply a nonempty subset of creation fields (arrays replace) if the revision matches.

    Call inside db.transaction(conn). expected_revision is required (agent tools pass the
    revision they read). Unchanged values keep the current revision. Raises ApiError
    (404, 409 PROJECT_ARCHIVED, 412 REVISION_CONFLICT, 422).
    """
    if not changes:
        raise validation_error([{"path": "", "message": "At least one field is required."}])
    values = validate_fields(changes, partial=True)
    load_visible(conn, project_id)
    row = conn.execute("SELECT doc FROM experiments WHERE id = ? AND project_id = ?",
                       (experiment_id, project_id)).fetchone()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    current = json.loads(row["doc"])
    if current["revision"] != expected_revision:
        raise ApiError(412, "REVISION_CONFLICT", "The experiment changed since it was loaded. Reload and reconcile edits.",
                       details={"current_revision": current["revision"]})
    load_writable(conn, project_id)
    if all(current.get(k) == val for k, val in values.items()):
        return current
    updated = {**current, **values, "revision": current["revision"] + 1, "updated_at": now_ts()}
    check_references(conn, project_id, updated)
    conn.execute("UPDATE experiments SET revision = ?, doc = ? WHERE id = ?",
                 (updated["revision"], dumps(updated), experiment_id))
    record_event(conn, project_id, "experiment.updated", {"experiment": updated})
    return updated


IMPLEMENTATION_MIMES = {"python": "text/x-python", "javascript": "text/javascript", "shell": "text/x-shellscript"}
MAX_IMPLEMENTATION_BYTES = 256 * 1024


def publish_implementation(conn, artifact_runtime, config, project_id: str, experiment_id: str, *,
                           runtime: str, filename: str, source: str, expected_revision: int):
    """Publish immutable source and point the experiment at it, atomically in DB visibility."""
    from . import artifacts
    from .db import transaction
    from .validation import Validator

    v = Validator()
    v.enum({"runtime": runtime}, "runtime", tuple(IMPLEMENTATION_MIMES))
    filename_issue = artifacts.filename_error(filename)
    if filename_issue:
        v.error("/filename", filename_issue)
    if not isinstance(source, str):
        v.error("/source", "source must be a string.")
        source = ""
    try:
        encoded = source.encode("utf-8", "strict")
    except UnicodeEncodeError:
        encoded = b""
        v.error("/source", "source must be valid UTF-8.")
    if not encoded or len(encoded) > MAX_IMPLEMENTATION_BYTES:
        v.error("/source", f"source must contain 1 to {MAX_IMPLEMENTATION_BYTES} UTF-8 bytes.")
    v.check()
    load_writable(conn, project_id)
    row = conn.execute("SELECT doc FROM experiments WHERE id = ? AND project_id = ?", (experiment_id, project_id)).fetchone()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    current = json.loads(row["doc"])
    if current["revision"] != expected_revision:
        raise ApiError(412, "REVISION_CONFLICT", "The experiment changed since it was loaded. Reload and reconcile edits.",
                       details={"current_revision": current["revision"]})
    os.makedirs(config.upload_tmp_dir, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="implementation-", dir=config.upload_tmp_dir)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        staged = artifacts._stage_owned_file(conn, artifact_runtime, config, project_id, path, filename=filename,
            mime_type=IMPLEMENTATION_MIMES[runtime], kind="code", origin="generated", experiment_id=experiment_id,
            run_id=None, parent_artifact_ids=(), artifact_id=None, extra_metadata=None)
        implementation = {"runtime": runtime, "code_artifact_id": staged["id"], "pipeline": "script_analysis_v1"}
        updated = {**current, "implementation": implementation, "revision": current["revision"] + 1, "updated_at": now_ts()}
        from .events import record_event
        with (transaction(conn) if not conn.in_transaction else nullcontext(conn)):
            load_writable(conn, project_id)
            latest = conn.execute("SELECT doc FROM experiments WHERE id = ? AND project_id = ?", (experiment_id, project_id)).fetchone()
            latest_doc = json.loads(latest["doc"])
            if latest_doc["revision"] != expected_revision:
                raise ApiError(412, "REVISION_CONFLICT", "The experiment changed since it was loaded. Reload and reconcile edits.",
                               details={"current_revision": latest_doc["revision"]})
            published = artifacts.commit_artifact(conn, staged)
            conn.execute("UPDATE experiments SET revision = ?, doc = ? WHERE id = ? AND project_id = ?",
                         (updated["revision"], dumps(updated), experiment_id, project_id))
            record_event(conn, project_id, "experiment.updated", {"experiment": updated})
        return updated, published
    except Exception:
        if 'staged' in locals():
            artifacts.discard_staged(artifact_runtime, staged)
        raise
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


@bp.post("/<project_id>/experiments/<experiment_id>/implementation")
def publish_implementation_route(project_id, experiment_id):
    body = json_body()
    key = idempotency_key()
    v = Validator()
    v.unknown(body, {"runtime", "filename", "source"})
    v.enum(body, "runtime", tuple(IMPLEMENTATION_MIMES))
    v.string(body, "filename", min_len=1, max_len=255)
    v.string(body, "source", min_len=1, max_len=MAX_IMPLEMENTATION_BYTES)
    v.check()
    expected = parse_if_match()
    if expected is None:
        raise ApiError(428, "PRECONDITION_REQUIRED", "If-Match with the experiment's current ETag is required.")
    config = current_app.config["STELLARIS"]
    def build(conn):
        experiment, artifact = publish_implementation(conn, current_app.extensions["stellaris_runtime"], config, project_id, experiment_id,
            runtime=body["runtime"], filename=body["filename"], source=body["source"], expected_revision=expected)
        return 200, {"experiment": experiment, "artifact": artifact}, {"ETag": etag(experiment["revision"])}, artifact["id"]
    return idempotency.run_command(g.db, key, body, build)


# -- routes ---------------------------------------------------------------------------

@bp.post("/<project_id>/experiments")
def create_experiment_route(project_id):
    body = json_body()
    key = idempotency_key()
    validate_fields(body, partial=False)  # Report 422 before touching the database.

    def build(conn):
        experiment = create_experiment(conn, project_id, body)
        headers = {"Location": f"/api/v1/projects/{project_id}/experiments/{experiment['id']}",
                   "ETag": etag(experiment["revision"])}
        return 201, experiment, headers, experiment["id"]

    return idempotency.run_command(g.db, key, body, build)


@bp.get("/<project_id>/experiments")
def list_experiments(project_id):
    load_visible(g.db, project_id)
    rows, next_cursor = project_page(g.db, "experiments", project_id, {})
    return json_response({"items": [json.loads(r["doc"]) for r in rows], "next_cursor": next_cursor})


@bp.get("/<project_id>/experiments/<experiment_id>")
def get_experiment(project_id, experiment_id):
    experiment = get_doc("experiments", project_id, experiment_id)
    return json_response(experiment, 200, {"ETag": etag(experiment["revision"])})


@bp.patch("/<project_id>/experiments/<experiment_id>")
def patch_experiment(project_id, experiment_id):
    body = json_body()
    if not body:
        raise validation_error([{"path": "", "message": "At least one field is required."}])
    validate_fields(body, partial=True)
    expected = parse_if_match()
    if expected is None:
        raise ApiError(428, "PRECONDITION_REQUIRED", "If-Match with the experiment's current ETag is required.")
    with transaction(g.db):
        experiment = update_experiment(g.db, project_id, experiment_id, body, expected_revision=expected)
    return json_response(experiment, 200, {"ETag": etag(experiment["revision"])})
