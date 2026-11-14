"""System relations projected from recorded legacy provenance (docs/file-workspace-contract.md section 10).

Two steps, called from catalog.sync's projection pass:

  edges = collect(main, project_id)          # inside the pass's ONE main-DB read transaction
  changes = sync(cat, project_id, edges)     # inside the pass's catalog write transaction,
                                             # after projected files were upserted

Only provenance that legacy records already state is used; nothing is inferred or ranked:

  derived_from   artifact -> artifact          Artifact.parent_artifact_ids
  produced_by    artifact -> run record        Artifact.run_id (the run file exists once terminal)
  produced_by    measurements -> run record    the measurements' run
  cites          claim -> source record        Claim.citations[].source_id
  uses_evidence  claim -> artifact             Claim.evidence[].artifact_id
  uses_evidence  claim -> measurements file    Claim.measurement_ids, via each measurement's run

Edges are addressed by deterministic file IDs (catalog_projection.file_id) and get
deterministic relation IDs. An edge is inserted only when both files already exist in the
catalog; otherwise it is retried on a later pass (e.g. produced_by appears once the run is
terminal and its run file is projected). Legacy provenance is insert-only, so system edges
are never deleted or updated. The project relation cap applies to user relations only; a
projection pass never fails because of it.
"""

import hashlib
import json

from . import catalog_projection as proj

# Bump to make every existing catalog re-run relation projection once (stored in catalog meta).
PROJECTION_VERSION = 1
SYSTEM_TYPES = ("derived_from", "produced_by", "cites", "uses_evidence")
_CHUNK = 500


def relation_id(project_id: str, from_file_id: str, to_file_id: str, rel_type: str) -> str:
    digest = hashlib.sha256(
        f"stellaris-relation:{project_id}:{from_file_id}:{to_file_id}:{rel_type}".encode()).hexdigest()
    return f"rel_{digest[:32]}"


def _ids(raw) -> list:
    """String IDs from a json_extract'ed JSON array (anything else is ignored)."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except ValueError:
        return []
    return [v for v in value if isinstance(v, str) and v] if isinstance(value, list) else []


def _field_ids(raw, field: str) -> list:
    """`field` of each object in a json_extract'ed JSON array of objects."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(value, list):
        return []
    return [item[field] for item in value if isinstance(item, dict) and isinstance(item.get(field), str)]


def collect(main, project_id: str) -> list:
    """Desired system edges as sorted (from_file_id, to_file_id, type) triples.

    Reads the main DB only. Call inside the projection pass's read transaction so the edges
    match the same legacy snapshot as the projected files.
    """
    fid = lambda origin_type, origin_id: proj.file_id(project_id, origin_type, origin_id)  # noqa: E731
    edges = set()
    for row in main.execute(
            "SELECT id, run_id, json_extract(doc, '$.parent_artifact_ids') AS parents FROM artifacts "
            "WHERE project_id = ?", (project_id,)):
        artifact = fid("artifact", row["id"])
        for parent in _ids(row["parents"]):
            if parent != row["id"]:
                edges.add((artifact, fid("artifact", parent), "derived_from"))
        if row["run_id"]:
            edges.add((artifact, fid("run", row["run_id"]), "produced_by"))
    for row in main.execute("SELECT DISTINCT run_id FROM measurements WHERE project_id = ?", (project_id,)):
        edges.add((fid("run_measurements", row["run_id"]), fid("run", row["run_id"]), "produced_by"))

    claim_measurements = []
    for row in main.execute(
            "SELECT id, json_extract(doc, '$.citations') AS citations, json_extract(doc, '$.evidence') AS evidence, "
            "json_extract(doc, '$.measurement_ids') AS measurement_ids FROM claims WHERE project_id = ?",
            (project_id,)):
        claim = fid("claim", row["id"])
        for source_id in _field_ids(row["citations"], "source_id"):
            edges.add((claim, fid("source", source_id), "cites"))
        for artifact_id in _field_ids(row["evidence"], "artifact_id"):
            edges.add((claim, fid("artifact", artifact_id), "uses_evidence"))
        claim_measurements.extend((claim, mid) for mid in _ids(row["measurement_ids"]))

    wanted = sorted({mid for _, mid in claim_measurements})
    run_of = {}
    for start in range(0, len(wanted), _CHUNK):
        chunk = wanted[start:start + _CHUNK]
        marks = ",".join("?" * len(chunk))
        for row in main.execute(f"SELECT id, run_id FROM measurements WHERE project_id = ? AND id IN ({marks})",
                                (project_id, *chunk)):
            run_of[row["id"]] = row["run_id"]
    for claim, mid in claim_measurements:
        if mid in run_of:
            edges.add((claim, fid("run_measurements", run_of[mid]), "uses_evidence"))
    return sorted(edges)


def sync(cat, project_id: str, edges) -> list:
    """Insert missing system edges whose two files exist. Call inside a catalog transaction.

    Returns one CatalogChange per inserted relation. created_at is the later of the two
    files' (legacy) created_at, so a rebuilt catalog reproduces identical relations.
    """
    if not edges:
        return []
    existing = {r["id"] for r in cat.execute("SELECT id FROM relations WHERE created_by = 'system'")}
    pending = []
    for from_id, to_id, rel_type in edges:
        rel_id = relation_id(project_id, from_id, to_id, rel_type)
        if rel_id not in existing and from_id != to_id and rel_type in SYSTEM_TYPES:
            pending.append((rel_id, from_id, to_id, rel_type))
    if not pending:
        return []
    created = {r["id"]: r["created_at"] for r in cat.execute("SELECT id, created_at FROM files WHERE file_kind != 'note'")}
    changes = []
    for rel_id, from_id, to_id, rel_type in pending:
        if from_id not in created or to_id not in created:
            continue  # Retried on a later pass once both files are projected.
        cursor = cat.execute(
            "INSERT OR IGNORE INTO relations (id, from_file_id, to_file_id, type, note, created_by, created_at) "
            "VALUES (?, ?, ?, ?, NULL, 'system', ?)",
            (rel_id, from_id, to_id, rel_type, max(created[from_id], created[to_id])))
        if cursor.rowcount:
            changes.append({"entity": "relation", "id": rel_id, "revision": None, "deleted": False})
    return changes


def compact(changes: list, limit: int = 100) -> list:
    """At most `limit` CatalogChange entries: past the limit, one bulk entry per entity type."""
    if len(changes) <= limit:
        return changes
    entities = sorted({c["entity"] for c in changes})
    return [{"entity": e, "id": None, "revision": None, "deleted": False, "bulk": True} for e in entities]
