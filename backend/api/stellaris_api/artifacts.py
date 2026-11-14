"""Uploads, artifacts, content downloads, and artifact publication helpers (Contracts.md section 6).

Storage:
  * In-flight upload bytes: <upload_tmp_dir>/<upload_id>.<random>.part (API volume), renamed to
    <upload_id>.bin once a transfer has the declared size (and hash, if declared).
  * Ready artifacts: /workspace/data/artifacts/<artifact_id> in the project's own volume,
    written and read through the Docker archive API (runtime.ProjectRuntime). Root-owned,
    mode 0444. SQLite holds the metadata; only ready artifacts have rows.

Concurrency: the API runs one Gunicorn process, so an in-process set serializes content
transfers and completion per upload (409 UPLOAD_IN_PROGRESS).
"""

import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from flask import Blueprint, Response, current_app, g, request

from . import db, idempotency
from .db import transaction
from .errors import ApiError, validation_error
from .events import record_event
from .http import (
    TIMESTAMP_FORMAT, canonical_sha256, dumps, idempotency_key, json_body, json_response, new_id, now_ts,
    project_page,
)
from .media import ARTIFACT_KINDS, INLINE_MIME_TYPES, TYPES, UPLOAD_MIME_TYPES, content_type_header, inspect_file
from .projects import load_visible, load_writable
from .refs import require_artifacts, require_one
from .research import get_doc
from .runtime import STREAM_CHUNK, ArtifactMissing, RuntimeUnavailable
from .validation import Validator, is_int, is_timestamp

log = logging.getLogger(__name__)

bp = Blueprint("artifacts", __name__, url_prefix="/api/v1/projects")

UPLOAD_FIELDS = {"filename", "mime_type", "size_bytes", "sha256", "kind", "origin", "experiment_id", "capture"}
UPLOAD_KINDS = ("document", "dataset", "image", "video", "audio", "code")
UPLOAD_ORIGINS = ("observed", "simulated", "reference", "generated")
ARTIFACT_ORIGINS = ("observed", "derived", "simulated", "generated", "reference")
CAPTURE_METHODS = ("browser_camera", "browser_microphone", "file_upload")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
_UNSATISFIABLE = object()

_busy = set()
_busy_lock = threading.Lock()


# -- shared helpers ------------------------------------------------------------------

def filename_error(name):
    """Filenames are display labels only; reject anything path-like or control characters."""
    if not isinstance(name, str) or not 1 <= len(name) <= 255:
        return "filename must be a string of 1-255 characters."
    if (name != name.strip() or name in (".", "..") or "/" in name or "\\" in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        return "filename must be a plain label without path separators, control characters, or surrounding spaces."
    return None


def ensure_tmp_dir(config) -> str:
    os.makedirs(config.upload_tmp_dir, exist_ok=True)
    os.chmod(config.upload_tmp_dir, 0o711)  # ffprobe (uid 65534) may open known names only.
    return config.upload_tmp_dir


def _bin_path(config, upload_id: str) -> str:
    return os.path.join(config.upload_tmp_dir, f"{upload_id}.bin")


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@contextmanager
def _transfer_lock(upload_id: str):
    with _busy_lock:
        if upload_id in _busy:
            raise ApiError(409, "UPLOAD_IN_PROGRESS", "Another transfer or completion for this upload is in progress.",
                           retryable=True, headers={"Retry-After": "2"})
        _busy.add(upload_id)
    try:
        yield
    finally:
        with _busy_lock:
            _busy.discard(upload_id)


def _used_bytes(conn, project_id: str, exclude_upload=None) -> int:
    stored = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM artifacts WHERE project_id = ?",
                          (project_id,)).fetchone()[0]
    reserved = conn.execute(
        "SELECT COALESCE(SUM(declared_size), 0) FROM uploads WHERE project_id = ? "
        "AND status IN ('pending', 'uploaded') AND id IS NOT ?", (project_id, exclude_upload),
    ).fetchone()[0]
    return stored + reserved


def _quota_error() -> ApiError:
    return ApiError(413, "PROJECT_QUOTA_EXCEEDED", "The project's storage quota would be exceeded.")


