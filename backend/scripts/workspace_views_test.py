#!/usr/bin/env python3
"""Focused checks for the curated-views catalog extension (docs/file-workspace-contract.md section 16).

Run from backend/ (stdlib only) after rebuilding and `docker compose up -d --wait`:

    python3 scripts/workspace_views_test.py
    python3 scripts/workspace_views_test.py --skip-docker      # API checks only

Covers, against the real API: the `workspace_views` capability and schema 2; repeated
`artifact_kind` OR selection (reordered/duplicate values, contradictions, invalid values,
tag/collection intersection, pagination beyond one page, cursor binding); exact paired
`origin_type` + `origin_id` lookup and project scoping; saved `artifact_kinds` validation,
canonicalization, and dynamic counts; collection `presentation` POST/PATCH/null/omission/no-op,
ETag conflict, events, idempotent replay, archive rejection, and survival across projection.

With Docker (default) it also:
  * downgrades one test project's catalog file to the v1 shape inside the api container and
    verifies the real API migrates it and backfills artifact kinds without new legacy events,
    preserving every file, note revision, tag, collection, and relation exactly;
  * runs FIXTURE checks inside the api container (`--fixtures` mode, temporary directory):
    new-catalog creation, a populated v1 catalog migration, a simulated migration failure
    that must roll back completely, idempotent reopen, and refusal of newer schema versions.

All fixture data is SYNTHETIC (origin "simulated", SIMULATED names). No model or provider is
called. Creates new projects and containers, which are retained. Does not read any .env file.
"""

import argparse
import base64
import hashlib
import http.client
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

_SCRIPT = globals().get("__file__") or ""
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(_SCRIPT))) if _SCRIPT.endswith(".py") else os.getcwd()
BASE = os.environ.get("STELLARIS_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
CATALOG_DIR = os.environ.get("STELLARIS_TEST_CATALOG_DIR", "/data/catalogs")
_PARSED = urllib.parse.urlsplit(BASE)
PASSED = []
KINDS = ("document", "dataset", "image", "video", "audio", "code", "chart", "report", "log", "environment")


# -- helpers --------------------------------------------------------------------------------

def check(condition, message):
    if not condition:
        raise AssertionError(message)
    PASSED.append(message)
    print(f"  ok  {message}")


def key():
    return f"wv-{uuid.uuid4().hex}"


def raw(method, path, data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=dict(headers or {}))
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read()


def api(method, path, body=None, headers=None):
    hdrs = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    status, resp_headers, payload = raw(method, path, data, hdrs)
    try:
        parsed = json.loads(payload) if payload else None
    except ValueError:
        parsed = payload
    return status, resp_headers, parsed


def post(path, body, idem=None):
    return api("POST", path, body, {"Idempotency-Key": idem or key()})


def code(body):
    return (body or {}).get("error", {}).get("code") if isinstance(body, dict) else None


def paths(body):
    return [e["path"] for e in ((body or {}).get("error", {}).get("details") or {}).get("field_errors", [])]


def all_pages(path, limit=100):
    items, cursor = [], None
    sep = "&" if "?" in path else "?"
    while True:
        url = f"{path}{sep}limit={limit}" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
        status, _, page = api("GET", url)
        assert status == 200, (url, page)
        items += page["items"]
        cursor = page["next_cursor"]
        if not cursor:
            return items


def ids(items):
    return {i["id"] for i in items}


def files_of(pid, query):
    return ids(all_pages(f"/projects/{pid}/files?{query}"))


def forge_cursor(state):
    return base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode().rstrip("=")


def project(name):
    status, _, body = post("/projects", {"name": name})
    assert status == 201, body
    return body["id"]


def upload(pid, data, filename, mime, kind):
    status, _, up = post(f"/projects/{pid}/uploads", {"filename": filename, "mime_type": mime, "size_bytes": len(data),
                                                       "sha256": hashlib.sha256(data).hexdigest(), "kind": kind,
                                                       "origin": "simulated"})
    assert status == 201, up
    status, _, body = raw("PUT", f"/projects/{pid}/uploads/{up['id']}/content", data, {"Content-Type": mime})
    assert status == 204, body
    status, _, art = post(f"/projects/{pid}/uploads/{up['id']}/complete", {})
    assert status == 200, art
    return art


def source(pid, title):
    status, _, body = post(f"/projects/{pid}/sources", {"title": title, "url": "https://example.org/simulated-reference"})
    assert status == 201, body
    return body


def file_by_origin(pid, origin_type, origin_id):
    items = all_pages(f"/projects/{pid}/files?status=all&origin_type={origin_type}&origin_id={origin_id}")
    assert len(items) == 1, items
    return items[0]


def event_cursor(pid):
    return api("GET", f"/projects/{pid}/workspace")[2]["event_cursor"]


def catalog_changes(pid, after, timeout=8):
    """All catalog.changed CatalogChange entries persisted after `after` (reads until idle/timeout)."""
    conn = http.client.HTTPConnection(_PARSED.hostname, _PARSED.port or 80, timeout=2)
    changes, deadline = [], time.monotonic() + timeout
    try:
        conn.request("GET", f"{_PARSED.path}/projects/{pid}/events?after={after}", headers={"Accept": "text/event-stream"})
        resp = conn.getresponse()
        current = {}
        while time.monotonic() < deadline:
            line = resp.readline()
            if not line:
                break
            text = line.decode().rstrip("\r\n")
            if text == "":
                if current.get("event") == "catalog.changed":
                    changes += json.loads(current["data"])["payload"]["changes"]
                current = {}
            elif not text.startswith(":"):
                name, _, value = text.partition(":")
                current[name] = value[1:] if value.startswith(" ") else value
    except (OSError, http.client.HTTPException):
        pass
    finally:
        conn.close()
    return changes


def set_project_status(pid, status):
    _, h, _ = api("GET", f"/projects/{pid}")
    s, _, body = api("PATCH", f"/projects/{pid}", {"status": status}, {"If-Match": h["ETag"]})
    assert s == 200, body


def in_container(*args):
    """Run this script inside the api container (stdin), where stellaris_api is importable."""
    with open(_SCRIPT, "rb") as handle:
        script = handle.read()
    result = subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "-", *args], input=script,
                            capture_output=True, cwd=BACKEND_DIR)
    sys.stdout.write(result.stdout.decode(errors="replace"))
    if result.returncode != 0:
        raise AssertionError(f"in-container {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()[-2000:]}")


