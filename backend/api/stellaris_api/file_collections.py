"""Workspace collections and user relations (docs/file-workspace-contract.md sections 7, 9, 11, 12; plan slice 3).

Routes (relative to /api/v1/projects/{project_id}):
  GET/POST            /collections
  GET/PATCH/DELETE    /collections/{collection_id}
  POST                /collections/{collection_id}/files
  DELETE              /collections/{collection_id}/files/{file_id}
  GET/POST            /relations
  DELETE              /relations/{relation_id}

Members of a collection are listed by `GET /files?collection_id=...` (files.py).

Every mutation:
  * validates its body first (422; types are checked before any set/hash operation),
  * opens the catalog and projects legacy changes (files._open: visibility 404, sync 503),
  * checks `load_writable` against the main DB (409 PROJECT_ARCHIVED); POST checks run
    inside the catalog transaction after replay lookup, while PATCH/DELETE check before it,
  * commits its catalog rows, idempotency record (POST), and outbox row in ONE catalog
    transaction, then relays the outbox to the main event stream after commit.

Accepted race (as in file_mutations.py): a project archived between the main-DB check and the
catalog commit may receive one last catalog mutation. Legacy evidence is never affected.

No-op operations (already-present members, absent members, equal PATCH values, existing
relation triples, idempotent replays) write no outbox row.
"""

import functools
import json
import logging
import sqlite3

from flask import Blueprint, Response, g, request

from . import catalog, idempotency
from . import catalog_projection as proj
from . import catalog_relations as rel
from . import files as wf
from .db import transaction
from .errors import ApiError, validation_error
from .http import decode_cursor, encode_cursor, etag, idempotency_key, json_body, json_response, new_id, now_ts, page_limit, parse_if_match
from .projects import load_visible, load_writable
from .validation import invalid_reference

log = logging.getLogger(__name__)

bp = Blueprint("file_collections", __name__, url_prefix="/api/v1/projects")

MAX_COLLECTIONS = 200
MAX_COLLECTION_FILES = 10_000
MAX_MEMBERSHIP_BATCH = 100
MAX_NAME = 120
MAX_DESCRIPTION = 2000
MAX_RELATIONS = 20_000
MAX_NOTE = 1000
MAX_ID = 100
FILTER_FIELDS = ("tags", "file_kind", "origin_type", "status", "q")
DIRECTIONS = ("out", "in", "both")
CREATED_BY = ("user", "system")
_NOT_FOUND = ("RESOURCE_NOT_FOUND", "Resource not found.")


# -- plumbing ------------------------------------------------------------------------------

@bp.teardown_request
def _close_catalog(_exc):
    cat = g.pop("catalog", None)
    if cat is not None:
        cat.close()


def _catalog_errors(view):
    """Map SQLite failures (locked, I/O, corruption) to a safe retryable 503."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except sqlite3.Error:
            log.exception("Catalog request failed (request_id=%s)", g.get("request_id"))
            raise wf._unavailable("The project's file catalog is busy or unavailable. Retry shortly.")
    return wrapper


def _relay(project_id: str) -> None:
    """After commit only: deliver pending catalog events (best effort; retried later)."""
    catalog.relay_pending(g.db, g.catalog, project_id)


def _emit(cat, changes: list) -> None:
    """Enqueue one catalog.changed payload (1..100 entries) inside the caller's catalog transaction."""
    if changes:
        catalog.enqueue_event(cat, rel.compact(changes))


def _unicode_errors(value, path: str, errors: list) -> None:
    """Strings must be encodable as UTF-8 (JSON escapes can produce unpaired surrogates)."""
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            errors.append({"path": path, "message": "Text must be valid Unicode without unpaired surrogates."})
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _unicode_errors(item, f"{path}/{i}", errors)
    elif isinstance(value, dict):
        for k, item in value.items():
            before = len(errors)
            _unicode_errors(k, path, errors)
            _unicode_errors(item, path if len(errors) > before else f"{path}/{k}", errors)


def _body() -> dict:
    body = json_body()
    errors = []
    _unicode_errors(body, "", errors)
    if errors:
        raise validation_error(errors)
    return body


def _unknown(body: dict, allowed, errors: list, path: str = "") -> None:
    errors.extend({"path": f"{path}/{k}", "message": "Unknown field."} for k in sorted(body) if k not in allowed)