# -- artifact publication (also used by later worker/agent slices) -------------------

def _hash_file(path: str):
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _stage_owned_file(conn, runtime, config, project_id, path, *, filename, mime_type, kind, origin,
                      experiment_id, run_id, parent_artifact_ids, artifact_id, extra_metadata,
                      exclude_upload=None, upload=False) -> dict:
    v = Validator()
    error = filename_error(filename)
    if error:
        v.error("/filename", error)
    allowed_kinds = TYPES.get(mime_type, (None, None, set(), set()))[2 if upload else 3]
    if mime_type not in TYPES or not allowed_kinds:
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", f"Unsupported artifact media type: {mime_type!r}.")
    if kind not in ARTIFACT_KINDS or kind not in allowed_kinds:
        v.error("/kind", f"kind {kind!r} is not valid for {mime_type}.")
    if origin not in ARTIFACT_ORIGINS:
        v.error("/origin", "origin is invalid.")
    if run_id is not None and not (isinstance(run_id, str) and 1 <= len(run_id) <= 100):
        v.error("/run_id", "run_id must be a string or null.")
    v.check()
    if experiment_id is not None:
        require_one(conn, "experiments", project_id, experiment_id, "/experiment_id")
    parents = list(parent_artifact_ids)
    require_artifacts(conn, project_id, parents, "/parent_artifact_ids")

    size, sha256 = _hash_file(path)
    metadata = {**inspect_file(path, mime_type, config), **(extra_metadata or {})}
    if size > config.max_file_bytes:
        raise ApiError(413, "UPLOAD_TOO_LARGE", "The file exceeds the maximum artifact size.")
    if _used_bytes(conn, project_id, exclude_upload) + size > config.max_project_bytes:
        raise _quota_error()

    artifact_id = artifact_id or new_id("art")
    runtime.store_artifact(project_id, artifact_id, path, config.upload_tmp_dir)
    return {
        "id": artifact_id, "project_id": project_id, "experiment_id": experiment_id, "run_id": run_id,
        "kind": kind, "origin": origin, "filename": filename, "mime_type": mime_type,
        "size_bytes": size, "sha256": sha256, "parent_artifact_ids": parents, "metadata": metadata,
        "created_at": None,
    }


def stage_artifact(conn, runtime, config, project_id: str, *, local_path: str, filename: str, mime_type: str,
                   kind: str, origin: str, experiment_id=None, run_id=None, parent_artifact_ids=()) -> dict:
    """Validate a local file and copy its bytes into the project volume. Not yet visible.

    Copies local_path into the API's temp dir first (so media inspection never reads caller
    paths), hashes it, inspects media, checks references and quotas, then stores it via the
    Docker archive API. Returns the Artifact dict; publish it with commit_artifact() inside a
    transaction (possibly together with other run outputs). Raises ApiError (413/415/422),
    RuntimeUnavailable (Docker), or OSError (unreadable local_path).
    """
    tmp_dir = ensure_tmp_dir(config)
    fd, copy_path = tempfile.mkstemp(prefix="stage-", suffix=".tmp", dir=tmp_dir)
    try:
        with os.fdopen(fd, "wb") as out, open(local_path, "rb") as src:
            while chunk := src.read(1024 * 1024):
                out.write(chunk)
        os.chmod(copy_path, 0o644)
        return _stage_owned_file(conn, runtime, config, project_id, copy_path, filename=filename,
                                 mime_type=mime_type, kind=kind, origin=origin, experiment_id=experiment_id,
                                 run_id=run_id, parent_artifact_ids=parent_artifact_ids, artifact_id=None,
                                 extra_metadata=None)
    finally:
        _remove(copy_path)