# -- 1-4. capability, artifact-kind selection, origin lookup --------------------------------

def capability_and_fixtures(run):
    print("1. Capability and fixtures (all data SIMULATED)")
    status, _, caps = api("GET", "/capabilities")
    check(status == 200 and caps["features"].get("workspace_views") is True
          and caps["features"].get("workspace_files") is True, "capabilities advertise workspace_views and workspace_files")
    A, B = project(f"WV A {run} (SIMULATED)"), project(f"WV B {run} (SIMULATED)")
    arts = []
    for i in range(3):
        arts.append(upload(A, f"t_s,height_px\n0.0,{100 + i}\n".encode(), f"SIMULATED-heights-{i}.csv", "text/csv", "dataset"))
    for i in range(2):
        arts.append(upload(A, f"print({i})\n".encode(), f"SIMULATED_{i}.py", "text/x-python", "code"))
    arts.append(upload(A, b"# SIMULATED notes document\n", "SIMULATED-doc.md", "text/markdown", "document"))
    src = source(A, "Views reference (SIMULATED)")
    b_art = upload(B, b"t_s,height_px\n0.0,1\n", "SIMULATED-B.csv", "text/csv", "dataset")
    status, _, note = post(f"/projects/{A}/files", {"name": "report-like note.md", "content": "SIMULATED note\n",
                                                    "tags": ["reports", "documents", "datasets"]})
    check(status == 201, "note tagged reports/documents/datasets created")
    status, _, cat = api("GET", f"/projects/{A}/catalog")
    check(status == 200 and cat["schema_version"] == 2 and cat["last_sync_error"] is None, "catalog reports schema version 2")
    return A, B, arts, src, b_art, note


