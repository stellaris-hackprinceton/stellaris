"""Workspace file read routes (docs/file-workspace-contract.md sections 4-8; plan slice 1).

Implemented here: GET /catalog, /files, /files/{id}, /files/{id}/content, /tags, /tags/{slug}.
GET /files also supports the section 16 curated-view selection (repeatable `artifact_kind`) and
exact paired `origin_type` + `origin_id` lookup.
Notes, revisions, tagging, and tag mutations (slice 2) live in file_mutations.py and register
on this blueprint. Collection and relation routes use the file_collections blueprint.

Every route first checks project visibility in the main DB (so catalogs are only created for
visible projects), opens the project's catalog, and projects legacy changes. The catalog
connection is closed at the end of each request.
"""

import hashlib
import json
import logging
import re

from flask import Blueprint, Response, current_app, g, request

from . import catalog
from . import catalog_projection as proj
from .artifacts import _content_disposition, artifact_content
from .db import transaction
from .errors import ApiError
from .http import decode_cursor, encode_cursor, etag, json_response, page_limit
from .media import ARTIFACT_KINDS, INLINE_MIME_TYPES, content_type_header
from .projects import load_visible

log = logging.getLogger(__name__)

bp = Blueprint("files", __name__, url_prefix="/api/v1/projects")

FILE_KINDS = ("artifact", "record", "note")
STATUSES = ("active", "trashed", "all")
SORT_COLUMNS = {"created_at": "created_at", "updated_at": "updated_at", "name": "name_key"}
ORDERS = ("asc", "desc")
TAG_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
MAX_TAG_FILTERS = 10
MAX_ARTIFACT_KINDS = 10  # Counted before deduplication (contract section 16.3).
MAX_Q = 100
MAX_ID = 100
CSP = "default-src 'none'; media-src 'self'; img-src 'self'; sandbox"
_NOT_FOUND = ("RESOURCE_NOT_FOUND", "Resource not found.")


# -- request plumbing --------------------------------------------------------------------

@bp.teardown_request
def _close_catalog(_exc):
    cat = g.pop("catalog", None)
    if cat is not None:
        cat.close()


def _unavailable(message: str) -> ApiError:
    return ApiError(503, "SERVICE_UNAVAILABLE", message, retryable=True, headers={"Retry-After": "5"})


def _open(project_id: str, *, tolerate_sync_error: bool = False):
    """Visible project -> open catalog -> project legacy changes. Returns the catalog connection."""
    load_visible(g.db, project_id)
    config = current_app.config["STELLARIS"]
    try:
        cat = catalog.open_catalog(config, project_id)
    except catalog.CatalogUnavailable as exc:
        log.error("Catalog unavailable: %s", exc)
        raise _unavailable("The project's file catalog is unavailable.")
    g.catalog = cat
    try:
        catalog.sync(g.db, cat, project_id)
    except catalog.SyncFailed:
        if not tolerate_sync_error:
            raise _unavailable("The project's file catalog could not be brought up to date. Retry shortly.")
    return cat


def _bad_query(message: str) -> ApiError:
    return ApiError(400, "INVALID_QUERY", message)


def _bad_cursor() -> ApiError:
    return ApiError(400, "INVALID_CURSOR", "cursor is invalid.")


# -- serialization -----------------------------------------------------------------------

def _to_files(cat, project_id: str, rows) -> list:
    ids = [r["id"] for r in rows]
    tags, collections = {}, {}
    if ids:
        marks = ",".join("?" * len(ids))
        for r in cat.execute(f"SELECT file_id, slug, assigned_by FROM file_tags WHERE file_id IN ({marks}) "
                             "ORDER BY slug", ids):
            tags.setdefault(r["file_id"], []).append({"slug": r["slug"], "assigned_by": r["assigned_by"]})
        for r in cat.execute(f"SELECT file_id, collection_id FROM collection_files WHERE file_id IN ({marks}) "
                             "ORDER BY collection_id", ids):
            collections.setdefault(r["file_id"], []).append(r["collection_id"])
    out = []
    for r in rows:
        note = r["file_kind"] == "note"
        origin = None if note else {
            "type": r["origin_type"], "id": r["origin_id"],
            "revision": r["origin_revision"] if r["origin_type"] == "experiment" else None,
        }
        out.append({
            "id": r["id"], "project_id": project_id, "name": r["name"], "file_kind": r["file_kind"],
            "origin": origin, "scientific_origin": r["scientific_origin"], "mime_type": r["mime_type"],
            "size_bytes": r["size_bytes"], "content_sha256": r["content_sha256"],
            "editable": {"name": note, "content": note, "tags": True}, "status": r["status"],
            "tags": tags.get(r["id"], []), "collection_ids": collections.get(r["id"], []),
            "content_revision": r["content_revision"] if note else None, "revision": r["revision"],
            "created_at": r["created_at"], "updated_at": r["updated_at"],
            # Authoritative underlying artifact kind (section 16.1); null for records and notes.
            "artifact_kind": r["artifact_kind"] if r["file_kind"] == "artifact" else None,
        })
    return out


