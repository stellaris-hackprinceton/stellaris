#!/usr/bin/env python3
"""Docker integration checks for the workspace file catalog (docs/file-workspace-contract.md).

Run from backend/ (stdlib only) after rebuilding and `docker compose up -d --wait`:

    python3 scripts/workspace_files_test.py --slice 1
    python3 scripts/workspace_files_test.py --slice 1 --skip-rebuild --skip-existing

Slice 1 covers lazy backfill, deterministic IDs and hashes, artifact/record content, default
tags, listing filters/sorts/cursors, project scoping, and unchanged legacy routes.

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
    check(status == 200 and cat["workspace_files"] is True and cat["schema_version"] == 1
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
    status, _, _ = post(f"/projects/{A}/files", {"name": "note.md", "content": "x"})
    check(status == 405, "note creation is not enabled in slice 1")

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", type=int, default=1, choices=(1,))
    parser.add_argument("--skip-rebuild", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()
    try:
        slice1(args)
    except AssertionError as err:
        print(f"FAIL {err}", file=sys.stderr)
        print(f"{len(PASSED)} checks passed before the failure", file=sys.stderr)
        sys.exit(1)
    print(f"\nAll {len(PASSED)} workspace file checks passed.")


if __name__ == "__main__":
    main()