def commit_artifact(conn, artifact: dict) -> dict:
    """Make a staged artifact visible: insert its row and artifact.created event.

    Call inside db.transaction(conn). Returns the final Artifact (created_at assigned).
    """
    artifact = {**artifact, "created_at": now_ts()}
    conn.execute(
        "INSERT INTO artifacts (id, project_id, kind, experiment_id, run_id, size_bytes, sha256, created_at, doc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (artifact["id"], artifact["project_id"], artifact["kind"], artifact["experiment_id"], artifact["run_id"],
         artifact["size_bytes"], artifact["sha256"], artifact["created_at"], dumps(artifact)),
    )
    record_event(conn, artifact["project_id"], "artifact.created", {"artifact": artifact}, run_id=artifact["run_id"])
    return artifact


def publish_artifact(runtime, config, project_id: str, *, local_path: str, filename: str, mime_type: str,
                     kind: str, origin: str, experiment_id=None, run_id=None, parent_artifact_ids=()) -> dict:
    """stage_artifact() + commit_artifact() with the helper's own connection and transaction.

    Allowed for archived projects (accepted runs may finish). Returns the ready Artifact.
    """
    conn = db.connect(config.db_path)
    try:
        load_visible(conn, project_id)
        staged = stage_artifact(conn, runtime, config, project_id, local_path=local_path, filename=filename,
                                mime_type=mime_type, kind=kind, origin=origin, experiment_id=experiment_id,
                                run_id=run_id, parent_artifact_ids=parent_artifact_ids)
        with transaction(conn):
            load_visible(conn, project_id)
            return commit_artifact(conn, staged)
    finally:
        conn.close()


def publish_text_artifact(runtime, config, project_id: str, *, text: str, filename: str,
                          mime_type: str = "text/markdown", kind: str = "report", origin: str = "generated",
                          experiment_id=None, run_id=None, parent_artifact_ids=()) -> dict:
    """Publish an immutable UTF-8 text artifact (e.g. a Markdown report or a log)."""
    tmp_dir = ensure_tmp_dir(config)
    fd, path = tempfile.mkstemp(prefix="text-", suffix=".tmp", dir=tmp_dir)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(text.encode("utf-8"))
        return publish_artifact(runtime, config, project_id, local_path=path, filename=filename,
                                mime_type=mime_type, kind=kind, origin=origin, experiment_id=experiment_id,
                                run_id=run_id, parent_artifact_ids=parent_artifact_ids)
    finally:
        _remove(path)


# -- uploads --------------------------------------------------------------------------

def to_upload(row) -> dict:
    return {
        "id": row["id"], "project_id": row["project_id"], "request": json.loads(row["request"]),
        "status": row["status"], "artifact_id": row["artifact_id"], "expires_at": row["expires_at"],
        "error": json.loads(row["error"]) if row["error"] else None,
    }


def _update_upload(conn, upload_id: str, **changes):
    """Update internal upload columns (fixed keyword names only) and emit upload.updated."""
    changes["updated_at"] = now_ts()
    assignments = ", ".join(f"{column} = ?" for column in changes)
    conn.execute(f"UPDATE uploads SET {assignments} WHERE id = ?", [*changes.values(), upload_id])
    row = conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    record_event(conn, row["project_id"], "upload.updated", {"upload": to_upload(row)})
    return row


def _expire(conn, row):
    return _update_upload(conn, row["id"], status="expired", error=dumps(
        {"code": "UPLOAD_EXPIRED", "message": "The upload expired before it was completed."}), error_status=410)


def _is_due(row) -> bool:
    return row["status"] in ("pending", "uploaded") and row["expires_at"] <= now_ts()


def _load_upload(conn, config, project_id: str, upload_id: str):
    """Load a project's upload, persisting expiry (and dropping its temp bytes) when due."""
    with transaction(conn):
        load_visible(conn, project_id)
        row = conn.execute("SELECT * FROM uploads WHERE id = ? AND project_id = ?",
                           (upload_id, project_id)).fetchone()
        if row is None:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
        expired_now = _is_due(row)
        if expired_now:
            row = _expire(conn, row)
    if expired_now:
        _remove(_bin_path(config, row["id"]))
    return row