def artifact_kinds(A, B, arts, note, b_art):
    print("2. Artifact-kind selection")
    F = f"/projects/{A}/files"
    every = all_pages(f"{F}?status=all")
    by_art = {a["id"]: a for a in arts}
    check(all(f["artifact_kind"] == by_art[f["origin"]["id"]]["kind"] for f in every if f["file_kind"] == "artifact")
          and all(f["artifact_kind"] is None for f in every if f["file_kind"] != "artifact")
          and all("artifact_kind" in f for f in every), "artifact_kind equals the artifact record's kind; null otherwise")
    fid = {f["origin"]["id"]: f["id"] for f in every if f["origin"]}
    datasets = {fid[a["id"]] for a in arts if a["kind"] == "dataset"}
    codes = {fid[a["id"]] for a in arts if a["kind"] == "code"}
    docs = {fid[a["id"]] for a in arts if a["kind"] == "document"}
    check(files_of(A, "artifact_kind=dataset") == datasets, "single kind selects exactly that kind")
    union = files_of(A, "artifact_kind=dataset&artifact_kind=code")
    check(union == datasets | codes and files_of(A, "artifact_kind=code&artifact_kind=dataset&artifact_kind=code") == union,
          "repeated kinds are OR; reordered/duplicate values select the same set")
    check(files_of(A, "artifact_kind=report") == set() and note["id"] not in files_of(A, "artifact_kind=document")
          and files_of(A, "artifact_kind=document") == docs, "a note tagged reports/documents never enters kind queries")
    check(files_of(A, "file_kind=note&artifact_kind=report") == set()
          and files_of(A, "file_kind=record&artifact_kind=dataset") == set()
          and files_of(A, "file_kind=artifact&artifact_kind=dataset") == datasets, "contradictory constraints match nothing")
    check(files_of(A, "tag=datasets&artifact_kind=dataset&artifact_kind=code") == datasets
          and files_of(A, "q=heights-1&artifact_kind=dataset") == {fid[arts[1]["id"]]}, "other constraints stay AND")
    check(fid.get(b_art["id"]) is None and files_of(B, "artifact_kind=dataset") == {file_by_origin(B, "artifact", b_art["id"])["id"]},
          "kind selection is project scoped")
    bad = ["artifact_kind=bogus", "artifact_kind=", "artifact_kind=Dataset", "&".join(["artifact_kind=code"] * 11)]
    check(all(api("GET", f"{F}?{q}")[0] == 400 and code(api("GET", f"{F}?{q}")[2]) == "INVALID_QUERY" for q in bad),
          "invalid, empty, wrong-case, and >10 kind values -> 400 INVALID_QUERY")

    print("3. Pagination and cursor binding")
    q = "artifact_kind=dataset&artifact_kind=code&sort=created_at&order=desc"
    expected = [f["id"] for f in sorted((f for f in every if f["id"] in datasets | codes),
                                        key=lambda f: (f["created_at"], f["id"]), reverse=True)]
    check([f["id"] for f in all_pages(f"{F}?{q}", limit=2)] == expected and len(expected) == 5,
          "selection applies before LIMIT: 3 pages of 2 return exactly the 5 matches in order")
    _, _, page1 = api("GET", f"{F}?{q}&limit=2")
    cur = urllib.parse.quote(page1["next_cursor"])
    s, _, same = api("GET", f"{F}?artifact_kind=code&artifact_kind=dataset&artifact_kind=code&limit=2&cursor={cur}")
    check(s == 200 and [f["id"] for f in same["items"]] == expected[2:4], "equivalent reordered kinds continue the cursor")
    s, _, bare = api("GET", f"{F}?limit=2&cursor={cur}")
    check(s == 200 and [f["id"] for f in bare["items"]] == expected[2:4], "the cursor carries the canonical selection")
    s, _, body = api("GET", f"{F}?artifact_kind=dataset&limit=2&cursor={cur}")
    check(s == 400 and code(body) == "INVALID_QUERY", "changed selection with an old cursor -> 400 INVALID_QUERY")
    forged = [{"artifact_kind": ["dataset", "code"]}, {"artifact_kind": []}, {"artifact_kind": ["bogus"]},
              {"artifact_kind": "dataset"}, {"origin_id": "x"}]
    check(all(code(api("GET", f"{F}?cursor=" + forge_cursor({"v": 1, "t": "files", "p": A, "s": "created_at", "o": "asc",
                                                              "f": f, "k": "x", "i": "y"}))[2]) == "INVALID_CURSOR"
              for f in forged), "non-canonical/invalid kinds and unpaired origin_id in a cursor -> INVALID_CURSOR")
    return fid, datasets, codes


