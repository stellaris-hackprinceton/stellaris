#!/usr/bin/env python3
"""Docker integration checks for the workspace file catalog (docs/file-workspace-contract.md).

Run from backend/ (stdlib only) after rebuilding and `docker compose up -d --wait`:

    python3 scripts/workspace_files_test.py --slice 1
    python3 scripts/workspace_files_test.py --slice 1 --skip-rebuild --skip-existing
    python3 scripts/workspace_files_test.py --slice 2

Slice 1 covers lazy backfill, deterministic IDs and hashes, artifact/record content, default
tags, listing filters/sorts/cursors, project scoping, and unchanged legacy routes.
Slice 2 covers notes and revisions, idempotency, validation (Unicode, NUL, limits), ETags and
no-ops, user tags and bulk tagging with rollback, tag CRUD, events, immutability of original
evidence, project scope, and archived-project rejection. It runs no analysis workers.

All fixture data is synthetic: uploads use origin "simulated" and SIMULATED names, and the
optional analysis run computes a mean over a generated CSV (no observed measurements). No
model or provider is called. Creates new projects and containers, which are retained.
--skip-rebuild skips deleting and rebuilding the test project's own catalog file inside the
api container. --skip-existing skips the read-only backfill check of one pre-existing
project. Does not read any .env file.
"""

import argparse
import base64
import csv
import hashlib
import http.client
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("STELLARIS_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
CATALOG_DIR = os.environ.get("STELLARIS_TEST_CATALOG_DIR", "/data/catalogs")
_PARSED = urllib.parse.urlsplit(BASE)
PASSED = []
TERMINAL = ("succeeded", "failed", "cancelled")
SYSTEM_TAGS = {"research", "hypotheses", "experiments", "results", "artifacts", "reports", "agent-logs", "run-logs",
               "provenance", "notes", "documents", "datasets", "images", "videos", "audio", "code", "charts"}
CSV_COLUMNS = ["id", "series", "quantity", "value", "unit", "time_s", "uncertainty_absolute", "uncertainty_method",
               "status", "calibration_mode", "data_origin", "assumptions_json", "evidence_json"]

# Synthetic analysis for python_analysis_v1: the mean of a generated column. Not a real analysis.
PY_FIXTURE = r'''
import json
manifest = json.load(open("/input/manifest.json"))
data = next(a for a in manifest["inputs"] if a["kind"] == "dataset")
lines = open(data["path"], encoding="utf-8").read().splitlines()[1:]
values = [float(line.split(",")[1]) for line in lines if line]
measurement = {
    "local_key": "mean", "series": "summary", "quantity": "mean_height", "value": sum(values) / len(values),
    "unit": "px", "time_s": None, "uncertainty": {"absolute": None, "method": None}, "status": "valid",
    "evidence": [{"artifact": {"input_artifact_id": data["artifact_id"]}, "frame_index": None, "time_s": None,
                  "row_index": 0}],
    "calibration_mode": manifest["calibration"]["mode"], "data_origin": "derived",
    "assumptions": ["SIMULATED fixture: arithmetic mean of a generated column."]}
json.dump({"measurements": [measurement], "claims": [], "artifacts": [], "warnings": []},
          open("/output/result.json", "w"))
print("done", flush=True)
'''


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    PASSED.append(message)
    print(f"  ok  {message}")


def key():
    return f"wf-{uuid.uuid4().hex}"


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


def post(path, body):
    return api("POST", path, body, {"Idempotency-Key": key()})


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


def forge_cursor(state):
    return base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode().rstrip("=")


def docker(*args, check_rc=True):
    result = subprocess.run(["docker", *args], capture_output=True, cwd=BACKEND_DIR)
    if check_rc and result.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()}")
    return result


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


def read_events(pid, after, wanted, timeout=15):
    """Replay persisted events after a cursor until one of type `wanted` arrives (or timeout)."""
    conn = http.client.HTTPConnection(_PARSED.hostname, _PARSED.port or 80, timeout=timeout)
    found, deadline = [], time.monotonic() + timeout
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
                if current.get("event") == wanted:
                    found.append(json.loads(current["data"]))
                    break
                current = {}
            elif not text.startswith(":"):
                name, _, value = text.partition(":")
                current[name] = value[1:] if value.startswith(" ") else value
    except (OSError, http.client.HTTPException):
        pass
    finally:
        conn.close()
    return found


def content(pid, file_id, headers=None, query=""):
    return raw("GET", f"/projects/{pid}/files/{file_id}/content{query}", headers=headers)


def legacy_counts(pid):
    runs = all_pages(f"/projects/{pid}/runs")
    terminal = [r for r in runs if r["status"] in TERMINAL]
    with_measurements = [r for r in terminal if r["input"]["kind"] == "analysis"
                         and api("GET", f"/projects/{pid}/runs/{r['id']}/results")[2]["measurement_count"] > 0]
    return {
        "artifact": len(all_pages(f"/projects/{pid}/artifacts")), "source": len(all_pages(f"/projects/{pid}/sources")),
        "claim": len(all_pages(f"/projects/{pid}/claims")), "experiment": len(all_pages(f"/projects/{pid}/experiments")),
        "run": len(terminal), "run_measurements": len(with_measurements),
    }


def by_origin(files):
    return {(f["origin"]["type"], f["origin"]["id"]): f for f in files if f["origin"]}


# -- slice 1 ------------------------------------------------------------------------------

