"""Sources (immutable snapshots) and claims (Contracts.md sections 5-6).

Public writes: only manual sources (POST /sources). Agent tools and workers publish
sources and claims through publish_source() / publish_claim(), which apply the same
validation and project-scoped reference rules.
"""

import json
import re
from urllib.parse import urlsplit

from flask import Blueprint, g

from . import idempotency
from .errors import ApiError, validation_error
from .events import record_event
from .http import dumps, idempotency_key, json_body, json_response, new_id, now_ts, project_page
from .projects import load_visible, load_writable
from .refs import require_artifacts, require_one
from .validation import MAX_TEXT, Validator, invalid_reference, is_finite, is_int, is_timestamp

bp = Blueprint("research", __name__, url_prefix="/api/v1/projects")

PROVIDERS = ("arxiv", "openalex", "semantic_scholar", "web", "manual")
RETRIEVAL_STATUSES = ("metadata_only", "abstract_retrieved", "full_text_retrieved", "failed")
MANUAL_FIELDS = {"title", "authors", "url", "doi", "published_at", "abstract"}
CLAIM_KINDS = ("observation", "inference", "hypothesis")
_PUBLISHED_AT = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$")
_NOT_FOUND = ("RESOURCE_NOT_FOUND", "Resource not found.")


def _project_for_write(conn, project_id, allow_archived):
    return load_visible(conn, project_id) if allow_archived else load_writable(conn, project_id)


# -- sources --------------------------------------------------------------------

def validate_source(fields: dict, *, allowed=None) -> dict:
    """Validate Source input fields; returns normalized values. Raises 422."""
    v = Validator()
    if allowed is not None:
        v.unknown(fields, allowed)
    values = {
        "title": v.string(fields, "title", min_len=1, max_len=1000, strip=True),
        "authors": v.strings(fields, "authors", required=False, max_items=500, min_len=1, max_len=500),
        "url": v.string(fields, "url", min_len=1, max_len=2048),
        "doi": v.string(fields, "doi", required=False, nullable=True, min_len=1, max_len=255),
        "published_at": v.string(fields, "published_at", required=False, nullable=True, max_len=10),
        "abstract": v.string(fields, "abstract", required=False, nullable=True, max_len=MAX_TEXT),
    }
    url = values["url"]
    if isinstance(url, str):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc or any(c.isspace() or ord(c) < 32 for c in url):
            v.error("/url", "url must be an absolute http(s) URL.")
    if values["published_at"] is not None and not _PUBLISHED_AT.match(values["published_at"]):
        v.error("/published_at", "published_at must be YYYY, YYYY-MM, or YYYY-MM-DD.")
    v.check()
    return values


def publish_source(conn, project_id: str, *, title: str, url: str, provider: str = "manual",
                   authors=(), external_id=None, published_at=None, doi=None, abstract=None,
                   retrieval_status: str = "metadata_only", retrieved_at=None,
                   document_artifact_id=None, allow_archived: bool = False) -> dict:
    """Create an immutable Source snapshot and its source.created event.

    Call inside db.transaction(conn). Raises ApiError (404 project, 409 PROJECT_ARCHIVED,
    422 VALIDATION_FAILED / INVALID_REFERENCE). Never call with invented retrieval results.
    """
    _project_for_write(conn, project_id, allow_archived)
    values = validate_source({"title": title, "url": url, "authors": list(authors), "doi": doi,
                              "published_at": published_at, "abstract": abstract})
    v = Validator()
    v.enum({"provider": provider}, "provider", PROVIDERS)
    v.enum({"retrieval_status": retrieval_status}, "retrieval_status", RETRIEVAL_STATUSES)
    v.string({"external_id": external_id}, "external_id", nullable=True, min_len=1, max_len=500)
    if retrieved_at is not None and not is_timestamp(retrieved_at):
        v.error("/retrieved_at", "retrieved_at must be an RFC 3339 timestamp.")
    v.check()
    if document_artifact_id is not None:
        require_one(conn, "artifacts", project_id, document_artifact_id, "/document_artifact_id")

    ts = now_ts()
    source = {
        "id": new_id("src"), "project_id": project_id, "provider": provider, "external_id": external_id,
        "title": values["title"], "authors": values["authors"], "published_at": values["published_at"],
        "doi": values["doi"], "url": values["url"], "abstract": values["abstract"],
        "retrieval_status": retrieval_status, "retrieved_at": retrieved_at or ts,
        "document_artifact_id": document_artifact_id, "created_at": ts,
    }
    conn.execute("INSERT INTO sources (id, project_id, provider, created_at, doc) VALUES (?, ?, ?, ?, ?)",
                 (source["id"], project_id, provider, ts, dumps(source)))
    record_event(conn, project_id, "source.created", {"source": source})
    return source