def _require_if_match(what: str) -> int:
    expected = parse_if_match()
    if expected is None:
        raise ApiError(428, "PRECONDITION_REQUIRED", f"If-Match with the {what}'s current ETag is required.")
    return expected


def _check_revision(current: int, expected: int, what: str) -> None:
    if current != expected:
        raise ApiError(412, "REVISION_CONFLICT", f"The {what} changed since it was loaded. Reload and reconcile edits.",
                       details={"current_revision": current})


def _bump_file(cat, file_id: str) -> dict:
    """Explicit membership changed: new file metadata revision. Returns its CatalogChange."""
    cat.execute("UPDATE files SET revision = revision + 1, updated_at = ? WHERE id = ?", (now_ts(), file_id))
    revision = cat.execute("SELECT revision FROM files WHERE id = ?", (file_id,)).fetchone()[0]
    return {"entity": "file", "id": file_id, "revision": revision, "deleted": False}


def _missing_files(cat, file_ids) -> list:
    """Indexes of IDs that are not files of this project's catalog (at most 100 IDs)."""
    marks = ",".join("?" * len(file_ids))
    found = {r["id"] for r in cat.execute(f"SELECT id FROM files WHERE id IN ({marks})", list(file_ids))}
    return [i for i, fid in enumerate(file_ids) if fid not in found]


def _cursor_after(project_id: str, route: str, valid_filters):
    """Decode a (created_at, id) cursor bound to route and project. Returns (filters, after) or (None, None)."""
    cursor = request.args.get("cursor")
    if not cursor:
        return None, None
    state = decode_cursor(cursor)
    saved = state.get("f", {})
    if (state.get("v") != 1 or state.get("t") != route or state.get("p") != project_id
            or not isinstance(state.get("c"), str) or not isinstance(state.get("i"), str)
            or not valid_filters(saved)):
        raise ApiError(400, "INVALID_CURSOR", "cursor is invalid.")
    return saved, (state["c"], state["i"])


# -- saved filters -------------------------------------------------------------------------

def _filter(value, errors: list):
    """Validate a FileFilter body value. Returns a normalized dict, or None for null/invalid."""
    if value is None:
        return None
    if not isinstance(value, dict):
        errors.append({"path": "/filter", "message": "filter must be an object or null."})
        return None
    out = {}
    for k in sorted(value):
        if k == "collection_id":
            errors.append({"path": "/filter/collection_id", "message": "Saved filters cannot reference collections."})
        elif k not in FILTER_FIELDS:
            errors.append({"path": f"/filter/{k}", "message": "Unknown field."})
    if "tags" in value:
        tags = value["tags"]
        if not isinstance(tags, list) or len(tags) > wf.MAX_TAG_FILTERS:
            errors.append({"path": "/filter/tags", "message": f"tags must be an array of at most {wf.MAX_TAG_FILTERS} tag slugs."})
        else:
            bad = [i for i, t in enumerate(tags) if not isinstance(t, str) or not wf.TAG_SLUG.fullmatch(t)]
            errors.extend({"path": f"/filter/tags/{i}", "message": "Expected a tag slug."} for i in bad)
            if not bad and tags:
                out["tags"] = sorted(set(tags))
    for name, choices in (("file_kind", wf.FILE_KINDS), ("origin_type", proj.ORIGIN_TYPES), ("status", wf.STATUSES)):
        if name in value:
            item = value[name]
            if not isinstance(item, str) or item not in choices:
                errors.append({"path": f"/filter/{name}", "message": f"{name} must be one of: {', '.join(choices)}."})
            else:
                out[name] = item
    if "q" in value:
        q = value["q"]
        if not isinstance(q, str) or not 1 <= len(q) <= wf.MAX_Q:
            errors.append({"path": "/filter/q", "message": f"q must contain 1-{wf.MAX_Q} characters."})
        else:
            out["q"] = q
    return out