def _raise_for_terminal(row, *, for_transfer: bool) -> None:
    if row["status"] == "expired":
        raise ApiError(410, "UPLOAD_EXPIRED", "The upload has expired. Create a new upload.")
    if row["status"] == "failed":
        error = json.loads(row["error"])
        if for_transfer:
            raise ApiError(409, "UPLOAD_FAILED", f"The upload failed validation ({error['code']}). Create a new upload.")
        raise ApiError(row["error_status"] or 422, error["code"], error["message"])


def _validate_upload_request(body: dict, config) -> None:
    v = Validator()
    v.unknown(body, UPLOAD_FIELDS)
    error = filename_error(body.get("filename"))
    if error:
        v.error("/filename", error)
    mime_type = v.string(body, "mime_type", min_len=1, max_len=255)
    size = body.get("size_bytes")
    if not is_int(size) or size < 1:
        v.error("/size_bytes", "size_bytes must be a positive integer.")
    sha256 = v.string(body, "sha256", required=False, max_len=64)
    if sha256 is not None and not _SHA256.match(sha256):
        v.error("/sha256", "sha256 must be 64 lowercase hexadecimal characters.")
    kind = v.enum(body, "kind", UPLOAD_KINDS)
    v.enum(body, "origin", UPLOAD_ORIGINS)
    v.string(body, "experiment_id", required=False, min_len=1, max_len=100)
    if "capture" in body and v.object(body["capture"], "/capture"):
        capture, p = body["capture"], "/capture"
        v.unknown(capture, {"method", "recorded_at", "recording_permission_confirmed"}, p)
        method = v.enum(capture, "method", CAPTURE_METHODS, p)
        if "recorded_at" not in capture or not (capture["recorded_at"] is None or is_timestamp(capture["recorded_at"])):
            v.error(f"{p}/recorded_at", "recorded_at is required and must be an RFC 3339 timestamp or null.")
        confirmed = capture.get("recording_permission_confirmed")
        if not isinstance(confirmed, bool):
            v.error(f"{p}/recording_permission_confirmed", "recording_permission_confirmed must be a boolean.")
        elif method in ("browser_camera", "browser_microphone") and not confirmed:
            v.error(f"{p}/recording_permission_confirmed", "Browser recordings require recording_permission_confirmed: true.")
    v.check()
    if mime_type not in UPLOAD_MIME_TYPES:
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "mime_type is not accepted for upload.",
                       details={"accepted_mime_types": UPLOAD_MIME_TYPES})
    if kind not in TYPES[mime_type][2]:
        raise validation_error([{"path": "/kind", "message": f"kind {kind!r} is not valid for {mime_type}."}])
    if size > config.max_file_bytes:
        raise ApiError(413, "UPLOAD_TOO_LARGE", "size_bytes exceeds the maximum file size.",
                       details={"max_file_bytes": config.max_file_bytes})


@bp.post("/<project_id>/uploads")
def create_upload(project_id):
    config = current_app.config["STELLARIS"]
    body = json_body()
    key = idempotency_key()
    _validate_upload_request(body, config)

    def build(conn):
        load_writable(conn, project_id)
        if "experiment_id" in body:
            require_one(conn, "experiments", project_id, body["experiment_id"], "/experiment_id")
        if _used_bytes(conn, project_id) + body["size_bytes"] > config.max_project_bytes:
            raise _quota_error()
        upload_id, ts = new_id("upl"), now_ts()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=config.upload_expiry_s)).strftime(TIMESTAMP_FORMAT)
        conn.execute(
            "INSERT INTO uploads (id, project_id, request, status, reserved_artifact_id, declared_size, "
            "expires_at, created_at, updated_at) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)",
            (upload_id, project_id, dumps(body), new_id("art"), body["size_bytes"], expires, ts, ts),
        )
        upload = to_upload(conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone())
        record_event(conn, project_id, "upload.updated", {"upload": upload})
        return 201, upload, {"Location": f"/api/v1/projects/{project_id}/uploads/{upload_id}"}, upload_id

    return idempotency.run_command(g.db, key, body, build)


@bp.get("/<project_id>/uploads/<upload_id>")
def get_upload(project_id, upload_id):
    config = current_app.config["STELLARIS"]
    return json_response(to_upload(_load_upload(g.db, config, project_id, upload_id)))