def origin_lookup(A, B, arts, src, b_art, fid):
    print("4. Exact origin lookup")
    F = f"/projects/{A}/files"
    a0 = arts[0]["id"]
    check(files_of(A, f"origin_type=artifact&origin_id={a0}") == {fid[a0]}
          and files_of(A, f"origin_type=source&origin_id={src['id']}") == {fid[src['id']]}, "paired origin lookup finds one file")
    check(files_of(A, f"origin_type=source&origin_id={a0}") == set()
          and files_of(A, f"origin_type=artifact&origin_id={b_art['id']}") == set()
          and files_of(A, "origin_type=artifact&origin_id=art_" + "0" * 32) == set(),
          "mismatched type, other-project, or unknown origin -> empty (no disclosure)")
    s, _, body = api("GET", f"{F}?origin_id={a0}")
    check(s == 400 and code(body) == "INVALID_QUERY", "origin_id without origin_type -> 400 INVALID_QUERY")
    s, _, body = api("GET", f"{F}?origin_type=artifact&origin_id=" + "x" * 101)
    check(s == 400, "overlong origin_id -> 400")
    _, _, page = api("GET", f"{F}?origin_type=artifact&limit=1")
    cur = urllib.parse.quote(page["next_cursor"])
    check(code(api("GET", f"{F}?origin_type=artifact&origin_id={a0}&cursor={cur}")[2]) == "INVALID_QUERY",
          "adding origin_id to an old cursor -> 400 INVALID_QUERY")


# -- 5-6. saved kinds and presentation -------------------------------------------------------

def saved_kinds(A, datasets, codes):
    print("5. Saved artifact_kinds filters")
    C = f"/projects/{A}/collections"
    s, _, K = post(C, {"name": "Data and code", "filter": {"artifact_kinds": ["dataset", "code", "dataset"]}})
    check(s == 201 and K["filter"] == {"artifact_kinds": ["code", "dataset"]} and K["file_count"] == 5
          and K["presentation"] is None, "saved kinds are deduplicated/sorted; dynamic count uses the same predicate")
    Kq = f"collection_id={K['id']}"
    check(files_of(A, Kq) == datasets | codes and files_of(A, f"{Kq}&artifact_kind=code") == codes
          and files_of(A, f"{Kq}&artifact_kind=document") == set() and files_of(A, f"{Kq}&file_kind=note") == set(),
          "query kinds intersect saved kinds")
    bad = [[], [None], [5], ["bogus"], "dataset", {"a": 1}, ["dataset"] * 11, [["dataset"]]]
    results = [post(C, {"name": "x", "filter": {"artifact_kinds": b}}) for b in bad]
    check(all(s == 422 and code(b) == "VALIDATION_FAILED" and all(p.startswith("/filter/artifact_kinds") for p in paths(b))
              and paths(b) for s, _, b in results), f"{len(bad)} invalid saved artifact_kinds -> 422 with field paths")
    upload(A, b"t_s,height_px\n0.0,7\n", "SIMULATED-late.csv", "text/csv", "dataset")
    check(api("GET", f"{C}/{K['id']}")[2]["file_count"] == 6, "dynamic count follows a new artifact of a saved kind")
    return K


