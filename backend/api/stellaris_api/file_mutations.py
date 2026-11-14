"""Workspace file mutations: notes, note revisions, user tags, and tag CRUD (plan slice 2).

Contract: docs/file-workspace-contract.md sections 6, 7, 9, 11, and 12. Routes register on the
`files` blueprint (imported at the end of files.py).

Every mutation:
  * validates its body before touching the catalog (422; unpaired surrogates included),
  * opens the project catalog and projects legacy changes (files._open),
  * commits its catalog changes, idempotency record (POST), and `catalog.changed` outbox row
    in ONE catalog transaction, re-checking `load_writable` inside it,
  * relays the outbox to the main event stream only after that transaction has committed.

Accepted race: the archive check reads the main DB, which cannot share an atomic commit
with the catalog. A project archived in the instant between that check and the catalog
commit may receive one last catalog mutation. Legacy evidence is never affected.
"""

import functools
import hashlib
import logging
import re
import sqlite3

from flask import Response, current_app, g, request

from . import catalog, idempotency
from .artifacts import filename_error
from .db import transaction
from .errors import ApiError, validation_error
from .files import _NOT_FOUND, TAG_SLUG, _file_row, _open, _tag_counts, _to_files, _to_tag, _unavailable, bp
from .http import (
    decode_cursor, encode_cursor, etag, idempotency_key, json_body, json_response, new_id, now_ts, page_limit,
    parse_if_match,
)
from .projects import load_visible, load_writable
from .validation import Validator, invalid_reference, is_int

log = logging.getLogger(__name__)

NOTE_MIME_TYPES = ("text/markdown", "text/plain")
MAX_NOTE_CONTENT_BYTES = 512 * 1024
MAX_USER_TAGS = 32
MAX_PROJECT_TAGS = 500
MAX_BATCH_FILES = 100
MAX_EVENT_CHANGES = 100
COLOR = re.compile(r"#[0-9a-f]{6}")


# -- shared plumbing -----------------------------------------------------------------------

def _catalog_errors(view):
    """Map SQLite failures (locked, I/O, corruption) to a safe retryable 503."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except sqlite3.Error:
            log.exception("Catalog mutation failed (request_id=%s)", g.get("request_id"))
            raise _unavailable("The project's file catalog is busy or unavailable. Retry shortly.")
    return wrapper


def _relay(project_id: str) -> None:
    """After commit only: deliver pending catalog events (best effort; retried later)."""
    catalog.relay_pending(g.db, g.catalog, project_id)


def _text_errors(value, path: str, errors: list) -> None:
    """Reject strings that cannot be UTF-8 encoded (unpaired surrogates from JSON escapes)."""
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            errors.append({"path": path, "message": "Text must be valid Unicode without unpaired surrogates."})
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _text_errors(item, f"{path}/{i}", errors)
    elif isinstance(value, dict):
        for k, item in value.items():
            _text_errors(k, path, errors)
            _text_errors(item, f"{path}/{k}" if _encodable(k) else path, errors)


def _encodable(text: str) -> bool:
    try:
        text.encode("utf-8")
        return True
    except UnicodeEncodeError:
        return False


def _body() -> dict:
    body = json_body()
    errors = []
    _text_errors(body, "", errors)
    if errors:
        raise validation_error(errors)
    return body


def _require_if_match(what: str) -> int:
    expected = parse_if_match()
    if expected is None:
        raise ApiError(428, "PRECONDITION_REQUIRED", f"If-Match with the {what}'s current ETag is required.")
    return expected


def _check_revision(current: int, expected: int, what: str) -> None:
    if current != expected:
        raise ApiError(412, "REVISION_CONFLICT", f"The {what} changed since it was loaded. Reload and reconcile edits.",
                       details={"current_revision": current})


def _slugs(v: Validator, body: dict, key: str, max_items: int) -> list:
    """A list of unique tag slugs. Types are checked before any set/sort operation."""
    value = body.get(key, [])
    if not isinstance(value, list) or len(value) > max_items:
        v.error(f"/{key}", f"{key} must be an array of at most {max_items} tag slugs.")
        return []
    bad = [i for i, s in enumerate(value) if not isinstance(s, str) or not TAG_SLUG.fullmatch(s)]
    for i in bad:
        v.error(f"/{key}/{i}", "Expected a tag slug matching ^[a-z0-9][a-z0-9-]{0,47}$.")
    if bad:
        return []
    if len(set(value)) != len(value):
        v.error(f"/{key}", f"{key} must not contain duplicates.")
    return list(value)


def _note_name(v: Validator, body: dict, required: bool):
    if "name" not in body:
        if required:
            v.error("/name", "name is required.")
        return None
    error = filename_error(body["name"])
    if error:
        v.error("/name", error)
        return None
    return body["name"]


def _note_bytes(v: Validator, body: dict, required: bool):
    if "content" not in body:
        if required:
            v.error("/content", "content is required.")
        return None
    content = body["content"]
    if not isinstance(content, str):
        v.error("/content", "content must be a string.")
        return None
    if "\x00" in content:
        v.error("/content", "content must not contain NUL characters.")
        return None
    data = content.encode("utf-8")  # Surrogates were rejected by _body().
    if len(data) > MAX_NOTE_CONTENT_BYTES:
        v.error("/content", f"content must be at most {MAX_NOTE_CONTENT_BYTES} UTF-8 bytes.")
        return None
    return data


def _check_quota(cat, added: int) -> None:
    limit = current_app.config["STELLARIS"].max_note_bytes
    used = cat.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM note_revisions").fetchone()[0]
    if used + added > limit:
        raise ApiError(413, "PROJECT_QUOTA_EXCEEDED", "The project's retained note storage would be exceeded.",
                       details={"max_bytes": limit})


def _emit(cat, changes: list) -> None:
    """Enqueue one catalog.changed payload (1..100 entries) in the caller's catalog transaction."""
    if not changes:
        return
    if len(changes) > MAX_EVENT_CHANGES:
        others = [c for c in changes if c["entity"] != "file"][:MAX_EVENT_CHANGES - 1]
        changes = others + [{"entity": "file", "id": None, "revision": None, "deleted": False, "bulk": True}]
    catalog.enqueue_event(cat, changes)