def _receive(path: str, limit: int):
    """Stream the raw request body to `path`, counting actual bytes (not Content-Length)."""
    stream = request.environ["wsgi.input"]  # Gunicorn decodes chunked transfer encoding.
    digest, size = hashlib.sha256(), 0
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as out:
        while True:
            try:
                chunk = stream.read(1024 * 1024)
            except (OSError, ValueError):
                raise ApiError(400, "BAD_REQUEST", "The upload transfer was interrupted. Retry the PUT.", retryable=True)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ApiError(413, "UPLOAD_TOO_LARGE", "More bytes were sent than the upload declared.")
            digest.update(chunk)
            out.write(chunk)
    return size, digest.hexdigest()


@bp.put("/<project_id>/uploads/<upload_id>/content")
def put_upload_content(project_id, upload_id):
    config = current_app.config["STELLARIS"]
    conn = g.db
    row = _load_upload(conn, config, project_id, upload_id)
    load_writable(conn, project_id)
    _raise_for_terminal(row, for_transfer=True)
    req = json.loads(row["request"])
    if request.mimetype != req["mime_type"]:
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Content-Type must match the upload's declared mime_type.")
    declared = row["declared_size"]
    if request.content_length is not None and request.content_length > declared:
        raise ApiError(413, "UPLOAD_TOO_LARGE", "Content-Length exceeds the upload's declared size_bytes.")

    with _transfer_lock(row["id"]):
        part = os.path.join(ensure_tmp_dir(config), f"{row['id']}.{uuid.uuid4().hex}.part")
        try:
            size, digest = _receive(part, declared)
            with transaction(conn):
                load_writable(conn, project_id)
                current = conn.execute("SELECT * FROM uploads WHERE id = ?", (row["id"],)).fetchone()
                if current["status"] in ("uploaded", "completed"):
                    if (size, digest) != (current["received_bytes"], current["received_sha256"]):
                        raise ApiError(409, "UPLOAD_CONTENT_CONFLICT",
                                       "Different content was already transferred for this upload.")
                    return Response(status=204)
                if _is_due(current):
                    raise ApiError(410, "UPLOAD_EXPIRED", "The upload has expired. Create a new upload.")
                _raise_for_terminal(current, for_transfer=True)
                if size != declared:
                    raise validation_error([{"path": "/size_bytes", "message":
                                             f"Received {size} bytes but the upload declared {declared}."}])
                if req.get("sha256") and digest != req["sha256"]:
                    raise ApiError(422, "HASH_MISMATCH", "The transferred bytes do not match the declared sha256.")
                os.replace(part, _bin_path(config, row["id"]))
                _update_upload(conn, row["id"], status="uploaded", received_bytes=size, received_sha256=digest)
            return Response(status=204)
        finally:
            _remove(part)


