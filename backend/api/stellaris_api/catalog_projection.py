"""Deterministic projection of legacy records into workspace files (docs/file-workspace-contract.md section 5).

Everything here reads the main database only; callers hold one read transaction so a
projection pass sees one consistent legacy snapshot. Nothing is written to the main
database and no evidence is copied: artifact files reuse the artifact's own bytes/hash,
and record files are rendered from the public legacy JSON.
"""

import csv
import hashlib
import io
import json

from .runs import TERMINAL
from .runs import results as run_results

RENDER_VERSION = 1
CATALOG_EVENT = "catalog.changed"
ORIGIN_TYPES = ("artifact", "source", "claim", "experiment", "run", "run_measurements")
SYSTEM_TAGS = ("research", "hypotheses", "experiments", "results", "artifacts", "reports", "agent-logs",
               "run-logs", "provenance", "notes", "documents", "datasets", "images", "videos", "audio", "code",
               "charts")
ARTIFACT_KIND_TAGS = {
    "document": "documents", "dataset": "datasets", "image": "images", "video": "videos", "audio": "audio",
    "code": "code", "chart": "charts", "report": "reports", "environment": "provenance",
}
CSV_COLUMNS = ("id", "series", "quantity", "value", "unit", "time_s", "uncertainty_absolute",
               "uncertainty_method", "status", "calibration_mode", "data_origin", "assumptions_json",
               "evidence_json")
_LEGACY_TABLES = {"source": "sources", "claim": "claims", "experiment": "experiments", "run": "runs"}
_API_SEGMENTS = {"source": "sources", "claim": "claims", "experiment": "experiments", "run": "runs"}


# -- identities and labels --------------------------------------------------------------

def file_id(project_id: str, origin_type: str, origin_id: str) -> str:
    """Deterministic: re-projection and rebuilds always reuse the same file ID."""
    digest = hashlib.sha256(f"stellaris-file:{project_id}:{origin_type}:{origin_id}".encode()).hexdigest()
    return f"fil_{digest[:32]}"


def label(text, fallback: str = "untitled") -> str:
    """Display label: no path separators or control characters, trimmed, at most 120 characters."""
    cleaned = "".join("_" if c in "/\\" or ord(c) < 32 or ord(c) == 127 else c for c in str(text or ""))
    cleaned = cleaned.strip()[:120].strip()
    return fallback if cleaned in ("", ".", "..") else cleaned


def _id8(resource_id: str) -> str:
    return resource_id[-8:]


# -- renderers ----------------------------------------------------------------------------

def render_json(record_type: str, project_id: str, resource_id: str, revision, data) -> bytes:
    envelope = {
        "schema": "stellaris.record.v1", "record_type": record_type, "project_id": project_id,
        "id": resource_id, "revision": revision,
        "api_path": f"/api/v1/projects/{project_id}/{_API_SEGMENTS[record_type]}/{resource_id}",
        "data": data,
    }
    text = json.dumps(envelope, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _compact(value) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False, allow_nan=False)