def _file_change(row) -> dict:
    return {"entity": "file", "id": row["id"], "revision": row["revision"], "deleted": False}


def _bump(cat, file_id: str, sets: dict):
    """Apply trusted column changes, increase the file's revision, and return the fresh row."""
    sets = {**sets, "updated_at": now_ts()}
    assignments = "".join(f"{column} = ?, " for column in sets)
    cat.execute(f"UPDATE files SET {assignments}revision = revision + 1 WHERE id = ?", [*sets.values(), file_id])
    return _file_row(cat, file_id)


# -- tag assignments -----------------------------------------------------------------------

def _assignments(cat, file_id: str) -> dict:
    return {r["slug"]: r["assigned_by"] for r in cat.execute(
        "SELECT slug, assigned_by FROM file_tags WHERE file_id = ?", (file_id,))}


def _ensure_tags(cat, slugs, changes: list) -> None:
    """Create missing slugs as user tags (label = slug)."""
    if not slugs:
        return
    marks = ",".join("?" * len(slugs))
    existing = {r["slug"] for r in cat.execute(f"SELECT slug FROM tags WHERE slug IN ({marks})", list(slugs))}
    missing = sorted(set(slugs) - existing)
    if not missing:
        return
    total = cat.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    if total + len(missing) > MAX_PROJECT_TAGS:
        raise validation_error([{"path": "", "message": f"A project may have at most {MAX_PROJECT_TAGS} tags."}])
    ts = now_ts()
    for slug in missing:
        cat.execute("INSERT INTO tags (slug, label, color, system, revision, created_at, updated_at) "
                    "VALUES (?, ?, NULL, 0, 1, ?, ?)", (slug, slug, ts, ts))
        changes.append({"entity": "tag", "id": slug, "revision": 1, "deleted": False})


def _apply_user_tags(cat, file_id: str, add, remove, path: str, changes: list) -> bool:
    """Add/remove USER assignments only. Slugs already assigned (by anyone) are no-ops on add;
    system assignments are never removed. Returns whether assignments changed."""
    current = _assignments(cat, file_id)
    add = [s for s in add if s not in current]
    remove = [s for s in remove if current.get(s) == "user"]
    user_count = sum(1 for by in current.values() if by == "user") + len(add) - len(remove)
    if user_count > MAX_USER_TAGS:
        raise validation_error([{"path": path, "message": f"A file may carry at most {MAX_USER_TAGS} user tags."}])
    _ensure_tags(cat, add, changes)
    ts = now_ts()
    for slug in add:
        cat.execute("INSERT INTO file_tags (file_id, slug, assigned_by, created_at) VALUES (?, ?, 'user', ?)",
                    (file_id, slug, ts))
    for slug in remove:
        cat.execute("DELETE FROM file_tags WHERE file_id = ? AND slug = ? AND assigned_by = 'user'", (file_id, slug))
    return bool(add or remove)