@bp.post("/<project_id>/uploads/<upload_id>/complete")
def complete_upload(project_id, upload_id):
    config = current_app.config["STELLARIS"]
    runtime = current_app.extensions["stellaris_runtime"]
    body = json_body()
    key = idempotency_key()
    if body:
        raise validation_error([{"path": f"/{k}", "message": "Unknown field."} for k in sorted(body)])
    conn = g.db
    row = _load_upload(conn, config, project_id, upload_id)
    scope, body_hash = idempotency.request_scope(), canonical_sha256(body)

    with _transfer_lock(row["id"]):
        with transaction(conn):
            idempotency.purge_expired(conn)
            key_row, replayed = idempotency.claim(conn, scope, key, body_hash)
            if replayed is not None:
                return replayed
            current = conn.execute("SELECT * FROM uploads WHERE id = ?", (row["id"],)).fetchone()
            if current["status"] == "completed":  # Always the same artifact, even after key expiry.
                artifact = get_doc("artifacts", project_id, current["artifact_id"])
                if key_row is None:
                    idempotency.begin(conn, scope, key, body_hash, artifact["id"])
                idempotency.complete(conn, scope, key, 200, dumps(artifact), {})
                return json_response(artifact)
            _raise_for_terminal(current, for_transfer=False)
            load_writable(conn, project_id)
            if current["status"] != "uploaded":
                raise ApiError(409, "ARTIFACT_NOT_READY", "Upload content has not been transferred yet.")
            if key_row is None:
                idempotency.begin(conn, scope, key, body_hash, current["reserved_artifact_id"])

        req = json.loads(current["request"])
        bin_path = _bin_path(config, current["id"])
        try:
            staged = _stage_owned_file(
                conn, runtime, config, project_id, bin_path, filename=req["filename"], mime_type=req["mime_type"],
                kind=req["kind"], origin=req["origin"], experiment_id=req.get("experiment_id"), run_id=None,
                parent_artifact_ids=(), artifact_id=current["reserved_artifact_id"],
                extra_metadata={"uploaded_at": now_ts()}, exclude_upload=current["id"], upload=True,
            )
            if staged["sha256"] != current["received_sha256"] or staged["size_bytes"] != current["received_bytes"]:
                raise RuntimeError("Temporary upload bytes changed after transfer.")
        except ApiError as err:
            content_invalid = err.status in (415, 422) and err.code != "INVALID_REFERENCE"
            with transaction(conn):
                if content_invalid:
                    _update_upload(conn, current["id"], status="failed",
                                   error=dumps({"code": err.code, "message": err.message}), error_status=err.status)
                idempotency.mark_failed(conn, scope, key)
            if content_invalid:
                _remove(bin_path)
            raise
        except RuntimeUnavailable as exc:
            log.error("Storing upload %s failed: %s", current["id"], exc)
            with transaction(conn):
                idempotency.mark_failed(conn, scope, key)
            raise ApiError(503, "SERVICE_UNAVAILABLE", "Project storage is temporarily unavailable.",
                           retryable=True, headers={"Retry-After": "5"})
        except BaseException:
            with transaction(conn):
                idempotency.mark_failed(conn, scope, key)
            raise

        with transaction(conn):
            artifact = commit_artifact(conn, staged)
            _update_upload(conn, current["id"], status="completed", artifact_id=artifact["id"])
            idempotency.complete(conn, scope, key, 200, dumps(artifact), {})
    _remove(bin_path)
    return json_response(artifact)


def cleanup_uploads(config) -> None:
    """Startup: expire due uploads and delete temp bytes no live upload needs.

    Runs before serving, so no transfer is in flight and every *.part file is abandoned.
    """
    tmp_dir = ensure_tmp_dir(config)
    conn = db.connect(config.db_path)
    try:
        with transaction(conn):
            for row in conn.execute("SELECT * FROM uploads WHERE status IN ('pending', 'uploaded')").fetchall():
                if _is_due(row):
                    _expire(conn, row)
            keep = {f"{r['id']}.bin" for r in conn.execute("SELECT id FROM uploads WHERE status = 'uploaded'")}
    finally:
        conn.close()
    for name in os.listdir(tmp_dir):
        if name not in keep:
            _remove(os.path.join(tmp_dir, name))


# -- artifacts ------------------------------------------------------------------------

@bp.get("/<project_id>/artifacts")
def list_artifacts(project_id):
    load_visible(g.db, project_id)
    rows, next_cursor = project_page(g.db, "artifacts", project_id, {
        "kind": ("kind", ARTIFACT_KINDS), "experiment_id": ("experiment_id", None), "run_id": ("run_id", None),
    })
    return json_response({"items": [json.loads(r["doc"]) for r in rows], "next_cursor": next_cursor})


@bp.get("/<project_id>/artifacts/<artifact_id>")
def get_artifact(project_id, artifact_id):
    return json_response(get_doc("artifacts", project_id, artifact_id))


def _parse_range(header: str, size: int):
    """Single byte range -> (start, end) inclusive, _UNSATISFIABLE, or None (ignore the header)."""
    match = _RANGE.match(header.strip())
    if not match or (not match.group(1) and not match.group(2)):
        return None  # Multiple or malformed ranges: serve the full representation.
    first, last = match.group(1), match.group(2)
    if not first:
        suffix = int(last)
        if suffix == 0 or size == 0:
            return _UNSATISFIABLE
        return max(0, size - suffix), size - 1
    start = int(first)
    end = int(last) if last else size - 1
    if last and end < start:
        return None
    if start >= size:
        return _UNSATISFIABLE
    return start, min(end, size - 1)