def presentation(A, B):
    print("6. Collection presentation")
    C = f"/projects/{A}/collections"
    P1 = {"preset": "media-data", "sort": "created_at", "order": "desc"}
    idem = key()
    s, h, V = post(C, {"name": "Motion recordings", "filter": {"artifact_kinds": ["video"], "status": "active"},
                       "presentation": P1}, idem)
    check(s == 201 and V["presentation"] == P1 and V["revision"] == 1 and h.get("ETag") == '"1"', "POST with presentation")
    s, h, again = post(C, {"name": "Motion recordings", "filter": {"artifact_kinds": ["video"], "status": "active"},
                           "presentation": P1}, idem)
    check(s == 201 and h.get("Idempotent-Replayed") == "true" and again["id"] == V["id"], "idempotent POST replay")
    s, _, E = post(C, {"name": "Explicit"})
    check(s == 201 and E["presentation"] is None, "omitted presentation on POST -> null")
    bad = [{}, {"preset": "all", "sort": "name"}, {**P1, "extra": 1}, {**P1, "preset": "gallery"},
           {**P1, "sort": "size"}, {**P1, "order": "up"}, {**P1, "order": None}, "all", ["all"], 5]
    results = [post(C, {"name": "x", "presentation": b}) for b in bad]
    check(all(s == 422 and code(b) == "VALIDATION_FAILED" and paths(b) and all(p.startswith("/presentation") for p in paths(b))
              for s, _, b in results), f"{len(bad)} invalid presentations -> 422 with /presentation paths")
    check(all(api("PATCH", f"{C}/{V['id']}", {"presentation": b}, {"If-Match": '"1"'})[0] == 422 for b in bad[:4]),
          "invalid presentation PATCH -> 422")

    P = f"{C}/{V['id']}"
    start = event_cursor(A)
    s, h, same = api("PATCH", P, {"presentation": {"order": "desc", "sort": "created_at", "preset": "media-data"}},
                     {"If-Match": '"1"'})
    check(s == 200 and same["revision"] == 1 and h.get("ETag") == '"1"', "equal canonical presentation -> no-op")
    check(event_cursor(A) == start, "no-op PATCH emits no event")
    P2 = {"preset": "all", "sort": "name", "order": "asc"}
    s, h, upd = api("PATCH", P, {"presentation": P2}, {"If-Match": '"1"'})
    check(s == 200 and upd["presentation"] == P2 and upd["revision"] == 2 and h.get("ETag") == '"2"'
          and upd["filter"] == V["filter"] and upd["file_count"] == V["file_count"],
          "presentation replaced: new revision/ETag; filter and members unchanged")
    check({"entity": "collection", "id": V["id"], "revision": 2, "deleted": False} in catalog_changes(A, start),
          "presentation change emits catalog.changed")
    s, _, body = api("PATCH", P, {"presentation": P1}, {"If-Match": '"1"'})
    check(s == 412 and code(body) == "REVISION_CONFLICT" and body["error"]["details"]["current_revision"] == 2,
          "stale If-Match -> 412")
    s, _, ren = api("PATCH", P, {"name": "Renamed recordings"}, {"If-Match": '"2"'})
    check(s == 200 and ren["presentation"] == P2 and ren["revision"] == 3, "omitted presentation on PATCH -> unchanged")
    s, _, cleared = api("PATCH", P, {"presentation": None}, {"If-Match": '"3"'})
    check(s == 200 and cleared["presentation"] is None and cleared["revision"] == 4, "null clears presentation")
    s, _, ep = api("PATCH", f"{C}/{E['id']}", {"presentation": P2}, {"If-Match": '"1"'})
    source(A, "Projection trigger (SIMULATED)")
    check(s == 200 and api("GET", f"{C}/{E['id']}")[2]["presentation"] == P2, "projection never resets presentation")

    print("7. Archived project")
    idem_b = key()
    s, _, BC = post(f"/projects/{B}/collections", {"name": "B view", "presentation": P1}, idem_b)
    assert s == 201, BC
    set_project_status(B, "archived")
    try:
        attempts = [post(f"/projects/{B}/collections", {"name": "y", "presentation": P2}),
                    api("PATCH", f"/projects/{B}/collections/{BC['id']}", {"presentation": P2}, {"If-Match": '"1"'})]
        check(all(s == 409 and code(b) == "PROJECT_ARCHIVED" for s, _, b in attempts),
              "presentation POST/PATCH on an archived project -> 409 PROJECT_ARCHIVED")
        s, h, replay = post(f"/projects/{B}/collections", {"name": "B view", "presentation": P1}, idem_b)
        check(s == 201 and h.get("Idempotent-Replayed") == "true" and replay["id"] == BC["id"],
              "replay of an earlier committed POST keeps its response")
        check(api("GET", f"/projects/{B}/collections/{BC['id']}")[2]["presentation"] == P1, "archived project readable")
    finally:
        set_project_status(B, "active")