def slice1(args):
    run = uuid.uuid4().hex[:8]
    print("1. Capability and fixture projects (all data SIMULATED)")
    status, _, caps = api("GET", "/capabilities")
    check(status == 200 and caps["features"].get("workspace_files") is True, "capabilities advertise workspace_files")
    workers = "isolated_python" in caps["execution"]["allowed_backends"]
    _, _, a = post("/projects", {"name": f"WF A {run} (SIMULATED)"})
    _, _, b = post("/projects", {"name": f"WF B {run} (SIMULATED)"})
    A, B = a["id"], b["id"]
    _, _, ws0 = api("GET", f"/projects/{A}/workspace")
    cursor0 = ws0["event_cursor"]

    # Legacy records created BEFORE any catalog access: the first catalog request backfills them.
    _, _, src = post(f"/projects/{A}/sources", {"title": "Synthetic reference / test (SIMULATED)",
                                                "url": "https://example.org/simulated-reference"})
    csv_bytes = b"t_s,height_px\n0.0,100\n0.5,64\n1.0,41\n"
    csv_art = upload(A, csv_bytes, "SIMULATED-heights.csv", "text/csv", "dataset", "simulated")
    exp_body = {"title": "Synthetic bounce check", "hypothesis": "SIMULATED fixture hypothesis.", "method": "computational",
                "protocol_markdown": "Synthetic protocol for catalog tests.", "variables": [], "success_criteria": [],
                "input_artifact_ids": [csv_art["id"]], "calibration": {"mode": "none", "assumptions": []},
                "limitations": ["All inputs are simulated."]}
    status, _, exp = post(f"/projects/{A}/experiments", exp_body)
    check(status == 201, "fixture source, simulated CSV artifact, and experiment created")
    analysis_run = None
    if workers:
        script = upload(A, PY_FIXTURE.encode(), "SIMULATED_mean.py", "text/x-python", "code", "generated")
        status, _, exp2 = post(f"/projects/{A}/experiments", {**exp_body, "title": "Synthetic mean run"})
        status, _, queued = post(f"/projects/{A}/runs", {
            "kind": "analysis", "experiment_id": exp2["id"], "experiment_revision": 1,
            "input_artifact_ids": [csv_art["id"]], "pipeline": "python_analysis_v1",
            "code_artifact_id": script["id"], "parameters": {}})
        analysis_run = wait_run(A, queued["id"])
        check(analysis_run["status"] == "succeeded", f"synthetic analysis run succeeded ({analysis_run['error']})")
    else:
        print("  --  worker unavailable: measurement/run projection checks skipped")
    legacy_artifacts_before = all_pages(f"/projects/{A}/artifacts")
    _, _, ws_before = api("GET", f"/projects/{A}/workspace")

    print("2. Lazy backfill")
    status, _, cat = api("GET", f"/projects/{A}/catalog")
    expected = legacy_counts(A)
    check(status == 200 and cat["workspace_files"] is True and cat["schema_version"] == 2
          and cat["last_sync_error"] is None and cat["last_synced_at"], "GET /catalog returns CatalogStatus")
    check(cat["projected"] == expected, f"projected counts equal legacy counts {expected}")
    check(cat["notes"] == {"count": 0, "retained_bytes": 0, "max_bytes": cat["notes"]["max_bytes"]}
          and cat["notes"]["max_bytes"] > 0, "no notes exist before slice 2")
    files = all_pages(f"/projects/{A}/files")
    check(len(files) == sum(expected.values()) and len({f["id"] for f in files}) == len(files),
          "every projected record appears exactly once in /files")
    check(len(by_origin(files)) == len(files), "each origin maps to exactly one file")
    origin = by_origin(files)
    src_file, csv_file = origin[("source", src["id"])], origin[("artifact", csv_art["id"])]
    exp_file = origin[("experiment", exp["id"])]
    check(src_file["created_at"] == src["created_at"] and csv_file["created_at"] == csv_art["created_at"],
          "projected files keep their legacy created_at")
    check(all(f["id"].startswith("fil_") and len(f["id"]) == 36 and f["status"] == "active"
              and f["editable"] == {"name": False, "content": False, "tags": True} and f["content_revision"] is None
              for f in files), "projected files are read-only, active, and have opaque fil_ IDs")
    events = read_events(A, cursor0, "catalog.changed")
    check(events and events[0]["payload"]["changes"], "backfill emitted a catalog.changed event")
    first = api("GET", f"/projects/{A}/catalog")[2]
    second = api("GET", f"/projects/{A}/catalog")[2]
    check(cat["last_synced_at"] == first["last_synced_at"] == second["last_synced_at"],
          "relayed catalog events do not trigger another projection pass")

    print("3. Stable identities and default tags")
    again = all_pages(f"/projects/{A}/files")
    check([(f["id"], f["content_sha256"], f["revision"]) for f in again]
          == [(f["id"], f["content_sha256"], f["revision"]) for f in files], "re-sync keeps IDs, hashes, revisions")
    tags = all_pages(f"/projects/{A}/tags?system=true")
    check({t["slug"] for t in tags} == SYSTEM_TAGS and all(t["system"] for t in tags), "all default tags exist")
    check(all_pages(f"/projects/{A}/tags?system=false") == [], "no user tags exist")
    status, h, tag = api("GET", f"/projects/{A}/tags/datasets")
    check(status == 200 and h.get("ETag") == f'"{tag["revision"]}"' and tag["file_count"] >= 1,
          "GET /tags/{slug} returns ETag and file_count")
    check(api("GET", f"/projects/{A}/tags/no-such-tag")[0] == 404, "unknown tag returns 404")
    slugs = lambda f: {t["slug"] for t in f["tags"] if t["assigned_by"] == "system"}
    check(slugs(src_file) == {"research"} and slugs(csv_file) == {"artifacts", "datasets"}
          and slugs(exp_file) == {"experiments"}, "system tags follow the legacy category")
    check(src_file["scientific_origin"] == "reference" and csv_file["scientific_origin"] == "simulated"
          and exp_file["scientific_origin"] is None, "scientific_origin follows the legacy record")
    check(src_file["name"] == "Synthetic reference _ test (SIMULATED).source.json", "record names contain no path separators")

    print("4. Content")
    status, h, body = content(A, csv_file["id"])
    check(status == 200 and body == csv_bytes and h.get("ETag") == f'"{csv_art["sha256"]}"'
          and csv_file["content_sha256"] == csv_art["sha256"], "artifact file streams the original bytes")
    status, h, part = content(A, csv_file["id"], {"Range": "bytes=0-3"})
    check(status == 206 and part == csv_bytes[:4] and h.get("Content-Range") == f"bytes 0-3/{len(csv_bytes)}",
          "artifact file supports byte ranges")
    status, h, body = content(A, src_file["id"])
    record = json.loads(body)
    check(status == 200 and hashlib.sha256(body).hexdigest() == src_file["content_sha256"] == h.get("ETag").strip('"')
          and len(body) == src_file["size_bytes"] and body.endswith(b"\n"), "record bytes match metadata hash and size")
    check(record["schema"] == "stellaris.record.v1" and record["record_type"] == "source" and record["id"] == src["id"]
          and record["revision"] is None and record["api_path"] == f"/api/v1/projects/{A}/sources/{src['id']}"
          and record["data"] == api("GET", f"/projects/{A}/sources/{src['id']}")[2], "record JSON envelope wraps the legacy body")
    check("attachment" in h.get("Content-Disposition", "") and h.get("X-Content-Type-Options") == "nosniff",
          "record download is an attachment with nosniff")
    check(code(json.loads(content(A, src_file["id"], query="?disposition=inline")[2])) == "INVALID_QUERY",
          "JSON records cannot be served inline")
    check(content(A, src_file["id"], query="?revision=1")[0] == 400, "?revision on a non-note returns 400")

    print("5. Experiment revisions re-project")
    status, _, exp_v2 = api("PATCH", f"/projects/{A}/experiments/{exp['id']}", {"title": "Synthetic bounce check v2"},
                            {"If-Match": '"1"'})
    status, h, exp_file2 = api("GET", f"/projects/{A}/files/{exp_file['id']}")
    check(status == 200 and exp_file2["origin"]["revision"] == 2 and exp_file2["revision"] == exp_file["revision"] + 1
          and exp_file2["content_sha256"] != exp_file["content_sha256"]
          and exp_file2["name"] == "Synthetic bounce check v2.experiment.json"
          and h.get("ETag") == f'"{exp_file2["revision"]}"', "experiment PATCH updates the same file on next read")
    body = content(A, exp_file["id"])[2]
    check(json.loads(body)["revision"] == 2 and json.loads(body)["data"] == exp_v2
          and hashlib.sha256(body).hexdigest() == exp_file2["content_sha256"], "experiment record renders the new revision")

    if analysis_run:
        print("6. Runs and simulated measurements")
        run_file = origin[("run", analysis_run["id"])]
        m_file = origin[("run_measurements", analysis_run["id"])]
        body = content(A, run_file["id"])[2]
        doc = json.loads(body)
        check(doc["data"]["run"] == api("GET", f"/projects/{A}/runs/{analysis_run['id']}")[2]
              and doc["data"]["results"] == api("GET", f"/projects/{A}/runs/{analysis_run['id']}/results")[2],
              "run record contains the terminal Run and RunResults")
        status, h, body = content(A, m_file["id"])
        rows = list(csv.reader(io.StringIO(body.decode("utf-8"), newline="")))
        legacy = all_pages(f"/projects/{A}/runs/{analysis_run['id']}/measurements")
        check(rows[0] == CSV_COLUMNS and len(rows) == 1 + len(legacy) and b"\r\n" in body,
              "measurements CSV has the contract columns and one row per measurement")
        check(all(r[10] == "simulated" for r in rows[1:]) and m_file["scientific_origin"] == "simulated"
              and slugs(m_file) == {"results"} and m_file["mime_type"] == "text/csv",
              "simulated measurements stay labelled simulated")
        logs = [f for f in files if f["origin"]["type"] == "artifact" and f["mime_type"] == "text/plain"
                and f["name"] == "run-log.txt"]
        check(logs and all("run-logs" in slugs(f) for f in logs), "analysis run logs carry the run-logs tag")

    print("7. Listing filters, sorting, cursors")
    files = all_pages(f"/projects/{A}/files")  # Current names after the experiment rename.
    page1 = api("GET", f"/projects/{A}/files?limit=1")[2]
    paged, cursor = page1["items"], page1["next_cursor"]
    while cursor:
        page = api("GET", f"/projects/{A}/files?limit=1&cursor={urllib.parse.quote(cursor)}")[2]
        paged += page["items"]
        cursor = page["next_cursor"]
    check([f["id"] for f in paged] == [f["id"] for f in files], "limit=1 paging visits every file once in order")
    check([f["id"] for f in files] == [f["id"] for f in sorted(files, key=lambda f: (f["created_at"], f["id"]))],
          "default order is ascending (created_at, id)")
    by_name = all_pages(f"/projects/{A}/files?sort=name&order=desc", limit=2)
    check([f["id"] for f in by_name] == [f["id"] for f in sorted(files, key=lambda f: (f["name"].casefold(), f["id"]),
                                                                  reverse=True)], "sort=name&order=desc pages correctly")
    tagged = all_pages(f"/projects/{A}/files?tag=artifacts&tag=datasets")
    check(csv_file["id"] in {f["id"] for f in tagged} and all({"artifacts", "datasets"} <= slugs(f) for f in tagged),
          "repeated tag filters use AND")
    check(all_pages(f"/projects/{A}/files?tag=artifacts&tag=research") == [], "disjoint tags match nothing")
    check(all_pages(f"/projects/{A}/files?tag=unknown-tag") == [], "unknown tag slug matches nothing")
    check({f["id"] for f in all_pages(f"/projects/{A}/files?origin_type=source")} == {src_file["id"]}, "origin_type filter")
    check(all(f["file_kind"] == "record" for f in all_pages(f"/projects/{A}/files?file_kind=record")), "file_kind filter")
    check(all_pages(f"/projects/{A}/files?file_kind=note") == [], "no notes are listed in slice 1")
    check({f["id"] for f in all_pages(f"/projects/{A}/files?q=SIMULATED-HEIGHTS")} == {csv_file["id"]},
          "q is a case-insensitive name substring")
    check(all_pages(f"/projects/{A}/files?q=%25") == [], "q treats % literally")
    check(len(all_pages(f"/projects/{A}/files?status=all")) == len(files)
          and all_pages(f"/projects/{A}/files?status=trashed") == [], "status filter")
    first_page = api("GET", f"/projects/{A}/files?limit=1&file_kind=record")[2]
    c = urllib.parse.quote(first_page["next_cursor"])
    bad = [
        ("tag=Bad Tag", "INVALID_QUERY"), ("file_kind=folder", "INVALID_QUERY"), ("status=deleted", "INVALID_QUERY"),
        ("sort=size", "INVALID_QUERY"), ("order=up", "INVALID_QUERY"), ("q=", "INVALID_QUERY"),
        ("limit=0", "INVALID_QUERY"), ("cursor=!!!", "INVALID_CURSOR"),
        (f"cursor={c}&file_kind=artifact", "INVALID_QUERY"), (f"cursor={c}&sort=name", "INVALID_QUERY"),
        (f"cursor={forge_cursor({'v': 1, 't': 'files', 'p': A, 's': 'bogus', 'o': 'asc', 'f': {}, 'k': '', 'i': ''})}",
         "INVALID_CURSOR"),
        (f"cursor={forge_cursor({'v': 1, 't': 'files', 'p': A, 's': 'name', 'o': 'asc', 'f': {'status': 'gone'}, 'k': '', 'i': ''})}",
         "INVALID_CURSOR"),
        (f"cursor={forge_cursor({'v': 1, 't': 'files', 'p': B, 's': 'name', 'o': 'asc', 'f': {}, 'k': '', 'i': ''})}",
         "INVALID_CURSOR"),
    ]
    for invalid in ([{}], ["research", 7], [["research"]]):
        bad.append((f"cursor={forge_cursor({'v': 1, 't': 'files', 'p': A, 's': 'name', 'o': 'asc', 'f': {'tag': invalid}, 'k': '', 'i': ''})}", "INVALID_CURSOR"))
    for query, expected_code in bad:
        status, _, err = api("GET", f"/projects/{A}/files?{query.replace(' ', '%20')}")
        check(status == 400 and code(err) == expected_code, f"/files?{query[:40]} returns 400 {expected_code}")
    tag_cursor = api("GET", f"/projects/{A}/tags?limit=1")[2]["next_cursor"]
    status, _, err = api("GET", f"/projects/{A}/files?cursor={urllib.parse.quote(tag_cursor)}")
    check(status == 400 and code(err) == "INVALID_CURSOR", "a /tags cursor is rejected by /files")
    status, _, err = api("GET", f"/projects/{A}/tags?system=maybe")
    check(status == 400 and code(err) == "INVALID_QUERY", "unsupported tag filter returns 400")
    check(len(all_pages(f"/projects/{A}/tags", limit=3)) == len(SYSTEM_TAGS), "tag paging visits every tag")
    status, _, err = api("GET", f"/projects/{A}/files?collection_id=col_{'0' * 32}")
    check(status == 404 and code(err) == "RESOURCE_NOT_FOUND", "unknown collection returns 404")

    print("8. Project scope and unavailable mutations")
    api("GET", f"/projects/{B}/catalog")
    for path in (f"/projects/{B}/files/{csv_file['id']}", f"/projects/{B}/files/{csv_file['id']}/content",
                 f"/projects/prj_{'0' * 32}/files", f"/projects/prj_{'0' * 32}/catalog", f"/projects/../catalog"):
        status, _, err = api("GET", path)
        check(status == 404, f"GET {path.replace(A, 'A').replace(B, 'B')[:60]} returns 404")
    check(all_pages(f"/projects/{B}/files") == [], "project B sees none of project A's files")
    # Notes exist since slice 2; an invalid body must still create nothing.
    status, _, err = post(f"/projects/{A}/files", {"name": "note.md", "content": "x", "folder": "nope"})
    check(status == 422 and code(err) == "VALIDATION_FAILED"
          and all_pages(f"/projects/{A}/files?file_kind=note") == [], "an invalid note body creates nothing")

    print("9. Legacy routes unchanged")
    check(all_pages(f"/projects/{A}/artifacts") == legacy_artifacts_before, "legacy artifact list unchanged")
    _, _, ws_after = api("GET", f"/projects/{A}/workspace")
    check(ws_after["counts"] == ws_before["counts"] and set(ws_after["counts"]) == {"sources", "experiments", "runs", "artifacts"},
          "Workspace.counts unchanged and does not count catalog files")

    if not args.skip_rebuild:
        print("10. Rebuild from legacy records (test project A only)")
        snapshot = [(f["id"], f["content_sha256"], f["origin"]["type"], f["origin"]["id"])
                    for f in all_pages(f"/projects/{A}/files")]
        base = f"{CATALOG_DIR}/{A}.sqlite3"
        docker("compose", "exec", "-T", "api", "rm", "-f", base, f"{base}-wal", f"{base}-shm")
        rebuilt = [(f["id"], f["content_sha256"], f["origin"]["type"], f["origin"]["id"])
                   for f in all_pages(f"/projects/{A}/files")]
        check(rebuilt == snapshot, "a deleted catalog rebuilds identical file IDs and hashes")

    if not args.skip_existing:
        print("11. Backfill of one pre-existing project (read-only; creates only its catalog)")
        others = [p for p in all_pages("/projects") if p["id"] not in (A, B)]
        if not others:
            print("  --  no pre-existing project found")
        else:
            other = others[-1]["id"]  # Least recently updated listed project; discovered, not hardcoded.
            status, _, ocat = api("GET", f"/projects/{other}/catalog")
            check(status == 200 and ocat["last_sync_error"] is None and ocat["projected"] == legacy_counts(other),
                  "an existing project's projection matches its legacy counts")