def render_measurements(measurements) -> bytes:
    """RFC 4180 CSV (CRLF) in (created_at, id) order. Nulls stay empty; data_origin is kept per row."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for m in measurements:
        uncertainty = m.get("uncertainty") or {}
        writer.writerow([
            _cell(m["id"]), _cell(m["series"]), _cell(m["quantity"]), _cell(m["value"]), _cell(m["unit"]),
            _cell(m["time_s"]), _cell(uncertainty.get("absolute")), _cell(uncertainty.get("method")),
            _cell(m["status"]), _cell(m["calibration_mode"]), _cell(m["data_origin"]),
            _compact(m.get("assumptions", [])), _compact(m.get("evidence", [])),
        ])
    return buffer.getvalue().encode("utf-8")


def measurements_origin(measurements) -> str:
    """Most cautious label: simulated beats derived beats observed. Never drops `simulated`."""
    origins = {m["data_origin"] for m in measurements}
    if "simulated" in origins:
        return "simulated"
    if "derived" in origins:
        return "derived"
    return "observed"


# -- legacy reads (caller holds a main-DB read transaction) --------------------------------

def legacy_sequence(main, project_id: str) -> int:
    """Newest legacy event sequence. Relayed catalog events are excluded so the catalog's own
    events never trigger another projection pass."""
    row = main.execute(
        "SELECT sequence FROM events WHERE project_id = ? AND type != ? ORDER BY sequence DESC LIMIT 1",
        (project_id, CATALOG_EVENT),
    ).fetchone()
    return row[0] if row else 0


def _doc(main, table: str, project_id: str, resource_id: str):
    row = main.execute(f"SELECT doc FROM {table} WHERE id = ? AND project_id = ?",
                       (resource_id, project_id)).fetchone()
    return json.loads(row["doc"]) if row else None


def _measurements(main, project_id: str, run_id: str):
    return [json.loads(r["doc"]) for r in main.execute(
        "SELECT doc FROM measurements WHERE project_id = ? AND run_id = ? ORDER BY created_at, id",
        (project_id, run_id))]


def render_record(main, project_id: str, origin_type: str, origin_id: str):
    """Fresh (bytes, mime_type) of a record file from current legacy state, or None if absent."""
    if origin_type == "run_measurements":
        rows = _measurements(main, project_id, origin_id)
        return (render_measurements(rows), "text/csv") if rows else None
    table = _LEGACY_TABLES.get(origin_type)
    doc = _doc(main, table, project_id, origin_id) if table else None
    if doc is None:
        return None
    if origin_type == "run":
        data = {"run": doc, "results": run_results(main, project_id, origin_id)}
        return render_json("run", project_id, origin_id, None, data), "application/json"
    revision = doc["revision"] if origin_type == "experiment" else None
    return render_json(origin_type, project_id, origin_id, revision, doc), "application/json"


# -- entries ---------------------------------------------------------------------------------

def _entry(project_id, kind, origin_type, origin_id, origin_revision, name, mime_type, size, sha256,
           scientific_origin, created_at, updated_at, tags, rendered):
    return {
        "id": file_id(project_id, origin_type, origin_id), "file_kind": kind, "origin_type": origin_type,
        "origin_id": origin_id, "origin_revision": origin_revision, "name": name, "name_key": name.casefold(),
        "mime_type": mime_type, "size_bytes": size, "content_sha256": sha256,
        "scientific_origin": scientific_origin, "render_version": RENDER_VERSION if rendered else None,
        "created_at": created_at, "updated_at": updated_at, "tags": tags,
    }


def _record(project_id, origin_type, origin_id, origin_revision, name, data: bytes, mime_type,
            scientific_origin, created_at, updated_at, tags):
    return _entry(project_id, "record", origin_type, origin_id, origin_revision, name, mime_type, len(data),
                  hashlib.sha256(data).hexdigest(), scientific_origin, created_at, updated_at, tags, True)


def artifact_entry(project_id: str, artifact: dict, run_kind) -> dict:
    tags = ["artifacts"]
    if artifact["kind"] == "log":
        tags.append("agent-logs" if run_kind == "agent" else "run-logs")
    elif artifact["kind"] in ARTIFACT_KIND_TAGS:
        tags.append(ARTIFACT_KIND_TAGS[artifact["kind"]])
    return _entry(project_id, "artifact", "artifact", artifact["id"], None, artifact["filename"],
                  artifact["mime_type"], artifact["size_bytes"], artifact["sha256"], artifact["origin"],
                  artifact["created_at"], artifact["created_at"], tags, False)


def source_entry(project_id: str, source: dict) -> dict:
    data = render_json("source", project_id, source["id"], None, source)
    return _record(project_id, "source", source["id"], None, f"{label(source['title'])}.source.json", data,
                   "application/json", "reference", source["created_at"], source["created_at"], ["research"])


def claim_entry(project_id: str, claim: dict) -> dict:
    data = render_json("claim", project_id, claim["id"], None, claim)
    tag = "hypotheses" if claim["kind"] == "hypothesis" else "results"
    return _record(project_id, "claim", claim["id"], None, f"claim-{claim['kind']}-{_id8(claim['id'])}.json",
                   data, "application/json", None, claim["created_at"], claim["created_at"], [tag])


def experiment_entry(project_id: str, experiment: dict) -> dict:
    data = render_json("experiment", project_id, experiment["id"], experiment["revision"], experiment)
    return _record(project_id, "experiment", experiment["id"], experiment["revision"],
                   f"{label(experiment['title'])}.experiment.json", data, "application/json", None,
                   experiment["created_at"], experiment["updated_at"], ["experiments"])


def run_entry(main, project_id: str, run: dict) -> dict:
    data = render_json("run", project_id, run["id"], None,
                       {"run": run, "results": run_results(main, project_id, run["id"])})
    updated = run.get("finished_at") or run["created_at"]
    return _record(project_id, "run", run["id"], run["revision"],
                   f"run-{run['input']['kind']}-{_id8(run['id'])}.json", data, "application/json", None,
                   run["created_at"], updated, ["results"])


def measurements_entry(project_id: str, run: dict, measurements) -> dict:
    data = render_measurements(measurements)
    updated = run.get("finished_at") or run["created_at"]
    return _record(project_id, "run_measurements", run["id"], run["revision"],
                   f"measurements-{_id8(run['id'])}.csv", data, "text/csv", measurements_origin(measurements),
                   run["created_at"], updated, ["results"])


def collect(main, project_id: str, projected: dict) -> list:
    """Entries for legacy records that are missing from, or newer than, the catalog.

    `projected` maps (origin_type, origin_id) -> (origin_revision, render_version). Insert-only
    tables (artifacts, sources, claims) need only membership checks; experiments and terminal
    runs are compared by revision. Call inside one main-DB read transaction.
    """
    def stale(origin_type, origin_id, revision=None, rendered=True):
        current = projected.get((origin_type, origin_id))
        if current is None:
            return True
        if revision is not None and current[0] != revision:
            return True
        return rendered and current[1] != RENDER_VERSION

    entries = []
    run_kinds = {r["id"]: r["kind"] for r in main.execute("SELECT id, kind FROM runs WHERE project_id = ?",
                                                          (project_id,))}
    for row in main.execute("SELECT id FROM artifacts WHERE project_id = ? ORDER BY created_at, id",
                            (project_id,)).fetchall():
        if stale("artifact", row["id"], rendered=False):
            artifact = _doc(main, "artifacts", project_id, row["id"])
            entries.append(artifact_entry(project_id, artifact, run_kinds.get(artifact["run_id"])))
    for origin_type, table, build in (("source", "sources", source_entry), ("claim", "claims", claim_entry)):
        for row in main.execute(f"SELECT id FROM {table} WHERE project_id = ? ORDER BY created_at, id",
                                (project_id,)).fetchall():
            if stale(origin_type, row["id"]):
                entries.append(build(project_id, _doc(main, table, project_id, row["id"])))
    for row in main.execute("SELECT id, revision FROM experiments WHERE project_id = ? ORDER BY created_at, id",
                            (project_id,)).fetchall():
        if stale("experiment", row["id"], row["revision"]):
            entries.append(experiment_entry(project_id, _doc(main, "experiments", project_id, row["id"])))
    terminal = main.execute(
        "SELECT id, kind, json_extract(doc, '$.revision') AS revision FROM runs WHERE project_id = ? "
        f"AND status IN ({','.join('?' * len(TERMINAL))}) ORDER BY created_at, id", (project_id, *TERMINAL),
    ).fetchall()
    for row in terminal:
        run = None
        if stale("run", row["id"], row["revision"]):
            run = _doc(main, "runs", project_id, row["id"])
            entries.append(run_entry(main, project_id, run))
        if row["kind"] == "analysis" and stale("run_measurements", row["id"], row["revision"]):
            measurements = _measurements(main, project_id, row["id"])
            if measurements:
                run = run or _doc(main, "runs", project_id, row["id"])
                entries.append(measurements_entry(project_id, run, measurements))
    return entries
