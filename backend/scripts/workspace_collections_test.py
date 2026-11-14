#!/usr/bin/env python3
"""Docker integration checks for workspace collections and relations (file-workspace contract slice 3).

Run from backend/ (stdlib only) after rebuilding and `docker compose up -d --wait`:

    python3 scripts/workspace_collections_test.py
    python3 scripts/workspace_collections_test.py --skip-limits --skip-system

Covers explicit and saved-filter collections (CRUD, ETags, idempotency, membership revisions,
dynamic saved results, status/query intersections, filter validation), user relations
(validation, direction/type/created_by filters, cursors, deletion), no-op operations that
must emit no event, archived-project 409s, the 200-collection limit, and system relations
projected from recorded provenance.

All fixture data is SYNTHETIC: uploads use origin "simulated" and SIMULATED names; the
optional analysis run computes a mean over a generated CSV and its claim is labelled
SIMULATED. No model or provider is called. Notes/tagging checks run only when the slice 2
routes are available. Creates new projects and containers, which are retained.
Does not read any .env file.
"""

import argparse
import base64
import hashlib
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = os.environ.get("STELLARIS_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
_PARSED = urllib.parse.urlsplit(BASE)
PASSED = []
TERMINAL = ("succeeded", "failed", "cancelled")
RESERVED = ("derived_from", "produced_by", "cites", "uses_evidence")

# SIMULATED analysis for python_analysis_v1: mean of a generated column, one derived summary
# CSV whose parent is the input, and one SIMULATED observation claim. Not a real analysis.
PY_FIXTURE = r'''
import json
manifest = json.load(open("/input/manifest.json"))
data = next(a for a in manifest["inputs"] if a["kind"] == "dataset")
lines = open(data["path"], encoding="utf-8").read().splitlines()[1:]
values = [float(line.split(",")[1]) for line in lines if line]
mean = sum(values) / len(values)
open("/output/summary.csv", "w").write("quantity,value\nmean_height,%r\n" % mean)
evidence = [{"artifact": {"input_artifact_id": data["artifact_id"]}, "frame_index": None, "time_s": None, "row_index": 0}]
measurement = {
    "local_key": "mean", "series": "summary", "quantity": "mean_height", "value": mean, "unit": "px", "time_s": None,
    "uncertainty": {"absolute": None, "method": None}, "status": "valid", "evidence": evidence,
    "calibration_mode": manifest["calibration"]["mode"], "data_origin": "derived",
    "assumptions": ["SIMULATED fixture: arithmetic mean of a generated column."]}
claim = {"local_key": "c1", "kind": "observation", "text": "SIMULATED: the generated column has a mean.",
         "measurement_keys": ["mean"], "citations": [], "evidence": evidence,
         "assumptions": ["SIMULATED fixture."], "limitations": ["Synthetic data only."]}
artifact = {"local_key": "summary", "path": "summary.csv", "kind": "dataset", "origin": "derived",
            "mime_type": "text/csv", "parents": [{"input_artifact_id": data["artifact_id"]}]}
json.dump({"measurements": [measurement], "claims": [claim], "artifacts": [artifact], "warnings": []},
          open("/output/result.json", "w"))
print("done", flush=True)
'''


# -- helpers --------------------------------------------------------------------------------

def check(condition, message):
    if not condition:
        raise AssertionError(message)
    PASSED.append(message)
    print(f"  ok  {message}")


def key():
    return f"wc-{uuid.uuid4().hex}"


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


def forge_cursor(state):
    return base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode().rstrip("=")


def upload(pid, data, filename, mime, kind, origin):
    status, _, up = post(f"/projects/{pid}/uploads", {"filename": filename, "mime_type": mime, "size_bytes": len(data),
                                                       "sha256": hashlib.sha256(data).hexdigest(), "kind": kind,
                                                       "origin": origin})
    assert status == 201, up
    status, _, body = raw("PUT", f"/projects/{pid}/uploads/{up['id']}/content", data, {"Content-Type": mime})
    assert status == 204, body
    status, _, art = post(f"/projects/{pid}/uploads/{up['id']}/complete", {})
    assert status == 200, art
    return art


def wait_run(pid, run_id, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = api("GET", f"/projects/{pid}/runs/{run_id}")[2]
        if run["status"] in TERMINAL:
            return run
        time.sleep(1)
    raise AssertionError(f"run {run_id} did not finish within {timeout}s")


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


def get_file(pid, fid):
    status, _, item = api("GET", f"/projects/{pid}/files/{fid}")
    assert status == 200, item
    return item


def files_of(pid, query):
    return ids(all_pages(f"/projects/{pid}/files?{query}"))


def project(name):
    status, _, body = post("/projects", {"name": name})
    assert status == 201, body
    return body["id"]


def source(pid, title):
    status, _, body = post(f"/projects/{pid}/sources", {"title": title, "url": "https://example.org/simulated-reference"})
    assert status == 201, body
    return body


def file_for(pid, origin_type, origin_id):
    for f in all_pages(f"/projects/{pid}/files?status=all"):
        if f["origin"] and f["origin"]["type"] == origin_type and f["origin"]["id"] == origin_id:
            return f
    raise AssertionError(f"no file for {origin_type} {origin_id}")


def set_project_status(pid, status):
    _, h, _ = api("GET", f"/projects/{pid}")
    s, _, body = api("PATCH", f"/projects/{pid}", {"status": status}, {"If-Match": h["ETag"]})
    assert s == 200, body


# -- collections ----------------------------------------------------------------------------

def collections(A, B, files, notes):
    S1, S2, S3, CSV = files
    C = f"/projects/{A}/collections"
    print("2. Explicit collections: create, idempotency, validation")
    status, _, body = api("POST", C, {"name": "x"})
    check(status == 428 and code(body) == "PRECONDITION_REQUIRED", "POST /collections without Idempotency-Key -> 428")
    idem = key()
    status, h, E = post(C, {"name": "  Reading list  ", "description": "SIMULATED fixture"}, idem)
    check(status == 201 and E["id"].startswith("col_") and len(E["id"]) == 36 and E["name"] == "Reading list"
          and E["filter"] is None and E["file_count"] == 0 and E["revision"] == 1 and E["project_id"] == A,
          "explicit collection created (trimmed name, filter null, count 0, revision 1)")
    check(h.get("ETag") == '"1"' and h.get("Location") == f"/api/v1/projects/{A}/collections/{E['id']}",
          "create returns ETag and Location")
    status, h, again = post(C, {"name": "  Reading list  ", "description": "SIMULATED fixture"}, idem)
    check(status == 201 and h.get("Idempotent-Replayed") == "true" and again["id"] == E["id"], "same key replays")
    status, _, body = post(C, {"name": "Other"}, idem)
    check(status == 409 and code(body) == "IDEMPOTENCY_CONFLICT", "same key with another body -> 409")
    status, h, got = api("GET", f"{C}/{E['id']}")
    check(status == 200 and got == E and h.get("ETag") == '"1"', "GET collection returns it with ETag")

    bad = [{}, {"name": ""}, {"name": "   "}, {"name": "x" * 121}, {"name": 5}, {"name": ["a"]}, {"name": None},
           {"name": "ok", "description": 5}, {"name": "ok", "description": "x" * 2001}, {"name": "ok", "extra": 1}]
    bad_filters = ["x", [], 5, True, {"tags": "research"}, {"tags": [["a"]]}, {"tags": [{"a": 1}]}, {"tags": [None]},
                   {"tags": ["Bad_Slug"]}, {"tags": [f"t{i}" for i in range(11)]}, {"file_kind": ["note"]},
                   {"file_kind": {"k": 1}}, {"file_kind": "folder"}, {"origin_type": "message"},
                   {"origin_type": None}, {"status": "archived"}, {"status": ["all"]}, {"q": ""}, {"q": "x" * 101},
                   {"q": 5}, {"q": ["a"]}, {"collection_id": E["id"]}, {"bogus": 1}]
    bad += [{"name": "ok", "filter": f} for f in bad_filters]
    results = [post(C, b) for b in bad]
    check(all(s == 422 and code(b) == "VALIDATION_FAILED" for s, _, b in results),
          f"{len(bad)} malformed collection bodies/filters (types, enums, limits, recursion) -> 422")
    status, _, body = api("POST", C, [1], {"Idempotency-Key": key()})
    check(status == 422, "non-object body -> 422")
    check(ids(all_pages(C)) == {E["id"]}, "rejected requests created no collection")
    status, _, body = api("POST", C, {"name": "x"}, {"Idempotency-Key": key(), "Content-Type": "text/plain"})
    check(status == 415, "non-JSON body -> 415")

    print("3. Explicit membership")
    rev = {f: get_file(A, f)["revision"] for f in (S1, S2, S3, CSV)}
    M = f"{C}/{E['id']}/files"
    status, _, body = post(M, {"file_ids": [S1, S2]})
    check(status == 200 and body["added_file_ids"] == [S1, S2] and body["collection"]["revision"] == 1
          and body["collection"]["file_count"] == 2, "add members -> 200 added ids, collection revision unchanged")
    f1 = get_file(A, S1)
    check(f1["revision"] == rev[S1] + 1 and f1["collection_ids"] == [E["id"]], "member file revision bumped, collection_ids set")
    check(get_file(A, S3)["revision"] == rev[S3], "non-member file revision unchanged")
    idem_add = key()
    status, _, body = post(M, {"file_ids": [S2, S3]}, idem_add)
    check(status == 200 and body["added_file_ids"] == [S3] and get_file(A, S2)["revision"] == rev[S2] + 1,
          "already-present members are ignored and not re-bumped")
    check(files_of(A, f"collection_id={E['id']}") == {S1, S2, S3}, "GET /files?collection_id lists explicit members")
    check(files_of(A, f"collection_id={E['id']}&origin_type=artifact") == set()
          and files_of(A, f"collection_id={E['id']}&q=alpha") == {S1, S2}, "query filters intersect explicit membership")

    bad_members = [{}, {"file_ids": []}, {"file_ids": "x"}, {"file_ids": [S1] * 2}, {"file_ids": [5]},
                   {"file_ids": [["x"]]}, {"file_ids": [{"a": 1}]}, {"file_ids": [f"fil_{i:032x}" for i in range(101)]},
                   {"file_ids": [S1], "extra": 1}, {"file_ids": [""]}]
    check(all(post(M, b)[0] == 422 for b in bad_members), f"{len(bad_members)} malformed membership bodies -> 422")
    status, _, body = post(M, {"file_ids": [S1, "fil_" + "0" * 32]})
    check(status == 422 and code(body) == "INVALID_REFERENCE"
          and body["error"]["details"]["field_errors"][0]["path"] == "/file_ids/1", "unknown file -> 422 INVALID_REFERENCE")
    b_file = all_pages(f"/projects/{B}/files")[0]["id"]
    status, _, body = post(M, {"file_ids": [b_file]})
    check(status == 422 and code(body) == "INVALID_REFERENCE", "another project's file -> 422 INVALID_REFERENCE")
    _, _, EB = post(f"/projects/{B}/collections", {"name": "B collection"})
    check(post(f"{C}/col_{'0' * 32}/files", {"file_ids": [S1]})[0] == 404
          and post(f"{C}/{EB['id']}/files", {"file_ids": [S1]})[0] == 404
          and api("GET", f"{C}/{EB['id']}")[0] == 404, "unknown or other-project collection -> 404")

    s3_rev = get_file(A, S3)["revision"]
    status, _, _ = api("DELETE", f"{M}/{S3}")
    f3 = get_file(A, S3)
    check(status == 204 and f3["revision"] == s3_rev + 1 and f3["collection_ids"] == [], "remove member -> 204, revision bumped")
    check(api("DELETE", f"{M}/{S3}")[0] == 204 and get_file(A, S3)["revision"] == s3_rev + 1,
          "removing a non-member -> 204 without a revision bump")
    check(api("DELETE", f"{M}/fil_{'0' * 32}")[0] == 404 and api("DELETE", f"{C}/col_{'0' * 32}/files/{S1}")[0] == 404,
          "remove with unknown file or collection -> 404")

    if notes:
        N1 = notes[0]
        post(M, {"file_ids": [N1]})
        n = get_file(A, N1)
        s, _, _ = api("PATCH", f"/projects/{A}/files/{N1}", {"status": "trashed"}, {"If-Match": f'"{n["revision"]}"'})
        check(s == 200 and get_file(A, N1)["collection_ids"] == [E["id"]], "trashed note keeps its membership")
        check(N1 not in files_of(A, f"collection_id={E['id']}")
              and files_of(A, f"collection_id={E['id']}&status=trashed") == {N1}
              and api("GET", f"{C}/{E['id']}")[2]["file_count"] == 2,
              "explicit listing/count hide trashed members; status=trashed shows them")

    print("4. PATCH and listing")
    P = f"{C}/{E['id']}"
    check(api("PATCH", P, {"name": "x"})[0] == 428, "PATCH without If-Match -> 428")
    status, _, body = api("PATCH", P, {"name": "x"}, {"If-Match": '"99"'})
    check(status == 412 and code(body) == "REVISION_CONFLICT" and body["error"]["details"]["current_revision"] == 1,
          "stale If-Match -> 412 with current_revision")
    check(all(api("PATCH", P, b, {"If-Match": '"1"'})[0] == 422
              for b in ({}, {"filter": "x"}, {"name": ""}, {"extra": 1}, {"filter": {"tags": [1]}})),
          "malformed PATCH bodies -> 422")
    status, h, same = api("PATCH", P, {"name": "Reading list", "description": "SIMULATED fixture"}, {"If-Match": '"1"'})
    check(status == 200 and same["revision"] == 1 and h.get("ETag") == '"1"', "equal-value PATCH keeps the revision")
    status, h, renamed = api("PATCH", P, {"name": "Renamed"}, {"If-Match": '"1"'})
    check(status == 200 and renamed["revision"] == 2 and renamed["name"] == "Renamed" and h.get("ETag") == '"2"',
          "PATCH name -> new revision and ETag")
    status, _, body = api("PATCH", P, {"filter": {}}, {"If-Match": '"2"'})
    check(status == 409 and code(body) == "COLLECTION_NOT_EMPTY", "switching to a saved filter with members -> 409")

    print("5. Saved-filter collections")
    status, _, F = post(C, {"name": "Research", "filter": {"tags": ["research", "research"]}})
    check(status == 201 and F["filter"] == {"tags": ["research"]} and F["file_count"] == 3,
          "saved tag filter -> dynamic count of matching files")
    check(files_of(A, f"collection_id={F['id']}") == {S1, S2, S3} and F["id"] not in get_file(A, S1)["collection_ids"],
          "saved members are listed but never in file.collection_ids")
    status, _, body = post(f"{C}/{F['id']}/files", {"file_ids": [S1]})
    check(status == 409 and code(body) == "COLLECTION_READ_ONLY", "adding to a saved filter -> 409 COLLECTION_READ_ONLY")
    status, _, body = api("DELETE", f"{C}/{F['id']}/files/{S1}")
    check(status == 409 and code(body) == "COLLECTION_READ_ONLY", "removing from a saved filter -> 409")
    S4 = file_for(A, "source", source(A, "Gamma (SIMULATED)")["id"])["id"]
    check(api("GET", f"{C}/{F['id']}")[2]["file_count"] == 4 and S4 in files_of(A, f"collection_id={F['id']}"),
          "saved results follow new legacy records")
    Fq = f"collection_id={F['id']}"
    check(files_of(A, f"{Fq}&q=alpha") == {S1, S2} and files_of(A, f"{Fq}&file_kind=artifact") == set()
          and files_of(A, f"{Fq}&tag=datasets") == set() and files_of(A, f"{Fq}&status=trashed") == set()
          and files_of(A, f"{Fq}&status=all") == {S1, S2, S3, S4}, "explicit query filters intersect the saved filter")
    _, _, Fq2 = post(C, {"name": "Alpha research", "filter": {"tags": ["research"], "q": "ALPHA", "file_kind": "record"}})
    check(files_of(A, f"collection_id={Fq2['id']}") == {S1, S2} and Fq2["file_count"] == 2, "tags+q+kind saved filter")
    every = files_of(A, "status=all")
    _, _, G = post(C, {"name": "Everything", "filter": {"status": "all"}})
    _, _, T = post(C, {"name": "Trash", "filter": {"status": "trashed"}})
    trashed = files_of(A, "status=trashed")
    check(G["file_count"] == len(every) and files_of(A, f"collection_id={G['id']}") == every,
          "saved status=all lists every file")
    check(T["file_count"] == len(trashed) and files_of(A, f"collection_id={T['id']}") == trashed,
          f"saved status=trashed lists trashed files ({len(trashed)})")
    check(files_of(A, f"collection_id={T['id']}&status=all") == trashed
          and files_of(A, f"collection_id={T['id']}&status=active") == set(), "status intersection is a set intersection")
    if notes:
        check(trashed == {notes[0]}, "the trashed note appears in the saved trashed collection")
    status, _, tagging = post(f"/projects/{A}/files/tagging", {"file_ids": [S1], "add": ["alpha-tag"]})
    if status == 200:
        _, _, U = post(C, {"name": "User tag", "filter": {"tags": ["alpha-tag", "research"]}})
        check(files_of(A, f"collection_id={U['id']}") == {S1}, "saved filter on a user tag AND a system tag")
    else:
        print(f"  --  tagging route unavailable ({status}); user-tag saved filter skipped")
    FP = f"{C}/{F['id']}"
    status, _, body = api("PATCH", FP, {"filter": {"tags": ["research"]}}, {"If-Match": '"1"'})
    check(status == 200 and body["revision"] == 1, "PATCH with an equal saved filter keeps the revision")
    status, _, body = api("PATCH", FP, {"filter": None}, {"If-Match": '"1"'})
    check(status == 200 and body["filter"] is None and body["revision"] == 2 and body["file_count"] == 0,
          "empty saved collection can switch to explicit mode")
    status, _, body = api("PATCH", FP, {"filter": {"file_kind": "record"}}, {"If-Match": '"2"'})
    check(status == 200 and body["revision"] == 3 and body["filter"] == {"file_kind": "record"},
          "empty explicit collection can switch to a saved filter")

    all_cols = all_pages(C)
    paged = all_pages(C, limit=1)
    check([c["id"] for c in paged] == [c["id"] for c in all_cols] and len(all_cols) >= 6
          and all_cols == sorted(all_cols, key=lambda c: (c["created_at"], c["id"])), "collections page in (created_at, id) order")
    check(api("GET", f"{C}?cursor=***")[0] == 400
          and code(api("GET", f"{C}?cursor={forge_cursor({'v': 1, 't': 'relations', 'p': A, 'f': {}, 'c': 'x', 'i': 'y'})}")[2]) == "INVALID_CURSOR"
          and code(api("GET", f"{C}?cursor={forge_cursor({'v': 1, 't': 'collections', 'p': B, 'f': {}, 'c': 'x', 'i': 'y'})}")[2]) == "INVALID_CURSOR",
          "malformed, other-route, and other-project cursors -> 400 INVALID_CURSOR")

    print("6. Delete collection")
    check(api("DELETE", P)[0] == 428, "DELETE collection without If-Match -> 428")
    check(api("DELETE", P, headers={"If-Match": '"1"'})[0] == 412, "DELETE with stale If-Match -> 412")
    before = {f: get_file(A, f)["revision"] for f in (S1, S2, S3)}
    check(api("DELETE", P, headers={"If-Match": '"2"'})[0] == 204, "DELETE collection -> 204")
    check(api("GET", P)[0] == 404 and api("GET", f"/projects/{A}/files?collection_id={E['id']}")[0] == 404,
          "deleted collection and its listing -> 404")
    after = {f: get_file(A, f) for f in (S1, S2, S3)}
    check(after[S1]["revision"] == before[S1] + 1 and after[S2]["revision"] == before[S2] + 1
          and after[S3]["revision"] == before[S3] and all(E["id"] not in f["collection_ids"] for f in after.values()),
          "files remain; former members get a new revision without the membership")
    return EB


# -- relations ------------------------------------------------------------------------------

def relations(A, B, files):
    S1, S2, S3, CSV = files
    R = f"/projects/{A}/relations"
    print("7. User relations")
    idem = key()
    status, h, r1 = post(R, {"from_file_id": S1, "to_file_id": S2}, idem)
    check(status == 201 and r1["id"].startswith("rel_") and r1["type"] == "related" and r1["note"] is None
          and r1["created_by"] == "user" and r1["from_file_id"] == S1 and r1["to_file_id"] == S2,
          "relation created with default type related")
    status, h, again = post(R, {"from_file_id": S1, "to_file_id": S2}, idem)
    check(status == 201 and h.get("Idempotent-Replayed") == "true" and again == r1, "same key replays the relation")
    status, _, dup = post(R, {"from_file_id": S1, "to_file_id": S2, "type": "related", "note": "changed"})
    check(status == 200 and dup == r1, "existing triple -> 200 unchanged (note kept)")
    _, _, r2 = post(R, {"from_file_id": S1, "to_file_id": S2, "type": "references", "note": "SIMULATED note"})
    _, _, r3 = post(R, {"from_file_id": S2, "to_file_id": S3, "type": "follows-up"})
    _, _, r4 = post(R, {"from_file_id": S2, "to_file_id": S1})
    check(r2["note"] == "SIMULATED note" and r3["type"] == "follows-up" and r4["id"] != r1["id"],
          "different type or direction creates distinct relations")

    bad = [{"from_file_id": S1, "to_file_id": S1}, {"from_file_id": S1, "to_file_id": S2, "type": "Bad_Type"},
           {"from_file_id": S1, "to_file_id": S2, "type": 5}, {"from_file_id": S1, "to_file_id": S2, "type": ["x"]},
           {"from_file_id": S1, "to_file_id": S2, "type": ""}, {"from_file_id": S1, "to_file_id": S2, "note": 5},
           {"from_file_id": S1, "to_file_id": S2, "note": "x" * 1001}, {"to_file_id": S2},
           {"from_file_id": [S1], "to_file_id": S2}, {"from_file_id": S1, "to_file_id": {"a": 1}},
           {"from_file_id": S1, "to_file_id": S2, "extra": 1}]
    bad += [{"from_file_id": S1, "to_file_id": S2, "type": t} for t in RESERVED]
    results = [post(R, b) for b in bad]
    check(all(s == 422 and code(b) == "VALIDATION_FAILED" for s, _, b in results),
          f"{len(bad)} malformed relations (self-loop, reserved/invalid types, note, types) -> 422")
    b_file = all_pages(f"/projects/{B}/files")[0]["id"]
    status, _, body = post(R, {"from_file_id": S1, "to_file_id": b_file})
    check(status == 422 and code(body) == "INVALID_REFERENCE"
          and body["error"]["details"]["field_errors"][0]["path"] == "/to_file_id", "cross-project file -> 422")
    check(code(post(R, {"from_file_id": "fil_" + "0" * 32, "to_file_id": S2})[2]) == "INVALID_REFERENCE",
          "unknown file -> 422 INVALID_REFERENCE")

    print("8. Relation listing")
    q = lambda query: ids(all_pages(f"{R}?{query}"))  # noqa: E731
    check(q(f"file_id={S1}&direction=out") == {r1["id"], r2["id"]}, "direction=out")
    check(q(f"file_id={S2}&direction=in") == {r1["id"], r2["id"]}, "direction=in")
    check(q(f"file_id={S2}") == {r1["id"], r2["id"], r3["id"], r4["id"]}, "default direction=both")
    check(q(f"file_id={S2}&direction=out") == {r3["id"], r4["id"]}, "direction=out from the other end")
    check(q("type=references") == {r2["id"]} and q("created_by=user") == {r1["id"], r2["id"], r3["id"], r4["id"]}
          and q("created_by=system") == set(), "type and created_by filters")
    check(q(f"file_id={S1}&type=related&direction=in") == {r4["id"]}, "combined filters")
    errors = ["direction=out", "file_id=x&direction=sideways", "created_by=bot", "type=Bad_Type", "limit=0"]
    check(all(api("GET", f"{R}?{e}")[0] == 400 for e in errors), "unsupported relation query values -> 400")
    full = all_pages(f"{R}?file_id={S2}")
    check([r["id"] for r in all_pages(f"{R}?file_id={S2}", limit=1)] == [r["id"] for r in full]
          and full == sorted(full, key=lambda r: (r["created_at"], r["id"])), "relation paging is stable and ordered")
    _, _, page = api("GET", f"{R}?file_id={S2}&limit=1")
    cur = urllib.parse.quote(page["next_cursor"])
    check(code(api("GET", f"{R}?cursor={cur}&type=references")[2]) == "INVALID_QUERY"
          and api("GET", f"{R}?cursor={cur}&file_id={S2}")[0] == 200, "cursor with different filters -> 400")
    forged = [{"v": 1, "t": "collections", "p": A, "f": {}, "c": "x", "i": "y"},
              {"v": 1, "t": "relations", "p": B, "f": {}, "c": "x", "i": "y"},
              {"v": 1, "t": "relations", "p": A, "f": "x", "c": "x", "i": "y"},
              {"v": 1, "t": "relations", "p": A, "f": {"direction": "out"}, "c": "x", "i": "y"},
              {"v": 1, "t": "relations", "p": A, "f": {"type": ["x"]}, "c": "x", "i": "y"},
              {"v": 1, "t": "relations", "p": A, "f": {}, "c": 5, "i": "y"}, ["list"]]
    check(all(code(api("GET", f"{R}?cursor={forge_cursor(s)}")[2]) == "INVALID_CURSOR" for s in forged),
          "forged relation cursors -> 400 INVALID_CURSOR")

    print("9. Relation deletion")
    check(api("DELETE", f"{R}/{r3['id']}")[0] == 204 and api("DELETE", f"{R}/{r3['id']}")[0] == 404,
          "DELETE relation -> 204, repeat -> 404")
    check(api("DELETE", f"{R}/rel_{'0' * 32}")[0] == 404, "unknown relation -> 404")
    _, _, rb = post(f"/projects/{B}/relations", {"from_file_id": b_file,
                                                 "to_file_id": all_pages(f"/projects/{B}/files")[1]["id"]})
    check(api("DELETE", f"{R}/{rb['id']}")[0] == 404, "another project's relation -> 404")
    return r1, rb


# -- events, no-ops, archive, limits --------------------------------------------------------

def events_and_noops(A, files, r1):
    S1, S2, S3, CSV = files
    C = f"/projects/{A}/collections"
    print("10. Events and no-op operations")
    start = event_cursor(A)
    status, _, E = post(C, {"name": "Event check"})
    post(f"{C}/{E['id']}/files", {"file_ids": [S1]})
    _, _, rel = post(f"/projects/{A}/relations", {"from_file_id": S3, "to_file_id": S1, "type": "questions"})
    changes = catalog_changes(A, start)
    check({"entity": "collection", "id": E["id"], "revision": 1, "deleted": False} in changes
          and any(c["entity"] == "file" and c["id"] == S1 for c in changes)
          and {"entity": "relation", "id": rel["id"], "revision": None, "deleted": False} in changes,
          "collection, membership, and relation mutations emit catalog.changed")

    idem = key()
    post(f"{C}/{E['id']}/files", {"file_ids": [S2]}, idem)
    rev = {f: get_file(A, f)["revision"] for f in (S1, S2, S3)}
    cursor = event_cursor(A)
    post(f"{C}/{E['id']}/files", {"file_ids": [S1, S2]})                       # already members
    post(f"{C}/{E['id']}/files", {"file_ids": [S2]}, idem)                     # idempotent replay
    api("DELETE", f"{C}/{E['id']}/files/{S3}")                                 # not a member
    api("PATCH", f"{C}/{E['id']}", {"name": "Event check"}, {"If-Match": '"1"'})  # equal values
    post(f"/projects/{A}/relations", {"from_file_id": S1, "to_file_id": S2})   # existing triple
    api("GET", f"/projects/{A}/catalog")
    check(event_cursor(A) == cursor and {f: get_file(A, f)["revision"] for f in (S1, S2, S3)} == rev,
          "no-op membership, PATCH, relation, and replay emit no event and bump no revision")
    _ = r1


def archive_checks(B, EB, rb):
    print("11. Archived project")
    files = all_pages(f"/projects/{B}/files")
    fid = files[0]["id"]
    post(f"/projects/{B}/collections/{EB['id']}/files", {"file_ids": [fid]})
    set_project_status(B, "archived")
    try:
        C = f"/projects/{B}/collections"
        attempts = [
            post(C, {"name": "x"}),
            api("PATCH", f"{C}/{EB['id']}", {"name": "y"}, {"If-Match": '"1"'}),
            api("DELETE", f"{C}/{EB['id']}", headers={"If-Match": '"1"'}),
            post(f"{C}/{EB['id']}/files", {"file_ids": [files[1]["id"]]}),
            api("DELETE", f"{C}/{EB['id']}/files/{fid}"),
            post(f"/projects/{B}/relations", {"from_file_id": files[1]["id"], "to_file_id": fid}),
            api("DELETE", f"/projects/{B}/relations/{rb['id']}"),
        ]
        check(all(s == 409 and code(b) == "PROJECT_ARCHIVED" for s, _, b in attempts),
              "every collection/relation mutation on an archived project -> 409 PROJECT_ARCHIVED")
        check(api("GET", C)[0] == 200 and api("GET", f"/projects/{B}/relations")[0] == 200
              and fid in files_of(B, f"collection_id={EB['id']}"), "archived project stays readable and unchanged")
    finally:
        set_project_status(B, "active")


def limit_checks(run):
    print("12. Collection limit (200 per project)")
    L = project(f"WC limits {run} (SIMULATED)")
    for i in range(200):
        status, _, body = post(f"/projects/{L}/collections", {"name": f"c{i}"})
        assert status == 201, body
    status, _, body = post(f"/projects/{L}/collections", {"name": "one too many"})
    check(status == 422 and code(body) == "VALIDATION_FAILED", "the 201st collection -> 422")


# -- system relations -----------------------------------------------------------------------

def system_relations(run):
    print("13. System relations from recorded provenance (SIMULATED analysis + report)")
    S = project(f"WC system {run} (SIMULATED)")
    data = upload(S, b"t_s,height_px\n0.0,100\n0.5,64\n1.0,41\n", "SIMULATED-heights.csv", "text/csv", "dataset",
                  "simulated")
    script = upload(S, PY_FIXTURE.encode(), "SIMULATED_summary.py", "text/x-python", "code", "generated")
    status, _, exp = post(f"/projects/{S}/experiments", {
        "title": "Synthetic relation check", "hypothesis": "SIMULATED fixture hypothesis.", "method": "computational",
        "protocol_markdown": "Synthetic protocol.", "variables": [], "success_criteria": [],
        "input_artifact_ids": [data["id"]], "calibration": {"mode": "none", "assumptions": []},
        "limitations": ["All inputs are simulated."]})
    assert status == 201, exp
    _, _, queued = post(f"/projects/{S}/runs", {
        "kind": "analysis", "experiment_id": exp["id"], "experiment_revision": 1, "input_artifact_ids": [data["id"]],
        "pipeline": "python_analysis_v1", "code_artifact_id": script["id"], "parameters": {}})
    analysis = wait_run(S, queued["id"])
    check(analysis["status"] == "succeeded", f"SIMULATED analysis run succeeded ({analysis['error']})")
    status, _, rq = post(f"/projects/{S}/runs", {"kind": "report", "experiment_id": exp["id"],
                                                 "evidence_run_ids": [analysis["id"]], "source_ids": [],
                                                 "title": "SIMULATED relation report", "format": "markdown"})
    if status == 202 or status == 201:
        wait_run(S, rq["id"])
    else:
        print(f"  --  report run not accepted ({status}); report edges not exercised")

    # Independent oracle from the legacy API: exactly the recorded provenance, nothing else.
    files = all_pages(f"/projects/{S}/files?status=all")
    fid = {(f["origin"]["type"], f["origin"]["id"]): f["id"] for f in files if f["origin"]}
    runs = {r["id"]: r for r in all_pages(f"/projects/{S}/runs")}
    measurement_run = {}
    for rid, r in runs.items():
        if r["status"] in TERMINAL and r["input"]["kind"] == "analysis":
            for m in all_pages(f"/projects/{S}/runs/{rid}/measurements"):
                measurement_run[m["id"]] = rid
    expected = set()
    for a in all_pages(f"/projects/{S}/artifacts"):
        for parent in a["parent_artifact_ids"]:
            expected.add((fid[("artifact", a["id"])], fid[("artifact", parent)], "derived_from"))
        if a["run_id"] and runs[a["run_id"]]["status"] in TERMINAL:
            expected.add((fid[("artifact", a["id"])], fid[("run", a["run_id"])], "produced_by"))
    for rid in set(measurement_run.values()):
        expected.add((fid[("run_measurements", rid)], fid[("run", rid)], "produced_by"))
    claims = all_pages(f"/projects/{S}/claims")
    for c in claims:
        for cit in c["citations"]:
            expected.add((fid[("claim", c["id"])], fid[("source", cit["source_id"])], "cites"))
        for ev in c["evidence"]:
            expected.add((fid[("claim", c["id"])], fid[("artifact", ev["artifact_id"])], "uses_evidence"))
        for mid in c["measurement_ids"]:
            expected.add((fid[("claim", c["id"])], fid[("run_measurements", measurement_run[mid])], "uses_evidence"))
    system = all_pages(f"/projects/{S}/relations?created_by=system")
    actual = {(r["from_file_id"], r["to_file_id"], r["type"]) for r in system}
    check(claims and any(t == "uses_evidence" for _, _, t in expected) and any(t == "derived_from" for _, _, t in expected),
          f"fixture records claim evidence and artifact parents ({len(expected)} expected edges)")
    check(actual == expected and len(system) == len(actual),
          "system relations equal recorded provenance exactly (no invented or duplicate edges)")
    check(all(r["created_by"] == "system" and r["note"] is None and r["id"].startswith("rel_") for r in system),
          "system relations are read-only provenance records")
    status, _, body = api("DELETE", f"/projects/{S}/relations/{system[0]['id']}")
    check(status == 409 and code(body) == "RELATION_PROTECTED", "deleting a system relation -> 409 RELATION_PROTECTED")
    a, b_, t = sorted(actual)[0]
    status, _, body = post(f"/projects/{S}/relations", {"from_file_id": a, "to_file_id": b_, "type": t})
    check(status == 422, "users cannot forge a system relation type")
    source(S, "Resync trigger (SIMULATED)")
    again = all_pages(f"/projects/{S}/relations?created_by=system")
    check(sorted(r["id"] for r in again) == sorted(r["id"] for r in system), "re-projection keeps relation IDs, no duplicates")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-limits", action="store_true", help="skip creating 200 collections")
    parser.add_argument("--skip-system", action="store_true", help="skip the worker-backed system relation checks")
    args = parser.parse_args()
    run = uuid.uuid4().hex[:8]
    print("1. Fixture projects (all data SIMULATED)")
    A = project(f"WC A {run} (SIMULATED)")
    B = project(f"WC B {run} (SIMULATED)")
    s1, s2, s3 = (source(A, t) for t in ("Alpha one (SIMULATED)", "Alpha two (SIMULATED)", "Beta (SIMULATED)"))
    csv_art = upload(A, b"t_s,height_px\n0.0,100\n", "SIMULATED-heights.csv", "text/csv", "dataset", "simulated")
    source(B, "B one (SIMULATED)")
    source(B, "B two (SIMULATED)")
    files = tuple(file_for(A, "source", s["id"])["id"] for s in (s1, s2, s3)) + (file_for(A, "artifact", csv_art["id"])["id"],)
    notes = []
    status, _, note = post(f"/projects/{A}/files", {"name": "alpha-note.md", "content": "SIMULATED note\n"})
    if status == 201:
        notes.append(note["id"])
    else:
        print(f"  --  notes route unavailable ({status}); trashed-note checks skipped")
    check(len(set(files)) == 4, "fixture files projected")

    EB = collections(A, B, files, notes)
    r1, rb = relations(A, B, files)
    events_and_noops(A, files, r1)
    archive_checks(B, EB, rb)
    if not args.skip_limits:
        limit_checks(run)
    workers = "isolated_python" in api("GET", "/capabilities")[2]["execution"]["allowed_backends"]
    if args.skip_system:
        print("  --  system relation checks skipped (--skip-system)")
    elif not workers:
        print("  --  worker unavailable: system relation checks skipped")
    else:
        system_relations(run)
    print(f"\nPASSED {len(PASSED)} checks")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"\nFAILED after {len(PASSED)} checks: {exc}")
        sys.exit(1)