def _canonical(saved):
    return None if saved is None else json.dumps(saved, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def saved_query(saved: dict) -> dict:
    """A stored FileFilter as /files query filters. Its omitted status means `active`."""
    query = {k: saved[k] for k in ("file_kind", "origin_type", "q") if k in saved}
    if saved.get("tags"):
        query["tag"] = sorted(set(saved["tags"]))
    query["status"] = saved.get("status", "active")
    return query


def _file_count(cat, row) -> int:
    """Files that `GET /files?collection_id=...` returns with no extra query filters."""
    where, params = [], []
    if row["filter"] is None:
        where += ["f.status = 'active'", "f.id IN (SELECT file_id FROM collection_files WHERE collection_id = ?)"]
        params.append(row["id"])
    else:
        wf._apply_filters(saved_query(json.loads(row["filter"])), where, params)  # Status is explicit here.
    sql = "SELECT COUNT(*) FROM files f" + (" WHERE " + " AND ".join(where) if where else "")
    return cat.execute(sql, params).fetchone()[0]


# -- collections ---------------------------------------------------------------------------

def _collection_fields(body: dict, *, creating: bool) -> dict:
    errors, values = [], {}
    _unknown(body, ("name", "description", "filter"), errors)
    if "name" in body or creating:
        name = body.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_NAME:
            errors.append({"path": "/name", "message": f"name must be a string of 1-{MAX_NAME} characters after trimming."})
        else:
            values["name"] = name.strip()
    if "description" in body:
        description = body["description"]
        if not isinstance(description, str) or len(description) > MAX_DESCRIPTION:
            errors.append({"path": "/description", "message": f"description must be a string of at most {MAX_DESCRIPTION} characters."})
        else:
            values["description"] = description
    elif creating:
        values["description"] = ""
    if "filter" in body:
        values["filter"] = _canonical(_filter(body["filter"], errors))
    elif creating:
        values["filter"] = None
    if errors:
        raise validation_error(errors)
    return values


def _collection_row(cat, collection_id: str):
    row = cat.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if row is None:
        raise ApiError(404, *_NOT_FOUND)
    return row


def _to_collection(cat, project_id: str, row) -> dict:
    return {
        "id": row["id"], "project_id": project_id, "name": row["name"], "description": row["description"],
        "filter": json.loads(row["filter"]) if row["filter"] is not None else None,
        "file_count": _file_count(cat, row), "revision": row["revision"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _no_filters(saved) -> bool:
    return saved == {}


@bp.get("/<project_id>/collections")
@_catalog_errors
def list_collections(project_id):
    load_visible(g.db, project_id)
    limit = page_limit()
    _, after = _cursor_after(project_id, "collections", _no_filters)
    cat = wf._open(project_id)
    sql, params = "SELECT * FROM collections", []
    if after is not None:
        sql += " WHERE (created_at > ? OR (created_at = ? AND id > ?))"
        params += [after[0], after[0], after[1]]
    rows = cat.execute(sql + " ORDER BY created_at, id LIMIT ?", [*params, limit + 1]).fetchall()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor({"v": 1, "t": "collections", "p": project_id, "f": {},
                                     "c": last["created_at"], "i": last["id"]})
    return json_response({"items": [_to_collection(cat, project_id, r) for r in rows[:limit]],
                          "next_cursor": next_cursor})


@bp.post("/<project_id>/collections")
@_catalog_errors
def create_collection(project_id):
    load_visible(g.db, project_id)
    body = _body()
    key = idempotency_key()
    values = _collection_fields(body, creating=True)
    cat = wf._open(project_id)

    def build(conn):
        load_writable(g.db, project_id)
        if conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0] >= MAX_COLLECTIONS:
            raise validation_error([{"path": "", "message": f"A project may have at most {MAX_COLLECTIONS} collections."}])
        collection_id, ts = new_id("col"), now_ts()
        conn.execute("INSERT INTO collections (id, name, description, filter, revision, created_at, updated_at) "
                     "VALUES (?, ?, ?, ?, 1, ?, ?)",
                     (collection_id, values["name"], values["description"], values["filter"], ts, ts))
        _emit(conn, [{"entity": "collection", "id": collection_id, "revision": 1, "deleted": False}])
        item = _to_collection(conn, project_id, _collection_row(conn, collection_id))
        headers = {"Location": f"/api/v1/projects/{project_id}/collections/{collection_id}", "ETag": etag(1)}
        return 201, item, headers, collection_id

    response = idempotency.run_command(cat, key, body, build)
    _relay(project_id)
    return response


@bp.get("/<project_id>/collections/<collection_id>")
@_catalog_errors
def get_collection(project_id, collection_id):
    cat = wf._open(project_id)
    item = _to_collection(cat, project_id, _collection_row(cat, collection_id))
    return json_response(item, 200, {"ETag": etag(item["revision"])})


@bp.patch("/<project_id>/collections/<collection_id>")
@_catalog_errors
def patch_collection(project_id, collection_id):
    load_visible(g.db, project_id)
    body = _body()
    if not body:
        raise validation_error([{"path": "", "message": "At least one field is required."}])
    values = _collection_fields(body, creating=False)
    expected = _require_if_match("collection")
    cat = wf._open(project_id)
    load_writable(g.db, project_id)
    with transaction(cat):
        row = _collection_row(cat, collection_id)
        _check_revision(row["revision"], expected, "collection")
        changed = {k: v for k, v in values.items() if row[k] != v}
        if "filter" in changed and (row["filter"] is None) != (changed["filter"] is None):
            if cat.execute("SELECT 1 FROM collection_files WHERE collection_id = ? LIMIT 1", (collection_id,)).fetchone():
                raise ApiError(409, "COLLECTION_NOT_EMPTY",
                               "Remove the collection's explicit members before switching it to a saved filter.")
        if changed:
            assignments = "".join(f"{column} = ?, " for column in changed)  # Columns from a fixed field set.
            cat.execute(f"UPDATE collections SET {assignments}revision = revision + 1, updated_at = ? WHERE id = ?",
                        [*changed.values(), now_ts(), collection_id])
            row = _collection_row(cat, collection_id)
            _emit(cat, [{"entity": "collection", "id": collection_id, "revision": row["revision"], "deleted": False}])
        item = _to_collection(cat, project_id, row)
    _relay(project_id)
    return json_response(item, 200, {"ETag": etag(item["revision"])})


@bp.delete("/<project_id>/collections/<collection_id>")
@_catalog_errors
def delete_collection(project_id, collection_id):
    load_visible(g.db, project_id)
    expected = _require_if_match("collection")
    cat = wf._open(project_id)
    load_writable(g.db, project_id)
    with transaction(cat):
        row = _collection_row(cat, collection_id)
        _check_revision(row["revision"], expected, "collection")
        members = [r["file_id"] for r in cat.execute(
            "SELECT file_id FROM collection_files WHERE collection_id = ? ORDER BY file_id", (collection_id,))]
        cat.execute("DELETE FROM collection_files WHERE collection_id = ?", (collection_id,))
        cat.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        file_changes = [_bump_file(cat, fid) for fid in members]  # Files stay; only collection_ids changes.
        _emit(cat, [{"entity": "collection", "id": collection_id, "revision": None, "deleted": True}, *file_changes])
    _relay(project_id)
    return Response(status=204)


@bp.post("/<project_id>/collections/<collection_id>/files")
@_catalog_errors
def add_collection_files(project_id, collection_id):
    load_visible(g.db, project_id)
    body = _body()
    key = idempotency_key()
    errors = []
    _unknown(body, ("file_ids",), errors)
    file_ids = body.get("file_ids")
    if not isinstance(file_ids, list) or not 1 <= len(file_ids) <= MAX_MEMBERSHIP_BATCH:
        errors.append({"path": "/file_ids", "message": f"file_ids must be an array of 1-{MAX_MEMBERSHIP_BATCH} file IDs."})
        file_ids = []
    bad = [i for i, fid in enumerate(file_ids) if not isinstance(fid, str) or not 1 <= len(fid) <= MAX_ID]
    errors.extend({"path": f"/file_ids/{i}", "message": "Expected a file ID string."} for i in bad)
    if not bad and len(set(file_ids)) != len(file_ids):
        errors.append({"path": "/file_ids", "message": "file_ids must not contain duplicates."})
    if errors:
        raise validation_error(errors)
    cat = wf._open(project_id)

    def build(conn):
        load_writable(g.db, project_id)
        row = _collection_row(conn, collection_id)
        if row["filter"] is not None:
            raise ApiError(409, "COLLECTION_READ_ONLY", "A saved-filter collection has no explicit members.")
        missing = _missing_files(conn, file_ids)
        if missing:
            raise invalid_reference([{"path": f"/file_ids/{i}", "message": "File not found in this project."}
                                     for i in missing])
        current = {r["file_id"] for r in conn.execute(
            "SELECT file_id FROM collection_files WHERE collection_id = ?", (collection_id,))}
        added = [fid for fid in file_ids if fid not in current]
        if len(current) + len(added) > MAX_COLLECTION_FILES:
            raise validation_error([{"path": "/file_ids",
                                     "message": f"A collection may contain at most {MAX_COLLECTION_FILES} files."}])
        ts, changes = now_ts(), []
        for fid in added:
            conn.execute("INSERT INTO collection_files (collection_id, file_id, added_at) VALUES (?, ?, ?)",
                         (collection_id, fid, ts))
            changes.append(_bump_file(conn, fid))
        _emit(conn, changes)  # Collection metadata revision is unchanged.
        return 200, {"collection": _to_collection(conn, project_id, row), "added_file_ids": added}, {}, None

    response = idempotency.run_command(cat, key, body, build)
    _relay(project_id)
    return response


@bp.delete("/<project_id>/collections/<collection_id>/files/<file_id>")
@_catalog_errors
def remove_collection_file(project_id, collection_id, file_id):
    load_visible(g.db, project_id)
    cat = wf._open(project_id)
    load_writable(g.db, project_id)
    with transaction(cat):
        row = _collection_row(cat, collection_id)
        wf._file_row(cat, file_id)  # 404 for an unknown file.
        if row["filter"] is not None:
            raise ApiError(409, "COLLECTION_READ_ONLY", "A saved-filter collection has no explicit members.")
        removed = cat.execute("DELETE FROM collection_files WHERE collection_id = ? AND file_id = ?",
                              (collection_id, file_id)).rowcount
        if removed:
            _emit(cat, [_bump_file(cat, file_id)])
    _relay(project_id)
    return Response(status=204)


# -- relations -----------------------------------------------------------------------------

def _to_relation(project_id: str, row) -> dict:
    return {"id": row["id"], "project_id": project_id, "from_file_id": row["from_file_id"],
            "to_file_id": row["to_file_id"], "type": row["type"], "note": row["note"],
            "created_by": row["created_by"], "created_at": row["created_at"]}


def _valid_type_query(value) -> bool:
    return isinstance(value, str) and (value in rel.SYSTEM_TYPES or bool(wf.TAG_SLUG.fullmatch(value)))


def _valid_relation_filters(filters) -> bool:
    if not isinstance(filters, dict):
        return False
    for name, value in filters.items():
        if name == "file_id":
            ok = isinstance(value, str) and 1 <= len(value) <= MAX_ID
        elif name == "direction":
            ok = isinstance(value, str) and value in DIRECTIONS
        elif name == "type":
            ok = _valid_type_query(value)
        elif name == "created_by":
            ok = isinstance(value, str) and value in CREATED_BY
        else:
            ok = False
        if not ok:
            return False
    return "direction" not in filters or "file_id" in filters


@bp.get("/<project_id>/relations")
@_catalog_errors
def list_relations(project_id):
    load_visible(g.db, project_id)
    limit = page_limit()
    supplied = {k: request.args.get(k) for k in ("file_id", "direction", "type", "created_by")
                if request.args.get(k) is not None}
    saved, after = _cursor_after(project_id, "relations", _valid_relation_filters)
    if saved is not None:
        if any(saved.get(k) != v for k, v in supplied.items()):
            raise ApiError(400, "INVALID_QUERY", "Query filters must match the filters used to create the cursor.")
        filters = saved
    else:
        if not _valid_relation_filters(supplied):
            if "direction" in supplied and "file_id" not in supplied:
                raise ApiError(400, "INVALID_QUERY", "direction requires file_id.")
            raise ApiError(400, "INVALID_QUERY", "A relation filter has an unsupported value.")
        filters = supplied

    cat = wf._open(project_id)
    where, params = [], []
    if "file_id" in filters:
        direction = filters.get("direction", "both")
        if direction == "out":
            where.append("from_file_id = ?")
            params.append(filters["file_id"])
        elif direction == "in":
            where.append("to_file_id = ?")
            params.append(filters["file_id"])
        else:
            where.append("(from_file_id = ? OR to_file_id = ?)")
            params += [filters["file_id"], filters["file_id"]]
    for name in ("type", "created_by"):
        if name in filters:
            where.append(f"{name} = ?")
            params.append(filters[name])
    if after is not None:
        where.append("(created_at > ? OR (created_at = ? AND id > ?))")
        params += [after[0], after[0], after[1]]
    sql = "SELECT * FROM relations" + (" WHERE " + " AND ".join(where) if where else "")
    rows = cat.execute(sql + " ORDER BY created_at, id LIMIT ?", [*params, limit + 1]).fetchall()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor({"v": 1, "t": "relations", "p": project_id, "f": filters,
                                     "c": last["created_at"], "i": last["id"]})
    return json_response({"items": [_to_relation(project_id, r) for r in rows[:limit]], "next_cursor": next_cursor})


def _relation_fields(body: dict) -> dict:
    errors = []
    _unknown(body, ("from_file_id", "to_file_id", "type", "note"), errors)
    for name in ("from_file_id", "to_file_id"):
        value = body.get(name)
        if not isinstance(value, str) or not 1 <= len(value) <= MAX_ID:
            errors.append({"path": f"/{name}", "message": f"{name} is required and must be a file ID string."})
    rel_type = body.get("type", "related")
    if not isinstance(rel_type, str):
        errors.append({"path": "/type", "message": "type must be a string."})
    elif rel_type in rel.SYSTEM_TYPES:
        errors.append({"path": "/type", "message": f"{rel_type!r} is reserved for system relations."})
    elif not wf.TAG_SLUG.fullmatch(rel_type):
        errors.append({"path": "/type", "message": "type must match ^[a-z0-9][a-z0-9-]{0,47}$."})
    note = body.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE):
        errors.append({"path": "/note", "message": f"note must be null or a string of at most {MAX_NOTE} characters."})
    if not errors and body["from_file_id"] == body["to_file_id"]:
        errors.append({"path": "/to_file_id", "message": "A relation cannot connect a file to itself."})
    if errors:
        raise validation_error(errors)
    return {"from_file_id": body["from_file_id"], "to_file_id": body["to_file_id"], "type": rel_type, "note": note}


@bp.post("/<project_id>/relations")
@_catalog_errors
def create_relation(project_id):
    load_visible(g.db, project_id)
    body = _body()
    key = idempotency_key()
    values = _relation_fields(body)
    cat = wf._open(project_id)

    def build(conn):
        load_writable(g.db, project_id)
        names = ("from_file_id", "to_file_id")
        missing = _missing_files(conn, [values[n] for n in names])
        if missing:
            raise invalid_reference([{"path": f"/{names[i]}", "message": "File not found in this project."}
                                     for i in missing])
        existing = conn.execute("SELECT * FROM relations WHERE from_file_id = ? AND to_file_id = ? AND type = ?",
                                (values["from_file_id"], values["to_file_id"], values["type"])).fetchone()
        if existing is not None:  # Same triple: unchanged (including its note), no event.
            return 200, _to_relation(project_id, existing), {}, existing["id"]
        if conn.execute("SELECT COUNT(*) FROM relations WHERE created_by = 'user'").fetchone()[0] >= MAX_RELATIONS:
            raise validation_error([{"path": "", "message": f"A project may have at most {MAX_RELATIONS} user relations."}])
        relation_id = new_id("rel")
        conn.execute("INSERT INTO relations (id, from_file_id, to_file_id, type, note, created_by, created_at) "
                     "VALUES (?, ?, ?, ?, ?, 'user', ?)",
                     (relation_id, values["from_file_id"], values["to_file_id"], values["type"], values["note"], now_ts()))
        _emit(conn, [{"entity": "relation", "id": relation_id, "revision": None, "deleted": False}])
        row = conn.execute("SELECT * FROM relations WHERE id = ?", (relation_id,)).fetchone()
        return 201, _to_relation(project_id, row), {}, relation_id

    response = idempotency.run_command(cat, key, body, build)
    _relay(project_id)
    return response


@bp.delete("/<project_id>/relations/<relation_id>")
@_catalog_errors
def delete_relation(project_id, relation_id):
    load_visible(g.db, project_id)
    cat = wf._open(project_id)
    load_writable(g.db, project_id)
    with transaction(cat):
        row = cat.execute("SELECT * FROM relations WHERE id = ?", (relation_id,)).fetchone()
        if row is None:
            raise ApiError(404, *_NOT_FOUND)
        if row["created_by"] == "system":
            raise ApiError(409, "RELATION_PROTECTED", "System relations record provenance and cannot be deleted.")
        cat.execute("DELETE FROM relations WHERE id = ?", (relation_id,))
        _emit(cat, [{"entity": "relation", "id": relation_id, "revision": None, "deleted": True}])
    _relay(project_id)
    return Response(status=204)