def _content_disposition(disposition: str, filename: str) -> str:
    fallback = "".join(c if 32 <= ord(c) < 127 and c not in '"\\;' else "_" for c in filename)
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _stream(reader, close, start: int, length: int, expected_sha256, artifact_id: str):
    """Yield [start, start+length) with bounded memory. For a full read, verify the hash and
    hold back the final chunk so a mismatch truncates the response instead of completing it."""
    try:
        skip = start
        while skip:
            chunk = reader.read(min(STREAM_CHUNK, skip))
            if not chunk:
                raise OSError(f"artifact {artifact_id} is shorter than recorded")
            skip -= len(chunk)
        digest = hashlib.sha256() if expected_sha256 else None
        left, held = length, None
        while left:
            chunk = reader.read(min(STREAM_CHUNK, left))
            if not chunk:
                raise OSError(f"artifact {artifact_id} is shorter than recorded")
            left -= len(chunk)
            if digest:
                digest.update(chunk)
            if held is not None:
                yield held
            held = chunk
        if digest and digest.hexdigest() != expected_sha256:
            log.error("Integrity failure: stored bytes of %s do not match the recorded sha256", artifact_id)
            raise OSError(f"artifact {artifact_id} failed integrity verification")
        if held is not None:
            yield held
    finally:
        close()


@bp.get("/<project_id>/artifacts/<artifact_id>/content")
def artifact_content(project_id, artifact_id):
    artifact = get_doc("artifacts", project_id, artifact_id)
    disposition = request.args.get("disposition", "attachment")
    if disposition not in ("attachment", "inline"):
        raise ApiError(400, "INVALID_QUERY", "disposition must be 'attachment' or 'inline'.")
    if disposition == "inline" and artifact["mime_type"] not in INLINE_MIME_TYPES:
        raise ApiError(400, "INVALID_QUERY", "This media type can only be downloaded as an attachment.")

    size, sha256 = artifact["size_bytes"], artifact["sha256"]
    tag = f'"{sha256}"'
    start, end, status = 0, size - 1, 200
    range_header = request.headers.get("Range")
    if range_header and request.headers.get("If-Range", tag) == tag:
        parsed = _parse_range(range_header, size)
        if parsed is _UNSATISFIABLE:
            raise ApiError(416, "RANGE_NOT_SATISFIABLE", "The requested byte range is not satisfiable.",
                           headers={"Content-Range": f"bytes */{size}"})
        if parsed is not None:
            (start, end), status = parsed, 206

    runtime = current_app.extensions["stellaris_runtime"]
    try:
        stored_size, reader, close = runtime.open_artifact(project_id, artifact["id"])
    except RuntimeUnavailable as exc:
        log.error("Artifact read failed: %s", exc)
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Project storage is temporarily unavailable.",
                       retryable=True, headers={"Retry-After": "5"})
    except ArtifactMissing as exc:
        log.error("Artifact bytes missing: %s", exc)
        raise ApiError(500, "INTERNAL_ERROR", "Stored artifact content is unavailable.")
    if stored_size != size:
        close()
        log.error("Artifact %s stored size %d differs from recorded %d", artifact["id"], stored_size, size)
        raise ApiError(500, "INTERNAL_ERROR", "Stored artifact content is inconsistent.")

    length = end - start + 1
    body = _stream(reader, close, start, length, sha256 if status == 200 else None, artifact["id"])
    response = Response(body, status=status, content_type=content_type_header(artifact["mime_type"]))
    response.headers["Content-Length"] = str(length)
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["ETag"] = tag
    response.headers["Content-Disposition"] = _content_disposition(disposition, artifact["filename"])
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; media-src 'self'; img-src 'self'; sandbox"
    if status == 206:
        response.headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return response