@bp.post("/<project_id>/sources")
def create_source(project_id):
    body = json_body()
    key = idempotency_key()
    validate_source(body, allowed=MANUAL_FIELDS)

    def build(conn):
        source = publish_source(conn, project_id, provider="manual", retrieval_status="metadata_only", **body)
        return 201, source, {"Location": f"/api/v1/projects/{project_id}/sources/{source['id']}"}, source["id"]

    return idempotency.run_command(g.db, key, body, build)


@bp.get("/<project_id>/sources")
def list_sources(project_id):
    load_visible(g.db, project_id)
    rows, next_cursor = project_page(g.db, "sources", project_id, {"provider": ("provider", PROVIDERS)})
    return json_response({"items": [json.loads(r["doc"]) for r in rows], "next_cursor": next_cursor})


@bp.get("/<project_id>/sources/<source_id>")
def get_source(project_id, source_id):
    return json_response(get_doc("sources", project_id, source_id))


# -- claims -----------------------------------------------------------------------

def _evidence(v: Validator, items, path: str):
    if not isinstance(items, (list, tuple)) or len(items) > 500:
        v.error(path, "Expected an array of at most 500 evidence references.")
        return []
    items = list(items)
    for i, ref in enumerate(items):
        p = f"{path}/{i}"
        if not v.object(ref, p):
            continue
        v.unknown(ref, {"artifact_id", "frame_index", "time_s", "row_index"}, p)
        v.string(ref, "artifact_id", p, min_len=1, max_len=100)
        for key in ("frame_index", "row_index"):
            if key not in ref or not (ref[key] is None or (is_int(ref[key]) and ref[key] >= 0)):
                v.error(f"{p}/{key}", f"{key} must be a nonnegative integer or null.")
        if "time_s" not in ref or not (ref["time_s"] is None or (is_finite(ref["time_s"]) and ref["time_s"] >= 0)):
            v.error(f"{p}/time_s", "time_s must be a finite nonnegative number or null.")
    return items