# -- 8. real API migration of a downgraded catalog -------------------------------------------

def snapshot(pid):
    files = sorted(all_pages(f"/projects/{pid}/files?status=all"), key=lambda f: f["id"])
    notes = {f["id"]: all_pages(f"/projects/{pid}/files/{f['id']}/revisions") for f in files if f["file_kind"] == "note"}
    return {"files": files, "notes": notes, "tags": all_pages(f"/projects/{pid}/tags"),
            "collections": all_pages(f"/projects/{pid}/collections"), "relations": all_pages(f"/projects/{pid}/relations")}


def api_migration(run):
    print("8. Populated v1 catalog migrated by the real API (artifact kinds backfilled without new events)")
    M = project(f"WV migrate {run} (SIMULATED)")
    data = upload(M, b"t_s,height_px\n0.0,3\n", "SIMULATED-m.csv", "text/csv", "dataset")
    code_art = upload(M, b"print('m')\n", "SIMULATED_m.py", "text/x-python", "code")
    source(M, "Migration reference (SIMULATED)")
    _, _, note = post(f"/projects/{M}/files", {"name": "m.md", "content": "rev 1\n", "tags": ["follow-up"]})
    s, _, note = api("PATCH", f"/projects/{M}/files/{note['id']}", {"content": "rev 2\n"}, {"If-Match": f'"{note["revision"]}"'})
    assert s == 200 and note["content_revision"] == 2, note
    df = file_by_origin(M, "artifact", data["id"])
    _, _, E = post(f"/projects/{M}/collections", {"name": "Explicit"})
    post(f"/projects/{M}/collections/{E['id']}/files", {"file_ids": [df["id"], note["id"]]})
    api("PATCH", f"/projects/{M}/collections/{E['id']}", {"name": "Explicit renamed"}, {"If-Match": '"1"'})
    post(f"/projects/{M}/collections", {"name": "Saved", "filter": {"tags": ["follow-up"]}})
    post(f"/projects/{M}/relations", {"from_file_id": note["id"], "to_file_id": df["id"], "type": "related"})
    before = snapshot(M)
    check(all(c["presentation"] is None for c in before["collections"]), "fixture collections have no presentation")

    in_container("--downgrade", f"{CATALOG_DIR}/{M}.sqlite3")
    start = event_cursor(M)
    s, _, cat = api("GET", f"/projects/{M}/catalog")
    check(s == 200 and cat["schema_version"] == 2 and cat["last_sync_error"] is None, "v1 catalog migrated to schema 2")
    after = snapshot(M)
    check(after == before, "IDs, revisions, dates, hashes, artifact kinds, tags, note revisions, collections "
                           "(revision, null presentation), and relations are identical after migration")
    kinds = {f["origin"]["id"]: f["artifact_kind"] for f in after["files"] if f["file_kind"] == "artifact"}
    check(kinds == {data["id"]: "dataset", code_art["id"]: "code"}, "artifact kinds backfilled from artifact records")
    check(files_of(M, "artifact_kind=code") == {file_by_origin(M, "artifact", code_art["id"])["id"]},
          "kind-filtered listing works immediately after migration")
    changes = catalog_changes(M, start)
    check(any(c.get("bulk") and c["entity"] == "file" for c in changes), "backfill emits a bulk file catalog.changed")
    cursor = event_cursor(M)
    api("GET", f"/projects/{M}/catalog")
    api("GET", f"/projects/{M}/files")
    check(event_cursor(M) == cursor and snapshot(M) == before, "reopening an upgraded catalog is a no-op")


def downgrade(path):
    """In-container helper: rewrite one catalog to the exact v1 shape (test project only)."""
    import sqlite3
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("DROP INDEX files_artifact_kind")
    conn.execute("ALTER TABLE files DROP COLUMN artifact_kind")
    conn.execute("ALTER TABLE collections DROP COLUMN presentation")
    conn.execute("DELETE FROM meta WHERE key = 'projection_version'")
    conn.execute("PRAGMA user_version = 1")
    conn.execute("COMMIT")
    print(f"  ..  downgraded test catalog to v1 (user_version={conn.execute('PRAGMA user_version').fetchone()[0]})")
    conn.close()