# -- notes ---------------------------------------------------------------------------------

@bp.post("/<project_id>/files")
@_catalog_errors
def create_note(project_id):
    load_visible(g.db, project_id)
    body = _body()
    key = idempotency_key()
    v = Validator()
    v.unknown(body, {"name", "content", "mime_type", "tags"})
    name = _note_name(v, body, required=True)
    data = _note_bytes(v, body, required=True)
    mime_type = v.enum(body, "mime_type", NOTE_MIME_TYPES, required=False, default="text/markdown")
    tags = _slugs(v, body, "tags", MAX_USER_TAGS)
    v.check()
    cat = _open(project_id)

    def build(conn):
        load_writable(g.db, project_id)
        _check_quota(conn, len(data))
        file_id, ts, sha256 = new_id("fil"), now_ts(), hashlib.sha256(data).hexdigest()
        conn.execute(
            "INSERT INTO files (id, file_kind, origin_type, origin_id, origin_revision, name, name_key, mime_type, "
            "size_bytes, content_sha256, scientific_origin, status, content_revision, render_version, revision, "
            "created_at, updated_at) VALUES (?, 'note', NULL, NULL, NULL, ?, ?, ?, ?, ?, NULL, 'active', 1, NULL, 1, ?, ?)",
            (file_id, name, name.casefold(), mime_type, len(data), sha256, ts, ts),
        )
        conn.execute("INSERT INTO note_revisions (file_id, content_revision, name, mime_type, content, size_bytes, "
                     "sha256, created_at) VALUES (?, 1, ?, ?, ?, ?, ?, ?)",
                     (file_id, name, mime_type, data.decode("utf-8"), len(data), sha256, ts))
        conn.execute("INSERT INTO file_tags (file_id, slug, assigned_by, created_at) VALUES (?, 'notes', 'system', ?)",
                     (file_id, ts))
        changes = []
        _apply_user_tags(conn, file_id, tags, [], "/tags", changes)
        row = _file_row(conn, file_id)
        _emit(conn, [_file_change(row), *changes])
        item = _to_files(conn, project_id, [row])[0]
        return 201, item, {"Location": f"/api/v1/projects/{project_id}/files/{file_id}", "ETag": etag(1)}, file_id

    response = idempotency.run_command(cat, key, body, build)
    _relay(project_id)
    return response


@bp.patch("/<project_id>/files/<file_id>")
@_catalog_errors
def patch_file(project_id, file_id):
    load_visible(g.db, project_id)
    body = _body()
    v = Validator()
    if not body:
        v.error("", "At least one field is required.")
    v.unknown(body, {"name", "content", "status", "tags"})
    name = _note_name(v, body, required=False)
    data = _note_bytes(v, body, required=False)
    status = v.enum(body, "status", ("active", "trashed"), required=False)
    tags = _slugs(v, body, "tags", MAX_USER_TAGS) if "tags" in body else None
    v.check()
    expected = _require_if_match("file")
    cat = _open(project_id)

    with transaction(cat):
        load_writable(g.db, project_id)
        row = _file_row(cat, file_id)
        _check_revision(row["revision"], expected, "file")
        if row["file_kind"] != "note" and {"name", "content", "status"} & set(body):
            raise ApiError(409, "FILE_READ_ONLY", "Only notes have an editable name, content, or status.")
        sets, changes = {}, []
        if name is not None and name != row["name"]:
            sets.update(name=name, name_key=name.casefold())
        if status is not None and status != row["status"]:
            sets["status"] = status
        if data is not None:
            sha256 = hashlib.sha256(data).hexdigest()
            if sha256 != row["content_sha256"]:  # Identical content creates no revision.
                _check_quota(cat, len(data))
                revision = row["content_revision"] + 1
                cat.execute("INSERT INTO note_revisions (file_id, content_revision, name, mime_type, content, "
                            "size_bytes, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (file_id, revision, sets.get("name", row["name"]), row["mime_type"],
                             data.decode("utf-8"), len(data), sha256, now_ts()))
                sets.update(content_revision=revision, size_bytes=len(data), content_sha256=sha256)
        tags_changed = False
        if tags is not None:  # Replaces user assignments; system assignments always remain.
            current_user = [s for s, by in _assignments(cat, file_id).items() if by == "user"]
            tags_changed = _apply_user_tags(cat, file_id, tags, [s for s in current_user if s not in tags],
                                            "/tags", changes)
        if sets or tags_changed:
            row = _bump(cat, file_id, sets)
            _emit(cat, [_file_change(row), *changes])
        item = _to_files(cat, project_id, [row])[0]
    _relay(project_id)
    return json_response(item, 200, {"ETag": etag(item["revision"])})