def _file_row(cat, file_id: str):
    row = cat.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if row is None:
        raise ApiError(404, *_NOT_FOUND)
    return row


def _tag_counts(cat, slugs) -> dict:
    if not slugs:
        return {}
    marks = ",".join("?" * len(slugs))
    return {r["slug"]: r["n"] for r in cat.execute(
        f"SELECT t.slug, COUNT(*) AS n FROM file_tags t JOIN files f ON f.id = t.file_id "
        f"WHERE t.slug IN ({marks}) AND f.status = 'active' GROUP BY t.slug", list(slugs))}


def _to_tag(row, count: int) -> dict:
    return {"slug": row["slug"], "label": row["label"], "color": row["color"], "system": bool(row["system"]),
            "file_count": count, "revision": row["revision"], "created_at": row["created_at"],
            "updated_at": row["updated_at"]}


# -- file filters and cursors ------------------------------------------------------------

def _valid_filters(filters) -> bool:
    """Validate a normalized filter dict (from a query or a saved cursor)."""
    if not isinstance(filters, dict):
        return False
    for name, value in filters.items():
        if name == "tag":
            if (not isinstance(value, list) or not 1 <= len(value) <= MAX_TAG_FILTERS 
                    or not all(isinstance(t, str) and TAG_SLUG.fullmatch(t) for t in value)
                    or value != sorted(set(value))):
                return False
        elif name == "artifact_kind":
            # Canonical: deduplicated and lexically sorted, so reordered values bind equal cursors.
            if (not isinstance(value, list) or not 1 <= len(value) <= MAX_ARTIFACT_KINDS
                    or not all(isinstance(k, str) and k in ARTIFACT_KINDS for k in value)
                    or value != sorted(set(value))):
                return False
        elif name == "origin_id":
            if not isinstance(value, str) or not 1 <= len(value) <= MAX_ID:
                return False
        elif name in ("file_kind", "origin_type", "status"):
            allowed = {"file_kind": FILE_KINDS, "origin_type": proj.ORIGIN_TYPES, "status": STATUSES}[name]
            if value not in allowed:
                return False
        elif name == "q":
            if not isinstance(value, str) or not 1 <= len(value) <= MAX_Q:
                return False
        elif name == "collection_id":
            if not isinstance(value, str) or not 1 <= len(value) <= MAX_ID:
                return False
        else:
            return False
    return "origin_id" not in filters or "origin_type" in filters  # Exact origin lookup is paired.


def _query_filters():
    """Filters, sort, and order explicitly supplied on this request (validated; 400 otherwise)."""
    args, filters = request.args, {}
    tags = args.getlist("tag")
    if tags:
        if len(tags) > MAX_TAG_FILTERS:
            raise _bad_query(f"At most {MAX_TAG_FILTERS} tag filters are allowed.")
        filters["tag"] = sorted(set(tags))
    kinds = args.getlist("artifact_kind")
    if kinds:
        if len(kinds) > MAX_ARTIFACT_KINDS:
            raise _bad_query(f"At most {MAX_ARTIFACT_KINDS} artifact_kind filters are allowed.")
        if not all(k in ARTIFACT_KINDS for k in kinds):
            raise _bad_query(f"artifact_kind must be one of: {', '.join(ARTIFACT_KINDS)}.")
        filters["artifact_kind"] = sorted(set(kinds))
    for name in ("file_kind", "origin_type", "origin_id", "status", "q", "collection_id"):
        if args.get(name) is not None:
            filters[name] = args.get(name)
    if "origin_id" in filters and "origin_type" not in filters:
        raise _bad_query("origin_id requires origin_type.")
    if not _valid_filters(filters):
        raise _bad_query("A file filter has an unsupported value.")
    sort, order = args.get("sort"), args.get("order")
    if sort is not None and sort not in SORT_COLUMNS:
        raise _bad_query("sort must be created_at, updated_at, or name.")
    if order is not None and order not in ORDERS:
        raise _bad_query("order must be asc or desc.")
    return filters, sort, order