# -- 9. in-container fixture checks (FIXTURE, not live data) ---------------------------------

def fixtures():
    import sqlite3
    import tempfile
    import types
    from stellaris_api import catalog
    print("9. FIXTURE migration checks (temporary directory inside the api container)")

    def dump(conn):
        out = {}
        for table in ("meta", "files", "note_revisions", "tags", "file_tags", "collections", "collection_files",
                      "relations", "idempotency_keys", "outbox"):
            out[table] = sorted((dict(r) for r in conn.execute(f"SELECT * FROM {table}")), key=lambda r: json.dumps(r, sort_keys=True))
        return out

    def columns(conn, table):
        return [(r[1], r[2], r[3], r[5]) for r in conn.execute(f"PRAGMA table_info({table})")]

    def shape(conn):
        return {t: columns(conn, t) for t in ("files", "collections")} | {
            "indexes": sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"))}

    def strip(rows, extra):
        return [{k: v for k, v in r.items() if k != extra} for r in rows]

    with tempfile.TemporaryDirectory() as tmp:
        config = types.SimpleNamespace(catalog_dir=tmp)
        new_pid, v1_pid, newer_pid = (f"prj_{uuid.uuid4().hex}" for _ in range(3))
        conn = catalog.open_catalog(config, new_pid)
        new_shape = shape(conn)
        check(conn.execute("PRAGMA user_version").fetchone()[0] == 2
              and any(c[0] == "artifact_kind" for c in new_shape["files"])
              and any(c[0] == "presentation" for c in new_shape["collections"])
              and "files_artifact_kind" in new_shape["indexes"], "new catalog initializes schema 2 with index")
        conn.close()

        path = catalog.catalog_path(config, v1_pid)
        raw_conn = sqlite3.connect(path, isolation_level=None)
        raw_conn.row_factory = sqlite3.Row
        raw_conn.execute("BEGIN")
        for statement in catalog.SCHEMA:
            raw_conn.execute(statement)
        ts1, ts2 = "2026-01-02T03:04:05.000Z", "2026-02-03T04:05:06.000Z"
        raw_conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)",
                             [("project_id", v1_pid), ("created_at", ts1), ("synced_event_sequence", "7")])
        raw_conn.executemany("INSERT INTO tags VALUES (?, ?, ?, ?, ?, ?, ?)",
                             [("artifacts", "Artifacts", "#112233", 1, 2, ts1, ts2), ("follow-up", "Follow up", None, 0, 1, ts1, ts1)])
        raw_conn.executemany(
            "INSERT INTO files (id, file_kind, origin_type, origin_id, origin_revision, name, name_key, mime_type, size_bytes, "
            "content_sha256, scientific_origin, status, content_revision, render_version, revision, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [("fil_" + "1" * 32, "artifact", "artifact", "art_" + "1" * 32, None, "SIMULATED.csv", "simulated.csv",
              "text/csv", 10, "a" * 64, "simulated", "active", None, None, 3, ts1, ts2),
             ("fil_" + "2" * 32, "note", None, None, None, "n.md", "n.md", "text/markdown", 6, "b" * 64, None,
              "trashed", 2, None, 5, ts1, ts2)])
        raw_conn.executemany("INSERT INTO note_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             [("fil_" + "2" * 32, 1, "n.md", "text/markdown", "rev 1\n", 6, "c" * 64, ts1),
                              ("fil_" + "2" * 32, 2, "n.md", "text/markdown", "rev 2\n", 6, "b" * 64, ts2)])
        raw_conn.executemany("INSERT INTO file_tags VALUES (?, ?, ?, ?)",
                             [("fil_" + "1" * 32, "artifacts", "system", ts1), ("fil_" + "2" * 32, "follow-up", "user", ts2)])
        raw_conn.executemany("INSERT INTO collections VALUES (?, ?, ?, ?, ?, ?, ?)",
                             [("col_" + "1" * 32, "Explicit", "", None, 4, ts1, ts2),
                              ("col_" + "2" * 32, "Saved", "d", '{"tags":["follow-up"]}', 1, ts1, ts1)])
        raw_conn.execute("INSERT INTO collection_files VALUES (?, ?, ?)", ("col_" + "1" * 32, "fil_" + "2" * 32, ts2))
        raw_conn.execute("INSERT INTO relations VALUES (?, ?, ?, ?, ?, ?, ?)",
                         ("rel_" + "1" * 32, "fil_" + "2" * 32, "fil_" + "1" * 32, "related", "SIMULATED", "user", ts2))
        raw_conn.execute("PRAGMA user_version = 1")
        raw_conn.execute("COMMIT")
        before = dump(raw_conn)
        v1_shape = shape(raw_conn)
        raw_conn.close()

        original = catalog.MIGRATIONS[2]
        catalog.MIGRATIONS[2] = original + ("SELECT * FROM simulated_missing_table",)
        try:
            failed = False
            try:
                catalog.open_catalog(config, v1_pid).close()
            except catalog.CatalogUnavailable:
                failed = True
        finally:
            catalog.MIGRATIONS[2] = original
        raw_conn = sqlite3.connect(path)
        raw_conn.row_factory = sqlite3.Row
        check(failed and raw_conn.execute("PRAGMA user_version").fetchone()[0] == 1 and shape(raw_conn) == v1_shape
              and dump(raw_conn) == before, "simulated migration failure -> unavailable, complete rollback, v1 intact")
        raw_conn.close()

        conn = catalog.open_catalog(config, v1_pid)
        after = dump(conn)
        check(conn.execute("PRAGMA user_version").fetchone()[0] == 2 and shape(conn) == new_shape,
              "populated v1 catalog migrates to the same schema as a new catalog")
        check(all(r["artifact_kind"] is None for r in after["files"]) and strip(after["files"], "artifact_kind") == before["files"]
              and all(r["presentation"] is None for r in after["collections"])
              and strip(after["collections"], "presentation") == before["collections"],
              "files and collections preserved exactly; new columns null until projection")
        check(all(after[t] == before[t] for t in ("meta", "note_revisions", "file_tags", "collection_files", "relations",
                                                   "idempotency_keys", "outbox"))
              and all(r in after["tags"] for r in before["tags"]), "notes, revisions, tags, memberships, relations preserved")
        conn.close()
        for _ in range(2):
            catalog._checked.discard(path)  # Force the first-open (seed) path again.
            conn = catalog.open_catalog(config, v1_pid)
            same = dump(conn) == after and conn.execute("PRAGMA user_version").fetchone()[0] == 2
            conn.close()
            check(same, "reopening the upgraded catalog is a no-op")

        newer = catalog.catalog_path(config, newer_pid)
        raw_conn = sqlite3.connect(newer, isolation_level=None)
        raw_conn.execute("PRAGMA user_version = 3")
        raw_conn.close()
        try:
            catalog.open_catalog(config, newer_pid).close()
            refused = False
        except catalog.CatalogUnavailable:
            refused = True
        raw_conn = sqlite3.connect(newer)
        check(refused and raw_conn.execute("PRAGMA user_version").fetchone()[0] == 3,
              "a newer catalog version is refused and never downgraded")
        raw_conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-docker", action="store_true", help="skip in-container migration checks")
    parser.add_argument("--fixtures", action="store_true", help=argparse.SUPPRESS)  # In-container mode.
    parser.add_argument("--downgrade", help=argparse.SUPPRESS)                       # In-container mode.
    args = parser.parse_args()
    if args.downgrade:
        downgrade(args.downgrade)
        return
    if args.fixtures:
        fixtures()
        print(f"  ..  {len(PASSED)} fixture checks passed")
        return
    run = uuid.uuid4().hex[:8]
    A, B, arts, src, b_art, note = capability_and_fixtures(run)
    fid, datasets, codes = artifact_kinds(A, B, arts, note, b_art)
    origin_lookup(A, B, arts, src, b_art, fid)
    saved_kinds(A, datasets, codes)
    presentation(A, B)
    if args.skip_docker:
        print("  --  migration checks skipped (--skip-docker)")
    else:
        api_migration(run)
        in_container("--fixtures")
    print(f"\nPASSED {len(PASSED)} checks (plus in-container fixture checks when run)")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"\nFAILED after {len(PASSED)} checks: {exc}")
        sys.exit(1)