@bp.get("/<project_id>/files/<file_id>/revisions")
@_catalog_errors
def list_revisions(project_id, file_id):
    """Page<NoteRevision> in ascending content_revision order (append-only history)."""
    load_visible(g.db, project_id)
    limit = page_limit()
    after = 0
    cursor = request.args.get("cursor")
    if cursor:
        state = decode_cursor(cursor)
        if (state.get("v") != 1 or state.get("t") != "note_revisions" or state.get("p") != project_id
                or state.get("f") != file_id or not is_int(state.get("k")) or state["k"] < 0):
            raise ApiError(400, "INVALID_CURSOR", "cursor is invalid.")
        after = state["k"]
    cat = _open(project_id)
    row = _file_row(cat, file_id)
    if row["file_kind"] != "note":
        raise ApiError(409, "FILE_KIND_UNSUPPORTED", "Only notes have content revisions.")
    rows = cat.execute("SELECT * FROM note_revisions WHERE file_id = ? AND content_revision > ? "
                       "ORDER BY content_revision LIMIT ?", (file_id, after, limit + 1)).fetchall()
    items = [{"file_id": r["file_id"], "content_revision": r["content_revision"], "name": r["name"],
              "mime_type": r["mime_type"], "size_bytes": r["size_bytes"], "content_sha256": r["sha256"],
              "created_at": r["created_at"]} for r in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        next_cursor = encode_cursor({"v": 1, "t": "note_revisions", "p": project_id, "f": file_id,
                                     "k": items[-1]["content_revision"]})
    return json_response({"items": items, "next_cursor": next_cursor})


@bp.post("/<project_id>/files/tagging")
@_catalog_errors
def tag_files(project_id):
    load_visible(g.db, project_id)
    body = _body()
    key = idempotency_key()
    v = Validator()
    v.unknown(body, {"file_ids", "add", "remove"})
    file_ids = v.strings(body, "file_ids", max_items=MAX_BATCH_FILES, min_len=1, max_len=100, unique=True)
    if "file_ids" in body and isinstance(body["file_ids"], list) and not body["file_ids"]:
        v.error("/file_ids", "file_ids must contain at least one file ID.")
    add = _slugs(v, body, "add", MAX_USER_TAGS)
    remove = _slugs(v, body, "remove", MAX_USER_TAGS)
    if not add and not remove:
        v.error("", "add or remove must contain at least one tag slug.")
    if set(add) & set(remove):
        v.error("/remove", "add and remove must not overlap.")
    v.check()
    cat = _open(project_id)

    def build(conn):
        load_writable(g.db, project_id)
        rows, missing = {}, []
        for i, fid in enumerate(file_ids):
            row = conn.execute("SELECT * FROM files WHERE id = ?", (fid,)).fetchone()
            if row is None:
                missing.append({"path": f"/file_ids/{i}", "message": "File not found in this project."})
            rows[fid] = row
        if missing:
            raise invalid_reference(missing)
        protected = [{"path": f"/remove/{j}", "message": f"{slug!r} is a system assignment and cannot be removed."}
                     for fid in file_ids for j, slug in enumerate(remove)
                     if _assignments(conn, fid).get(slug) == "system"]
        if protected:
            raise validation_error(protected)
        changes, file_changes = [], []
        for i, fid in enumerate(file_ids):  # Any error rolls back the whole batch.
            if _apply_user_tags(conn, fid, add, remove, f"/file_ids/{i}", changes):
                rows[fid] = _bump(conn, fid, {})
                file_changes.append(_file_change(rows[fid]))
        _emit(conn, file_changes + changes)
        return 200, {"files": _to_files(conn, project_id, [rows[fid] for fid in file_ids])}, {}, None

    response = idempotency.run_command(cat, key, body, build)
    _relay(project_id)
    return response


# -- tags ----------------------------------------------------------------------------------

def _tag_fields(v: Validator, body: dict) -> dict:
    values = {}
    if "label" in body:
        values["label"] = v.string(body, "label", min_len=1, max_len=64, strip=True)
    if "color" in body:
        color = body["color"]
        if color is not None and (not isinstance(color, str) or not COLOR.fullmatch(color)):
            v.error("/color", "color must be a lowercase #rrggbb string or null.")
        values["color"] = color
    return values


def _tag_row(cat, slug: str):
    row = cat.execute("SELECT * FROM tags WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise ApiError(404, *_NOT_FOUND)
    return row


def _tag_json(cat, row) -> dict:
    return _to_tag(row, _tag_counts(cat, [row["slug"]]).get(row["slug"], 0))


@bp.post("/<project_id>/tags")
@_catalog_errors
def create_tag(project_id):
    load_visible(g.db, project_id)
    body = _body()
    key = idempotency_key()
    v = Validator()
    v.unknown(body, {"slug", "label", "color"})
    slug = body.get("slug")
    if not isinstance(slug, str) or not TAG_SLUG.fullmatch(slug):
        v.error("/slug", "slug is required and must match ^[a-z0-9][a-z0-9-]{0,47}$.")
    values = _tag_fields(v, body)
    v.check()
    cat = _open(project_id)

    def build(conn):
        load_writable(g.db, project_id)
        if conn.execute("SELECT 1 FROM tags WHERE slug = ?", (slug,)).fetchone():
            raise ApiError(409, "TAG_EXISTS", "A tag with this slug already exists.")
        if conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0] >= MAX_PROJECT_TAGS:
            raise validation_error([{"path": "/slug", "message": f"A project may have at most {MAX_PROJECT_TAGS} tags."}])
        ts = now_ts()
        conn.execute("INSERT INTO tags (slug, label, color, system, revision, created_at, updated_at) "
                     "VALUES (?, ?, ?, 0, 1, ?, ?)", (slug, values.get("label") or slug, values.get("color"), ts, ts))
        _emit(conn, [{"entity": "tag", "id": slug, "revision": 1, "deleted": False}])
        tag = _tag_json(conn, _tag_row(conn, slug))
        return 201, tag, {"Location": f"/api/v1/projects/{project_id}/tags/{slug}", "ETag": etag(1)}, slug

    response = idempotency.run_command(cat, key, body, build)
    _relay(project_id)
    return response


@bp.patch("/<project_id>/tags/<slug>")
@_catalog_errors
def patch_tag(project_id, slug):
    load_visible(g.db, project_id)
    body = _body()
    v = Validator()
    if not body:
        v.error("", "At least one field is required.")
    v.unknown(body, {"label", "color"})
    values = _tag_fields(v, body)
    v.check()
    expected = _require_if_match("tag")
    cat = _open(project_id)
    with transaction(cat):
        load_writable(g.db, project_id)
        row = _tag_row(cat, slug)
        _check_revision(row["revision"], expected, "tag")
        changed = {k: val for k, val in values.items() if row[k] != val}
        if changed:
            assignments = "".join(f"{column} = ?, " for column in changed)
            cat.execute(f"UPDATE tags SET {assignments}revision = revision + 1, updated_at = ? WHERE slug = ?",
                        [*changed.values(), now_ts(), slug])
            row = _tag_row(cat, slug)
            _emit(cat, [{"entity": "tag", "id": slug, "revision": row["revision"], "deleted": False}])
        tag = _tag_json(cat, row)
    _relay(project_id)
    return json_response(tag, 200, {"ETag": etag(tag["revision"])})


@bp.delete("/<project_id>/tags/<slug>")
@_catalog_errors
def delete_tag(project_id, slug):
    load_visible(g.db, project_id)
    expected = _require_if_match("tag")
    cat = _open(project_id)
    with transaction(cat):
        load_writable(g.db, project_id)
        row = _tag_row(cat, slug)
        if row["system"]:
            raise ApiError(409, "TAG_PROTECTED", "Default tags cannot be deleted.")
        _check_revision(row["revision"], expected, "tag")
        affected = [r["file_id"] for r in cat.execute(
            "SELECT file_id FROM file_tags WHERE slug = ? ORDER BY file_id", (slug,))]
        cat.execute("DELETE FROM file_tags WHERE slug = ?", (slug,))
        cat.execute("DELETE FROM tags WHERE slug = ?", (slug,))
        file_changes = [_file_change(_bump(cat, fid, {})) for fid in affected]
        _emit(cat, [{"entity": "tag", "id": slug, "revision": None, "deleted": True}, *file_changes])
    _relay(project_id)
    return Response(status=204)