def publish_claim(conn, project_id: str, *, run_id: str, kind: str, text: str, measurement_ids=(),
                  citations=(), evidence=(), assumptions=(), limitations=(),
                  allow_archived: bool = True) -> dict:
    """Create a Claim and its claim.created event. Call inside db.transaction(conn).

    Rules enforced: observation needs evidence or measurements; inference needs evidence,
    measurements, or citations plus at least one assumption; cited sources and evidence
    artifacts must belong to the project; a citation excerpt must come from retrieved
    material (none for metadata-only/failed sources, a substring of the abstract for
    abstract-only sources). run_id and measurement_ids must belong to the project
    (422 INVALID_REFERENCE otherwise).
    """
    _project_for_write(conn, project_id, allow_archived)
    data = {"run_id": run_id, "kind": kind, "text": text, "measurement_ids": list(measurement_ids),
            "assumptions": list(assumptions), "limitations": list(limitations)}
    v = Validator()
    v.string(data, "run_id", min_len=1, max_len=100)
    v.enum(data, "kind", CLAIM_KINDS)
    v.string(data, "text", min_len=1, max_len=MAX_TEXT, strip=True)
    v.strings(data, "measurement_ids", max_items=1000, unique=True)
    v.strings(data, "assumptions")
    v.strings(data, "limitations")
    evidence = _evidence(v, evidence, "/evidence")
    citations = list(citations) if isinstance(citations, (list, tuple)) else None
    if citations is None:
        v.error("/citations", "citations must be an array.")
        citations = []
    for i, cit in enumerate(citations):
        p = f"/citations/{i}"
        if v.object(cit, p):
            v.unknown(cit, {"source_id", "locator", "excerpt"}, p)
            v.string(cit, "source_id", p, min_len=1, max_len=100)
            v.string(cit, "locator", p, nullable=True, max_len=1000)
            v.string(cit, "excerpt", p, nullable=True, min_len=1, max_len=MAX_TEXT)
    if kind == "observation" and not (evidence or measurement_ids):
        v.error("/evidence", "An observation requires evidence or measurement links.")
    if kind == "inference":
        if not (evidence or measurement_ids or citations):
            v.error("/evidence", "An inference requires evidence, measurements, or citations.")
        if not assumptions:
            v.error("/assumptions", "An inference must state its assumptions.")
    v.check()

    if conn.execute("SELECT 1 FROM runs WHERE id = ? AND project_id = ?", (run_id, project_id)).fetchone() is None:
        raise invalid_reference([{"path": "/run_id", "message": "Run not found in this project."}])
    missing = [i for i, mid in enumerate(data["measurement_ids"]) if conn.execute(
        "SELECT 1 FROM measurements WHERE id = ? AND project_id = ?", (mid, project_id)).fetchone() is None]
    if missing:
        raise invalid_reference([{"path": f"/measurement_ids/{i}", "message": "Measurement not found in this project."}
                                 for i in missing])
    require_artifacts(conn, project_id, [ref["artifact_id"] for ref in evidence], "/evidence")
    errors = []
    for i, cit in enumerate(citations):
        source = require_one(conn, "sources", project_id, cit["source_id"], f"/citations/{i}/source_id")
        excerpt = cit["excerpt"]
        if excerpt is None:
            continue
        status = source["retrieval_status"]
        if status in ("metadata_only", "failed") or (
                status == "abstract_retrieved" and excerpt not in (source["abstract"] or "")):
            errors.append({"path": f"/citations/{i}/excerpt", "message": "Excerpt must come from retrieved source material."})
    if errors:
        raise validation_error(errors)

    claim = {
        "id": new_id("clm"), "project_id": project_id, "run_id": run_id, "kind": kind, "text": text.strip(),
        "measurement_ids": data["measurement_ids"],
        "citations": [{"source_id": c["source_id"], "locator": c["locator"], "excerpt": c["excerpt"]} for c in citations],
        "evidence": [{k: ref[k] for k in ("artifact_id", "frame_index", "time_s", "row_index")} for ref in evidence],
        "assumptions": data["assumptions"], "limitations": data["limitations"], "created_at": now_ts(),
    }
    conn.execute("INSERT INTO claims (id, project_id, run_id, created_at, doc) VALUES (?, ?, ?, ?, ?)",
                 (claim["id"], project_id, run_id, claim["created_at"], dumps(claim)))
    record_event(conn, project_id, "claim.created", {"claim": claim}, run_id=run_id)
    return claim


@bp.get("/<project_id>/claims")
def list_claims(project_id):
    load_visible(g.db, project_id)
    rows, next_cursor = project_page(g.db, "claims", project_id, {"run_id": ("run_id", None)})
    return json_response({"items": [json.loads(r["doc"]) for r in rows], "next_cursor": next_cursor})


@bp.get("/<project_id>/claims/<claim_id>")
def get_claim(project_id, claim_id):
    return json_response(get_doc("claims", project_id, claim_id))


def get_doc(table: str, project_id: str, resource_id: str) -> dict:
    """Public JSON of one project-owned resource from a fixed internal table name, or 404."""
    if table not in ("sources", "claims", "experiments", "artifacts", "runs"):
        raise ValueError(table)
    load_visible(g.db, project_id)
    row = g.db.execute(f"SELECT doc FROM {table} WHERE id = ? AND project_id = ?",
                       (resource_id, project_id)).fetchone()
    if row is None:
        raise ApiError(404, *_NOT_FOUND)
    return json.loads(row["doc"])
