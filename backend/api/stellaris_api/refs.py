"""Project-scoped reference checks. A reference outside the project, or to an artifact that is
not ready (only ready artifacts have rows), is reported as 422 INVALID_REFERENCE without
revealing whether it exists elsewhere."""

import json

from .validation import invalid_reference

_TABLES = {"artifacts": "Artifact", "experiments": "Experiment", "sources": "Source"}


def require_one(conn, table: str, project_id: str, resource_id, path: str) -> dict:
    label = _TABLES[table]  # KeyError for anything but the fixed table names.
    row = None
    if isinstance(resource_id, str):
        row = conn.execute(f"SELECT doc FROM {table} WHERE id = ? AND project_id = ?",
                           (resource_id, project_id)).fetchone()
    if row is None:
        raise invalid_reference([{"path": path, "message": f"{label} not found in this project."}])
    return json.loads(row["doc"])


def require_artifacts(conn, project_id: str, ids, path: str) -> dict:
    """Return {artifact_id: Artifact} for ready artifacts of this project, or raise 422."""
    found, errors = {}, []
    for index, artifact_id in enumerate(ids):
        row = conn.execute("SELECT doc FROM artifacts WHERE id = ? AND project_id = ?",
                           (artifact_id, project_id)).fetchone()
        if row is None:
            errors.append({"path": f"{path}/{index}", "message": "Artifact not found in this project or not ready."})
        else:
            found[artifact_id] = json.loads(row["doc"])
    if errors:
        raise invalid_reference(errors)
    return found