# -- slice 2 ------------------------------------------------------------------------------

def catalog_events(pid, after, until, timeout=15):
    """catalog.changed payloads after `after`, read until until(payload) is true or timeout."""
    conn = http.client.HTTPConnection(_PARSED.hostname, _PARSED.port or 80, timeout=timeout)
    collected, deadline = [], time.monotonic() + timeout
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
                    payload = json.loads(current["data"])["payload"]
                    collected.append(payload)
                    if until(payload):
                        break
                current = {}
            elif not text.startswith(":"):
                name, _, value = text.partition(":")
                current[name] = value[1:] if value.startswith(" ") else value
    except (OSError, http.client.HTTPException):
        pass
    finally:
        conn.close()
    return collected


def event_cursor(pid):
    status, _, ws = api("GET", f"/projects/{pid}/workspace")
    assert status == 200, ws
    return ws["event_cursor"]


def changes_of(payloads):
    return [c for p in payloads for c in p["changes"]]


def raw_json(method, path, text, headers=None):
    """Send a hand-written JSON body (e.g. lone surrogate escapes json.dumps would not produce)."""
    status, _, payload = raw(method, path, text.encode("ascii"), {"Content-Type": "application/json", **(headers or {})})
    return status, json.loads(payload) if payload else None


def slice2(_args):
    run = uuid.uuid4().hex[:8]
    print("1. Fixtures (all SIMULATED)")
    s1, _, c = post("/projects", {"name": f"WF2 C {run} (SIMULATED)"})
    s2, _, d = post("/projects", {"name": f"WF2 D {run} (SIMULATED)"})
    check(s1 == 201 and s2 == 201, "created projects C and D")
    C, D = c["id"], d["id"]
    status, _, src = post(f"/projects/{C}/sources", {"title": "Synthetic reference (SIMULATED)",
                                                     "url": "https://example.org/simulated-reference"})
    check(status == 201, "fixture source created")
    csv_bytes = b"t_s,height_px\n0.0,100\n0.5,64\n"
    csv_art = upload(C, csv_bytes, "SIMULATED-heights.csv", "text/csv", "dataset", "simulated")
    origin = by_origin(all_pages(f"/projects/{C}/files"))
    src_file, csv_file = origin[("source", src["id"])], origin[("artifact", csv_art["id"])]
    legacy_art = api("GET", f"/projects/{C}/artifacts/{csv_art['id']}")[2]
    legacy_src = api("GET", f"/projects/{C}/sources/{src['id']}")[2]
    counts_before = api("GET", f"/projects/{C}/workspace")[2]["counts"]
    files_path = f"/projects/{C}/files"

    print("2. Create notes")
    body = {"name": "Lab notes.md", "content": "# Synthetic notes ünïcode ✓\n", "tags": ["todo", "hypotheses"]}
    data = body["content"].encode("utf-8")
    create_key = key()
    status, h, note = api("POST", files_path, body, {"Idempotency-Key": create_key})
    check(status == 201 and h.get("ETag") == '"1"' and h.get("Location", "").endswith(f"/files/{note['id']}"),
          "POST /files creates a note with ETag and Location")
    nid, npath = note["id"], f"{files_path}/{note['id']}"
    check(note["file_kind"] == "note" and note["origin"] is None and note["scientific_origin"] is None
          and note["revision"] == 1 and note["content_revision"] == 1 and note["status"] == "active"
          and note["editable"] == {"name": True, "content": True, "tags": True} and note["mime_type"] == "text/markdown"
          and note["size_bytes"] == len(data) and note["content_sha256"] == hashlib.sha256(data).hexdigest(),
          "new note has revision 1, content revision 1, and correct hash")
    check(note["tags"] == [{"slug": "hypotheses", "assigned_by": "user"}, {"slug": "notes", "assigned_by": "system"},
                           {"slug": "todo", "assigned_by": "user"}], "new note carries system notes plus user tags")
    status, h, again = api("POST", files_path, body, {"Idempotency-Key": create_key})
    check(status == 201 and again == note and h.get("Idempotent-Replayed") == "true", "note creation replays idempotently")
    status, _, err = api("POST", files_path, {**body, "content": "different"}, {"Idempotency-Key": create_key})
    check(status == 409 and code(err) == "IDEMPOTENCY_CONFLICT", "same key with another body returns 409")
    status, _, todo = api("GET", f"/projects/{C}/tags/todo")
    check(status == 200 and todo["system"] is False and todo["file_count"] == 1 and todo["revision"] == 1,
          "unknown user slugs are auto-created as user tags")
    status, h, got = content(C, nid)
    check(status == 200 and got == data and h.get("ETag") == f'"{note["content_sha256"]}"'
          and h.get_content_type() == "text/markdown" and "Lab notes.md" in h.get("Content-Disposition", ""),
          "note content downloads its exact bytes and name")
    status, _, empty = post(files_path, {"name": "empty.txt", "content": "", "mime_type": "text/plain"})
    check(status == 201 and empty["size_bytes"] == 0 and empty["mime_type"] == "text/plain", "empty notes are valid")
    status, _, big = post(files_path, {"name": "limit.txt", "content": "a" * 524288})
    check(status == 201 and big["size_bytes"] == 524288, "a 512 KiB note is accepted")
    invalid = [
        ({"name": "x.md"}, "missing content"), ({"name": "a/b.md", "content": "x"}, "a path-like name"),
        ({"name": " x.md", "content": "x"}, "a name with surrounding spaces"),
        ({"name": "x.md", "content": "a\u0000b"}, "a NUL character"),
        ({"name": "x.md", "content": "a" * 524289}, "content over 512 KiB"), ({"name": "x.md", "content": 5}, "non-string content"),
        ({"name": "x.md", "content": "x", "mime_type": "text/html"}, "an unsupported mime_type"),
        ({"name": "x.md", "content": "x", "tags": ["Bad"]}, "an invalid slug"),
        ({"name": "x.md", "content": "x", "tags": [1, ["x"]]}, "non-string tags"),
        ({"name": "x.md", "content": "x", "tags": ["a", "a"]}, "duplicate tags"),
        ({"name": "x.md", "content": "x", "tags": [f"t{i}" for i in range(33)]}, "33 user tags"),
        ({"name": "x.md", "content": "x", "folder": "y"}, "an unknown field"),
    ]
    for bad_body, label in invalid:
        status, _, err = post(files_path, bad_body)
        check(status == 422 and code(err) == "VALIDATION_FAILED", f"note with {label} returns 422")
    for text, label in (('{"name":"x.md","content":"\\ud800"}', "content"), ('{"name":"\\udfff.md","content":"x"}', "name")):
        status, err = raw_json("POST", files_path, text, {"Idempotency-Key": key()})
        check(status == 422 and code(err) == "VALIDATION_FAILED", f"an unpaired surrogate in the {label} returns 422")
    check(len(all_pages(f"{files_path}?file_kind=note")) == 3, "rejected requests created no notes")

    print("3. Revisions, ETags, and no-ops")
    status, _, err = api("PATCH", npath, {"content": "# v2\n"})
    check(status == 428 and code(err) == "PRECONDITION_REQUIRED", "PATCH without If-Match returns 428")
    status, _, err = api("PATCH", npath, {"content": "# v2\n"}, {"If-Match": '"7"'})
    check(status == 412 and code(err) == "REVISION_CONFLICT" and err["error"]["details"]["current_revision"] == 1,
          "stale If-Match returns 412 with the current revision")
    status, h, n2 = api("PATCH", npath, {"content": "# v2\n"}, {"If-Match": '"1"'})
    check(status == 200 and n2["revision"] == 2 and n2["content_revision"] == 2 and h.get("ETag") == '"2"',
          "content change creates content revision 2")
    after_change = event_cursor(C)
    status, _, same = api("PATCH", npath, {"content": "# v2\n"}, {"If-Match": '"2"'})
    check(status == 200 and same["revision"] == 2 and same["content_revision"] == 2, "identical content is a no-op")
    status, h, _ = api("POST", files_path, body, {"Idempotency-Key": create_key})
    check(status == 201 and h.get("Idempotent-Replayed") == "true", "replay after edits returns the original response")
    status, _, n3 = api("PATCH", npath, {"name": "Renamed notes.md"}, {"If-Match": '"2"'})
    check(status == 200 and n3["revision"] == 3 and n3["content_revision"] == 2 and n3["name"] == "Renamed notes.md",
          "a name-only change creates no content revision")
    seen = changes_of(catalog_events(C, after_change, lambda p: any(ch["id"] == nid and ch["revision"] == 3
                                                                   for ch in p["changes"])))
    mine = [ch for ch in seen if ch["id"] == nid]
    check(mine and all(ch["revision"] == 3 for ch in mine), "the change emits an event; no-op and replay emit none")
    revisions = all_pages(f"{npath}/revisions", limit=1)
    check([r["content_revision"] for r in revisions] == [1, 2] and [r["name"] for r in revisions] == ["Lab notes.md"] * 2
          and revisions[0]["content_sha256"] == note["content_sha256"], "revision history is ordered and keeps names")
    status, h, old = content(C, nid, query="?revision=1")
    check(status == 200 and old == data and "Lab notes.md" in h.get("Content-Disposition", ""),
          "an old revision downloads with its original bytes and name")
    status, h, cur = content(C, nid)
    check(status == 200 and cur == b"# v2\n" and "Renamed notes.md" in h.get("Content-Disposition", ""),
          "current content downloads under the current name")
    check(content(C, nid, query="?revision=9")[0] == 404 and content(C, nid, query="?revision=0")[0] == 400,
          "unknown revision returns 404 and invalid revision 400")
    status, _, n4 = api("PATCH", npath, {"status": "trashed"}, {"If-Match": '"3"'})
    check(status == 200 and n4["status"] == "trashed" and n4["revision"] == 4, "notes can be trashed")
    check(nid not in {f["id"] for f in all_pages(files_path)}
          and nid in {f["id"] for f in all_pages(f"{files_path}?status=trashed")}, "trashed notes leave the default listing")
    status, _, n5 = api("PATCH", npath, {"content": "# v3 while trashed\n"}, {"If-Match": '"4"'})
    check(status == 200 and n5["content_revision"] == 3 and n5["revision"] == 5, "history stays append-only while trashed")
    status, _, n6 = api("PATCH", npath, {"status": "active", "name": "Renamed notes.md"}, {"If-Match": '"5"'})
    check(status == 200 and n6["revision"] == 6 and n6["status"] == "active", "notes can be restored")
    for bad_body, label in (({}, "an empty body"), ({"folder": 1}, "an unknown field"), ({"status": "deleted"}, "a bad status"),
                            ({"content": "\u0000"}, "NUL content"), ({"tags": "x"}, "non-array tags"),
                            ({"name": ".."}, "a dot name")):
        status, _, err = api("PATCH", npath, bad_body, {"If-Match": '"6"'})
        check(status == 422 and code(err) == "VALIDATION_FAILED", f"PATCH with {label} returns 422")
    status, err = raw_json("PATCH", npath, '{"content":"\\udc00"}', {"If-Match": '"6"'})
    check(status == 422, "PATCH with an unpaired surrogate returns 422")
    check(api("GET", npath)[2]["revision"] == 6, "rejected PATCHes did not change the note")
    status, _, cat = api("GET", f"/projects/{C}/catalog")
    expected_bytes = len(data) + len(b"# v2\n") + len("# v3 while trashed\n".encode()) + 524288
    check(status == 200 and cat["notes"]["count"] == 3 and cat["notes"]["retained_bytes"] == expected_bytes,
          "catalog status counts notes and all retained revision bytes")

    print("4. User tags and bulk tagging")
    status, _, t1 = api("PATCH", npath, {"tags": ["alpha"]}, {"If-Match": '"6"'})
    check(status == 200 and t1["revision"] == 7 and t1["tags"] == [{"slug": "alpha", "assigned_by": "user"},
                                                                    {"slug": "notes", "assigned_by": "system"}],
          "PATCH tags replaces user assignments and keeps system ones")
    status, _, t2 = api("PATCH", npath, {"tags": ["alpha", "notes"]}, {"If-Match": '"7"'})
    check(status == 200 and t2["revision"] == 7, "listing a system-assigned slug is a no-op")
    status, _, t3 = api("PATCH", npath, {"tags": []}, {"If-Match": '"7"'})
    check(status == 200 and t3["revision"] == 8 and t3["tags"] == [{"slug": "notes", "assigned_by": "system"}],
          "PATCH tags [] clears user tags only")
    status, _, todo = api("GET", f"/projects/{C}/tags/todo")
    check(status == 200 and todo["file_count"] == 0 and todo["revision"] == 1, "tag counts are derived; no ETag bump")
    tag_body = {"file_ids": [nid, src_file["id"], csv_file["id"]], "add": ["shared", "hypotheses"]}
    tag_key = key()
    status, h, tagged = api("POST", f"{files_path}/tagging", tag_body, {"Idempotency-Key": tag_key})
    check(status == 200 and [f["id"] for f in tagged["files"]] == tag_body["file_ids"]
          and all({"shared", "hypotheses"} <= {t["slug"] for t in f["tags"]} for f in tagged["files"]),
          "bulk tagging adds tags to every file, in request order")
    by_id = {f["id"]: f for f in tagged["files"]}
    check(by_id[src_file["id"]]["revision"] == src_file["revision"] + 1
          and by_id[csv_file["id"]]["scientific_origin"] == "simulated" and by_id[csv_file["id"]]["file_kind"] == "artifact"
          and by_id[src_file["id"]]["scientific_origin"] == "reference",
          "user-applied hypotheses tag changes revisions but not scientific labels")
    status, h, replay = api("POST", f"{files_path}/tagging", tag_body, {"Idempotency-Key": tag_key})
    check(status == 200 and replay == tagged and h.get("Idempotent-Replayed") == "true", "bulk tagging replays")
    ids = lambda q: {f["id"] for f in all_pages(f"{files_path}?{q}")}
    check(ids("tag=shared&tag=research") == {src_file["id"]} and ids("tag=shared&tag=notes") == {nid}
          and ids("tag=shared") == set(tag_body["file_ids"]), "tag filters use AND across system and user tags")
    src_rev = by_id[src_file["id"]]["revision"]
    status, _, err = post(f"{files_path}/tagging", {"file_ids": [src_file["id"]], "remove": ["research"]})
    check(status == 422 and code(err) == "VALIDATION_FAILED", "bulk removal of a system assignment returns 422")
    note_rev = by_id[nid]["revision"]
    status, _, err = post(f"{files_path}/tagging", {"file_ids": [nid, f"fil_{'0' * 32}"], "add": ["rollback-tag"]})
    check(status == 422 and code(err) == "INVALID_REFERENCE", "an unknown file in a batch returns 422 INVALID_REFERENCE")
    check(api("GET", f"/projects/{C}/tags/rollback-tag")[0] == 404 and api("GET", npath)[2]["revision"] == note_rev,
          "a failed batch rolls back entirely (no tag, no revision)")
    status, _, d_note = post(f"/projects/{D}/files", {"name": "other.md", "content": "D"})
    check(status == 201, "created a note in project D")
    status, _, err = post(f"{files_path}/tagging", {"file_ids": [d_note["id"]], "add": ["x"]})
    check(status == 422 and code(err) == "INVALID_REFERENCE", "another project's file is an invalid reference")
    for bad_body, label in (({"file_ids": [], "add": ["x"]}, "no files"), ({"file_ids": [nid]}, "no tags"),
                            ({"file_ids": [nid], "add": ["x"], "remove": ["x"]}, "overlapping lists"),
                            ({"file_ids": [nid, nid], "add": ["x"]}, "duplicate files"),
                            ({"file_ids": [nid], "add": ["Bad"]}, "a bad slug"), ({"file_ids": "x", "add": ["x"]}, "non-array ids"),
                            ({"file_ids": [nid], "add": [{}]}, "a non-string slug"),
                            ({"file_ids": [nid], "add": ["x"], "extra": 1}, "an unknown field")):
        status, _, err = post(f"{files_path}/tagging", bad_body)
        check(status == 422 and code(err) == "VALIDATION_FAILED", f"tagging with {label} returns 422")
    status, _, untag = post(f"{files_path}/tagging", {"file_ids": [src_file["id"]], "remove": ["shared"]})
    src_now = untag["files"][0] if status == 200 else {}
    check(status == 200 and {t["slug"] for t in src_now["tags"]} == {"research", "hypotheses"}
          and src_now["revision"] == src_rev + 1, "removing a user tag keeps system tags")

    print("5. Tag CRUD")
    tags_path = f"/projects/{C}/tags"
    status, _, err = post(tags_path, {"slug": "Bad"})
    check(status == 422 and code(err) == "VALIDATION_FAILED", "POST /tags with an invalid slug returns 422")
    status, h, zeta = post(tags_path, {"slug": "zeta", "label": "  Zeta  ", "color": "#a1b2c3"})
    check(status == 201 and h.get("ETag") == '"1"' and zeta["label"] == "Zeta" and zeta["system"] is False
          and zeta["file_count"] == 0 and h.get("Location", "").endswith("/tags/zeta"), "POST /tags creates a user tag")
    status, _, err = post(tags_path, {"slug": "zeta"})
    check(status == 409 and code(err) == "TAG_EXISTS", "an existing slug returns 409 TAG_EXISTS")
    for bad_body in ({"slug": "x1", "color": "#ABCDEF"}, {"slug": "x1", "label": "   "}, {"slug": "x1", "label": 3},
                     {"slug": "x1", "extra": True}, {"slug": ["x1"]}):
        status, _, err = post(tags_path, bad_body)
        check(status == 422, f"POST /tags {json.dumps(bad_body)[:40]} returns 422")
    status, _, err = api("PATCH", f"{tags_path}/zeta", {"label": "Zeta 2"})
    check(status == 428, "PATCH /tags without If-Match returns 428")
    status, h, z2 = api("PATCH", f"{tags_path}/zeta", {"label": "Zeta 2"}, {"If-Match": '"1"'})
    check(status == 200 and z2["revision"] == 2 and z2["label"] == "Zeta 2" and h.get("ETag") == '"2"', "PATCH /tags updates")
    status, _, z3 = api("PATCH", f"{tags_path}/zeta", {"label": "Zeta 2", "color": "#a1b2c3"}, {"If-Match": '"2"'})
    check(status == 200 and z3["revision"] == 2, "a no-op tag PATCH keeps the revision")
    status, _, err = api("PATCH", f"{tags_path}/zeta", {"color": None}, {"If-Match": '"1"'})
    check(status == 412 and code(err) == "REVISION_CONFLICT", "stale tag If-Match returns 412")
    research = api("GET", f"{tags_path}/research")[2]
    status, _, r2 = api("PATCH", f"{tags_path}/research", {"label": "Research"}, {"If-Match": f'"{research["revision"]}"'})
    check(status == 200 and r2["system"] is True and r2["label"] == "Research", "system tags can be relabelled")
    status, _, err = api("DELETE", f"{tags_path}/research", None, {"If-Match": f'"{r2["revision"]}"'})
    check(status == 409 and code(err) == "TAG_PROTECTED", "deleting a system tag returns 409 TAG_PROTECTED")
    check(raw("DELETE", f"{tags_path}/zeta")[0] == 428 and raw("DELETE", f"{tags_path}/zeta", headers={"If-Match": '"1"'})[0] == 412,
          "DELETE /tags requires a current If-Match")
    check(raw("DELETE", f"{tags_path}/no-such-tag", headers={"If-Match": '"1"'})[0] == 404, "deleting an unknown tag returns 404")
    shared = api("GET", f"{tags_path}/shared")[2]
    before = {fid: api("GET", f"{files_path}/{fid}")[2]["revision"] for fid in (nid, csv_file["id"])}
    cursor = event_cursor(C)
    status = raw("DELETE", f"{tags_path}/shared", headers={"If-Match": f'"{shared["revision"]}"'})[0]
    check(status == 204 and api("GET", f"{tags_path}/shared")[0] == 404, "DELETE /tags removes a user tag")
    after = {fid: api("GET", f"{files_path}/{fid}")[2] for fid in before}
    check(all(after[fid]["revision"] == before[fid] + 1 and "shared" not in {t["slug"] for t in after[fid]["tags"]}
              for fid in before), "tag deletion bumps every affected file's revision")
    seen = changes_of(catalog_events(C, cursor, lambda p: any(ch["entity"] == "tag" and ch["id"] == "shared"
                                                              for ch in p["changes"])))
    check(any(ch["entity"] == "tag" and ch["id"] == "shared" and ch["deleted"] for ch in seen)
          and {nid, csv_file["id"]} <= {ch["id"] for ch in seen if ch["entity"] == "file"},
          "tag deletion emits tag and file changes")

    print("6. Original evidence stays immutable; notes are not evidence")
    for target in (src_file, csv_file):
        current = api("GET", f"{files_path}/{target['id']}")[2]
        for patch in ({"name": "x.json"}, {"content": "x"}, {"status": "trashed"}):
            status, _, err = api("PATCH", f"{files_path}/{target['id']}", patch, {"If-Match": f'"{current["revision"]}"'})
            check(status == 409 and code(err) == "FILE_READ_ONLY", f"PATCH {list(patch)[0]} on a {target['file_kind']} returns 409")
    check(content(C, csv_file["id"])[2] == csv_bytes and api("GET", f"/projects/{C}/artifacts/{csv_art['id']}")[2] == legacy_art
          and api("GET", f"/projects/{C}/sources/{src['id']}")[2] == legacy_src, "legacy evidence is unchanged")
    status, _, err = api("GET", f"{files_path}/{csv_file['id']}/revisions")
    check(status == 409 and code(err) == "FILE_KIND_UNSUPPORTED", "revisions of a non-note return 409")
    status, _, err = post(f"/projects/{C}/experiments", {
        "title": "Synthetic", "hypothesis": "SIMULATED.", "method": "computational", "protocol_markdown": "x",
        "variables": [], "success_criteria": [], "input_artifact_ids": [nid],
        "calibration": {"mode": "none", "assumptions": []}, "limitations": []})
    check(status == 422 and code(err) == "INVALID_REFERENCE", "a note cannot be used as an experiment input")
    check(nid not in {a["id"] for a in all_pages(f"/projects/{C}/artifacts")}
          and api("GET", f"/projects/{C}/workspace")[2]["counts"] == counts_before,
          "notes are not artifacts and do not change Workspace.counts")

    print("7. Project scope")
    check(api("GET", f"/projects/{D}/files/{nid}")[0] == 404
          and api("PATCH", f"/projects/{D}/files/{nid}", {"tags": []}, {"If-Match": '"1"'})[0] == 404
          and api("GET", f"/projects/{D}/files/{nid}/revisions")[0] == 404, "project C's note is 404 under project D")

    print("8. Archived projects reject every mutation")
    status, h, _ = api("GET", f"/projects/{C}")
    status, _, archived = api("PATCH", f"/projects/{C}", {"status": "archived"}, {"If-Match": h.get("ETag")})
    check(status == 200 and archived["status"] == "archived", "project C archived")
    rev = api("GET", npath)[2]["revision"]
    zrev = api("GET", f"{tags_path}/zeta")[2]["revision"]
    attempts = [
        ("POST", files_path, {"name": "late.md", "content": "x"}, {"Idempotency-Key": key()}),
        ("PATCH", npath, {"content": "late"}, {"If-Match": f'"{rev}"'}),
        ("POST", f"{files_path}/tagging", {"file_ids": [nid], "add": ["late"]}, {"Idempotency-Key": key()}),
        ("POST", tags_path, {"slug": "late"}, {"Idempotency-Key": key()}),
        ("PATCH", f"{tags_path}/zeta", {"label": "late"}, {"If-Match": f'"{zrev}"'}),
        ("DELETE", f"{tags_path}/zeta", None, {"If-Match": f'"{zrev}"'}),
    ]
    for method, path, bad_body, headers in attempts:
        status, _, err = api(method, path, bad_body, headers)
        check(status == 409 and code(err) == "PROJECT_ARCHIVED", f"{method} {path.replace(C, 'C')[-28:]} on an archived project returns 409")
    check(api("GET", npath)[2]["revision"] == rev and content(C, nid)[0] == 200, "archived notes remain readable and unchanged")
    status, h, _ = api("POST", files_path, body, {"Idempotency-Key": create_key})
    check(status == 201 and h.get("Idempotent-Replayed") == "true", "an earlier create still replays while archived")
    status, h, _ = api("GET", f"/projects/{C}")
    status, _, restored = api("PATCH", f"/projects/{C}", {"status": "active"}, {"If-Match": h.get("ETag")})
    check(status == 200 and restored["status"] == "active", "project C restored")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", type=int, default=1, choices=(1, 2))
    parser.add_argument("--skip-rebuild", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()
    try:
        (slice2 if args.slice == 2 else slice1)(args)
    except AssertionError as err:
        print(f"FAIL {err}", file=sys.stderr)
        print(f"{len(PASSED)} checks passed before the failure", file=sys.stderr)
        sys.exit(1)
    print(f"\nAll {len(PASSED)} workspace file checks passed.")


if __name__ == "__main__":
    main()