def _apply_filters(filters: dict, where: list, params: list, *, default_status: bool = True) -> None:
    status = filters.get("status", "active" if default_status else "all")
    if status != "all":
        where.append("f.status = ?")
        params.append(status)
    for name in ("file_kind", "origin_type", "origin_id"):
        if name in filters:
            where.append(f"f.{name} = ?")
            params.append(filters[name])
    kinds = filters.get("artifact_kind") or []
    if kinds:  # OR within the set; only artifact files carry a kind, so notes/records never match.
        where.append(f"(f.file_kind = 'artifact' AND f.artifact_kind IN ({','.join('?' * len(kinds))}))")
        params.extend(kinds)
    if "q" in filters:
        escaped = filters["q"].casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("f.name_key LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
    tags = filters.get("tag") or []
    if tags:
        marks = ",".join("?" * len(tags))
        where.append(f"(SELECT COUNT(*) FROM file_tags t WHERE t.file_id = f.id AND t.slug IN ({marks})) = ?")
        params.extend([*tags, len(tags)])


def saved_filter_query(saved: dict) -> dict:
    """A stored FileFilter as query filters: `tags` -> `tag`, `artifact_kinds` -> `artifact_kind`.
    Omitted status stays omitted (the caller's default applies)."""
    query = {k: v for k, v in saved.items() if k not in ("tags", "artifact_kinds")}
    if saved.get("tags"):
        query["tag"] = sorted(set(saved["tags"]))
    if saved.get("artifact_kinds"):
        query["artifact_kind"] = sorted(set(saved["artifact_kinds"]))
    return query


def _collection_filters(cat, collection_id: str, where: list, params: list) -> bool:
    """Add membership constraints; return whether a saved filter supplies the default status."""
    row = cat.execute("SELECT filter FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if row is None:
        raise ApiError(404, *_NOT_FOUND)
    if row["filter"] is None:
        where.append("f.id IN (SELECT file_id FROM collection_files WHERE collection_id = ?)")
        params.append(collection_id)
        return False
    _apply_filters(saved_filter_query(json.loads(row["filter"])), where, params)
    return True


# -- routes ------------------------------------------------------------------------------

@bp.get("/<project_id>/catalog")
def get_catalog(project_id):
    cat = _open(project_id, tolerate_sync_error=True)
    return json_response(catalog.status(cat, current_app.config["STELLARIS"]))


@bp.get("/<project_id>/files")
def list_files(project_id):
    load_visible(g.db, project_id)  # 404 before query validation, like the legacy list routes.
    limit = page_limit()
    supplied, sort, order = _query_filters()
    cursor = request.args.get("cursor")
    filters, after = supplied, None
    if cursor:
        state = decode_cursor(cursor)
        if (state.get("v") != 1 or state.get("t") != "files" or state.get("p") != project_id
                or not isinstance(state.get("s"), str) or state["s"] not in SORT_COLUMNS
                or state.get("o") not in ORDERS
                or not isinstance(state.get("k"), str) or not isinstance(state.get("i"), str)
                or not _valid_filters(state.get("f"))):
            raise _bad_cursor()
        saved = state["f"]
        if (any(saved.get(name) != value for name, value in supplied.items())
                or (sort is not None and sort != state["s"]) or (order is not None and order != state["o"])):
            raise _bad_query("Query filters must match the filters used to create the cursor.")
        filters, sort, order, after = saved, state["s"], state["o"], (state["k"], state["i"])
    sort, order = sort or "created_at", order or "asc"

    cat = _open(project_id)
    where, params = [], []
    saved_collection = False
    if "collection_id" in filters:
        saved_collection = _collection_filters(cat, filters["collection_id"], where, params)
    _apply_filters(filters, where, params, default_status=not saved_collection)
    column, direction = SORT_COLUMNS[sort], order.upper()
    if after is not None:
        op = ">" if order == "asc" else "<"
        where.append(f"(f.{column} {op} ? OR (f.{column} = ? AND f.id {op} ?))")
        params.extend([after[0], after[0], after[1]])
    sql = "SELECT f.* FROM files f"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY f.{column} {direction}, f.id {direction} LIMIT ?"
    rows = cat.execute(sql, [*params, limit + 1]).fetchall()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor({"v": 1, "t": "files", "p": project_id, "s": sort, "o": order,
                                     "f": filters, "k": last[column], "i": last["id"]})
    return json_response({"items": _to_files(cat, project_id, rows[:limit]), "next_cursor": next_cursor})


@bp.get("/<project_id>/files/<file_id>")
def get_file(project_id, file_id):
    cat = _open(project_id)
    item = _to_files(cat, project_id, [_file_row(cat, file_id)])[0]
    return json_response(item, 200, {"ETag": etag(item["revision"])})


def _bytes_response(data: bytes, mime_type: str, name: str, disposition: str) -> Response:
    response = Response(data, status=200, content_type=content_type_header(mime_type))
    response.headers["Content-Length"] = str(len(data))
    response.headers["ETag"] = f'"{hashlib.sha256(data).hexdigest()}"'
    response.headers["Accept-Ranges"] = "none"
    response.headers["Content-Disposition"] = _content_disposition(disposition, name)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = CSP
    return response


@bp.get("/<project_id>/files/<file_id>/content")
def file_content(project_id, file_id):
    cat = _open(project_id)
    row = _file_row(cat, file_id)
    raw_revision = request.args.get("revision")
    if raw_revision is not None and row["file_kind"] != "note":
        raise _bad_query("revision applies only to notes.")
    if row["file_kind"] == "artifact":
        # Identical behavior to the artifact content route: Range, ETag, CSP, integrity checks.
        return artifact_content(project_id, row["origin_id"])
    disposition = request.args.get("disposition", "attachment")
    if disposition not in ("attachment", "inline"):
        raise _bad_query("disposition must be 'attachment' or 'inline'.")
    if disposition == "inline" and row["mime_type"] not in INLINE_MIME_TYPES:
        raise _bad_query("This media type can only be downloaded as an attachment.")
    if row["file_kind"] == "note":
        return _note_content(cat, row, raw_revision, disposition)
    # Rendered from the newest committed legacy state. If a concurrent legacy change landed
    # after this request's projection pass, the bytes (and ETag) may be newer than
    # content_sha256; metadata catches up on the next request.
    with transaction(g.db, immediate=False):
        rendered = proj.render_record(g.db, project_id, row["origin_type"], row["origin_id"])
    if rendered is None:
        log.error("Legacy record for file %s is missing", row["id"])
        raise ApiError(404, *_NOT_FOUND)
    data, mime_type = rendered
    return _bytes_response(data, mime_type, row["name"], disposition)


def _note_content(cat, row, raw_revision, disposition: str) -> Response:
    # The current content downloads under the file's current name; a historical revision
    # downloads under the name it had when that content revision was created.
    revision, name = row["content_revision"], row["name"]
    if raw_revision is not None:
        name = None
        try:
            revision = int(raw_revision)
        except ValueError:
            raise _bad_query("revision must be a positive integer.")
        if revision < 1:
            raise _bad_query("revision must be a positive integer.")
    note = cat.execute("SELECT * FROM note_revisions WHERE file_id = ? AND content_revision = ?",
                       (row["id"], revision)).fetchone()
    if note is None:
        raise ApiError(404, *_NOT_FOUND)
    return _bytes_response(note["content"].encode("utf-8"), note["mime_type"], name or note["name"], disposition)


@bp.get("/<project_id>/tags")
def list_tags(project_id):
    load_visible(g.db, project_id)
    limit = page_limit()
    system = request.args.get("system")
    if system is not None and system not in ("true", "false"):
        raise _bad_query("system must be true or false.")
    after = None
    cursor = request.args.get("cursor")
    if cursor:
        state = decode_cursor(cursor)
        saved = state.get("f")
        if (state.get("v") != 1 or state.get("t") != "tags" or state.get("p") != project_id
                or not isinstance(saved, dict) or set(saved) - {"system"}
                or saved.get("system", "true") not in ("true", "false")
                or not isinstance(state.get("k"), str) or not TAG_SLUG.fullmatch(state["k"])):
            raise _bad_cursor()
        if system is not None and saved.get("system") != system:
            raise _bad_query("Query filters must match the filters used to create the cursor.")
        system, after = saved.get("system"), state["k"]

    cat = _open(project_id)
    where, params = [], []
    if system is not None:
        where.append("system = ?")
        params.append(1 if system == "true" else 0)
    if after is not None:
        where.append("slug > ?")
        params.append(after)
    sql = "SELECT * FROM tags" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY slug LIMIT ?"
    rows = cat.execute(sql, [*params, limit + 1]).fetchall()
    page = rows[:limit]
    counts = _tag_counts(cat, [r["slug"] for r in page])
    next_cursor = None
    if len(rows) > limit:
        saved = {"system": system} if system is not None else {}
        next_cursor = encode_cursor({"v": 1, "t": "tags", "p": project_id, "f": saved, "k": page[-1]["slug"]})
    return json_response({"items": [_to_tag(r, counts.get(r["slug"], 0)) for r in page], "next_cursor": next_cursor})


@bp.get("/<project_id>/tags/<slug>")
def get_tag(project_id, slug):
    cat = _open(project_id)
    row = cat.execute("SELECT * FROM tags WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise ApiError(404, *_NOT_FOUND)
    tag = _to_tag(row, _tag_counts(cat, [slug]).get(slug, 0))
    return json_response(tag, 200, {"ETag": etag(tag["revision"])})


# Slice 2 routes register on `bp`; imported last because they reuse the helpers above.
from . import file_mutations  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import
