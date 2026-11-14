"""Shared request/response helpers: timestamps, IDs, JSON bodies, pagination."""

import base64
import binascii
import hashlib
import json
import math
import uuid
from datetime import datetime, timezone

from flask import Response, request

from .errors import ApiError

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def now_ts() -> str:
    """RFC 3339 UTC timestamp with fixed-width microseconds (sorts lexicographically)."""
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT)


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def dumps(payload) -> str:
    # allow_nan=False enforces the contract's finite-number rule on output.
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def json_response(payload, status: int = 200, headers=None) -> Response:
    response = Response(dumps(payload), status=status, mimetype="application/json")
    for name, value in (headers or {}).items():
        response.headers[name] = value
    return response


def _reject_constant(value):
    raise ValueError(f"non-finite number {value} is not allowed")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):  # e.g. 1e999 overflows to inf
        raise ValueError("non-finite number is not allowed")
    return value


def strict_loads(text: str):
    """json.loads that rejects NaN, Infinity, and overflowing numbers."""
    return json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float)


def json_body() -> dict:
    if request.mimetype != "application/json":
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Request body must be application/json.")
    raw = request.get_data(cache=True)
    try:
        data = strict_loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "MALFORMED_JSON", "Request body is not valid JSON.")
    if not isinstance(data, dict):
        raise ApiError(
            422, "VALIDATION_FAILED", "Request body must be a JSON object.",
            details={"field_errors": [{"path": "", "message": "Expected a JSON object."}]},
        )
    return data


def canonical_sha256(data) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def idempotency_key() -> str:
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        raise ApiError(428, "PRECONDITION_REQUIRED", "Idempotency-Key header is required for this request.")
    if len(key) > 255:
        raise ApiError(400, "INVALID_HEADER", "Idempotency-Key must be at most 255 characters.")
    return key


def page_limit() -> int:
    raw = request.args.get("limit")
    if raw is None:
        return 50
    try:
        limit = int(raw)
    except ValueError:
        raise ApiError(400, "INVALID_QUERY", "limit must be an integer from 1 to 100.")
    if not 1 <= limit <= 100:
        raise ApiError(400, "INVALID_QUERY", "limit must be an integer from 1 to 100.")
    return limit


def encode_cursor(state: dict) -> str:
    raw = json.dumps(state, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        state = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, binascii.Error, UnicodeEncodeError):
        raise ApiError(400, "INVALID_CURSOR", "cursor is invalid.")
    if not isinstance(state, dict):
        raise ApiError(400, "INVALID_CURSOR", "cursor is invalid.")
    return state


def project_page(conn, table: str, project_id: str, filters: dict):
    """Ascending (created_at, id) page of `table` rows for one project.

    filters maps query parameter -> (column, allowed_values_or_None). Column names come
    only from this trusted mapping. Cursors are bound to the table and project and keep
    their original filters. Returns (rows, next_cursor).
    """
    limit = page_limit()
    active = {}
    for name, (_column, allowed) in filters.items():
        value = request.args.get(name)
        if value is not None:
            if allowed is not None and value not in allowed:
                raise ApiError(400, "INVALID_QUERY", f"{name} has an unsupported value.")
            active[name] = value

    after = None
    cursor = request.args.get("cursor")
    if cursor:
        state = decode_cursor(cursor)
        saved = state.get("f")
        if (state.get("v") != 1 or state.get("t") != table or state.get("p") != project_id
                or not isinstance(state.get("c"), str) or not isinstance(state.get("i"), str)
                or not isinstance(saved, dict) or not set(saved) <= set(filters)
                or not all(isinstance(v, str) for v in saved.values())):
            raise ApiError(400, "INVALID_CURSOR", "cursor is invalid.")
        if any(saved.get(k) != v for k, v in active.items()):
            raise ApiError(400, "INVALID_QUERY", "Query filters must match the filters used to create the cursor.")
        active = saved
        after = (state["c"], state["i"])

    sql = f"SELECT * FROM {table} WHERE project_id = ?"
    params = [project_id]
    for name, value in active.items():
        sql += f" AND {filters[name][0]} = ?"
        params.append(value)
    if after is not None:
        sql += " AND (created_at > ? OR (created_at = ? AND id > ?))"
        params += [after[0], after[0], after[1]]
    sql += " ORDER BY created_at, id LIMIT ?"
    params.append(limit + 1)

    rows = conn.execute(sql, params).fetchall()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor(
            {"v": 1, "t": table, "p": project_id, "c": last["created_at"], "i": last["id"], "f": active}
        )
    return rows[:limit], next_cursor


def etag(revision: int) -> str:
    return f'"{revision}"'


def parse_if_match():
    """Return the revision named by If-Match, or None if the header is missing."""
    raw = request.headers.get("If-Match")
    if raw is None or not raw.strip():
        return None
    value = raw.strip()
    if value.startswith("W/"):
        value = value[2:]
    value = value.strip('"')
    try:
        return int(value)
    except ValueError:
        return -1  # Never matches a real revision; reported as a conflict.
