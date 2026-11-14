#!/usr/bin/env python3
"""Docker integration smoke test for the first Stellaris backend slice.

Run from the host (stdlib only) after `docker compose up -d` in backend/:

    python3 scripts/smoke_test.py            # full run, includes restarts
    python3 scripts/smoke_test.py --skip-restart

Creates real projects and containers; they are retained (there is no hard delete).
Does not read any .env file.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("STELLARIS_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
NETWORK = "stellaris-projects"
PASSED = []


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    PASSED.append(message)
    print(f"  ok  {message}")


def api(method, path, body=None, headers=None):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            return resp.status, resp.headers, json.loads(raw) if raw else None
    except urllib.error.HTTPError as err:
        raw = err.read()
        return err.code, err.headers, json.loads(raw) if raw else None


def docker(*args, check_rc=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, cwd=BACKEND_DIR)
    if check_rc and result.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def wait_for(predicate, timeout, what):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError(f"timed out waiting for {what}")


def api_healthy():
    return api("GET", "/health")[0] == 200


def container_for(project_id):
    out = docker("ps", "-a", "--filter", f"label=stellaris.project_id={project_id}",
                 "--filter", "label=stellaris.role=project-runtime", "--format", "{{.Names}}").stdout.split()
    return out[0] if len(out) == 1 else None


def inspect(name):
    return json.loads(docker("inspect", name).stdout)[0]


def container_healthy(project_id):
    name = container_for(project_id)
    return bool(name) and inspect(name)["State"].get("Health", {}).get("Status") == "healthy"


def create(name, key, extra=None):
    body = {"name": name, **(extra or {})}
    return api("POST", "/projects", body, {"Idempotency-Key": key})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-restart", action="store_true", help="skip api/container restart checks")
    args = parser.parse_args()

    print("1. API availability")
    wait_for(api_healthy, 60, "API health")
    check(True, "GET /health returns 200 (database and Docker reachable)")
    status, _, session = api("GET", "/session")
    check(status == 200 and session["auth_mode"] == "development_none", "GET /session returns dev compatibility body")
    status, _, caps = api("GET", "/capabilities")
    unimplemented = ("image_analysis", "audio_analysis", "remote_compute",
                     "collaboration")
    check(status == 200 and not any(caps["features"][f] for f in unimplemented),
          "capabilities advertise no unimplemented features")
    check(all(caps["features"][f] == caps["model_configured"] for f in
              ("research_chat", "literature_search", "experiment_design")),
          "research capabilities reflect selected provider configuration without making model calls")

    print("2. Project creation and idempotency")
    run = uuid.uuid4().hex[:8]
    key_a = f"smoke-{run}-a"
    status, headers, a = create(f"Smoke A {run}", key_a, {"research_question": "How much energy is lost per bounce?"})
    check(status == 201, f"POST /projects creates project A ({status})")
    check(headers.get("ETag") == '"1"' and headers.get("Location", "").endswith(a["id"]), "create returns ETag \"1\" and Location")
    check(a["status"] == "active" and a["description"] == "" and a["revision"] == 1, "create applies contract defaults")

    status, headers, replay = create(f"Smoke A {run}", key_a, {"research_question": "How much energy is lost per bounce?"})
    check(status == 201 and replay == a and headers.get("Idempotent-Replayed") == "true", "same key + body replays original response")
    status, _, err = create(f"Different {run}", key_a)
    check(status == 409 and err["error"]["code"] == "IDEMPOTENCY_CONFLICT", "same key + different body returns 409 IDEMPOTENCY_CONFLICT")
    status, _, err = api("POST", "/projects", {"name": "No key"})
    check(status == 428 and err["error"]["code"] == "PRECONDITION_REQUIRED", "missing Idempotency-Key returns 428")
    status, _, err = create(f"Bad {run}", f"smoke-{run}-bad", {"colour": "red"})
    check(status == 422 and err["error"]["code"] == "VALIDATION_FAILED", "unknown field returns 422")
    status, _, err = create("   ", f"smoke-{run}-blank")
    check(status == 422, "blank name returns 422")
    status, _, err = api("POST", "/projects", {"name": "x"}, {"Idempotency-Key": f"smoke-{run}-o", "Origin": "http://evil.example"})
    check(status == 403 and err["error"]["code"] == "CSRF_FAILED", "disallowed Origin returns 403 CSRF_FAILED")
    check("request_id" in err["error"], "error envelope carries request_id")

    status, _, b = create(f"Smoke B {run}", f"smoke-{run}-b")
    check(status == 201 and b["id"] != a["id"], "POST /projects creates distinct project B")

    print("3. Dedicated containers and isolation")
    ctr_a, ctr_b = container_for(a["id"]), container_for(b["id"])
    check(ctr_a and ctr_b and ctr_a != ctr_b, "each project has exactly one dedicated container")
    check(container_healthy(a["id"]) and container_healthy(b["id"]), "both project containers are healthy")
    info_a = inspect(ctr_a)
    mounts = info_a["Mounts"]
    check(len(mounts) == 1 and mounts[0]["Type"] == "volume" and mounts[0]["Destination"] == "/workspace",
          "project A has exactly one named-volume mount at /workspace")
    check(all("docker.sock" not in (m.get("Source") or "") for m in mounts), "no Docker socket mounted into project A")
    check(not info_a["HostConfig"].get("PortBindings"), "project container publishes no host ports")
    check(info_a["HostConfig"].get("ReadonlyRootfs") is True, "project container root filesystem is read-only")
    check(docker("exec", ctr_a, "test", "!", "-e", "/var/run/docker.sock", check_rc=False).returncode == 0,
          "/var/run/docker.sock absent inside project A")

    secret = f"secret-{run}"
    docker("exec", ctr_a, "sh", "-c", f"echo {secret} > /workspace/data/smoke.txt")
    check(docker("exec", ctr_b, "test", "!", "-e", "/workspace/data/smoke.txt", check_rc=False).returncode == 0,
          "file written in project A is not visible in project B")
    for d in ("data", "scratch"):
        check(docker("exec", ctr_a, "test", "-w", f"/workspace/{d}", check_rc=False).returncode == 0,
              f"/workspace/{d} is writable in project A")

    ip_b = inspect(ctr_b)["NetworkSettings"]["Networks"][NETWORK]["IPAddress"]
    probe = "import socket,sys; socket.create_connection((sys.argv[1], 8080), timeout=3)"
    check(docker("exec", ctr_b, "python", "-c", probe, ip_b, check_rc=False).returncode == 0,
          "positive control: project B reaches its own runtime on its network IP")
    check(docker("exec", ctr_a, "python", "-c", probe, ip_b, check_rc=False).returncode != 0,
          "project A cannot connect to project B over the project network")

    print("4. Revisions, archive, pagination, workspace")
    pid = a["id"]
    status, headers, _ = api("GET", f"/projects/{pid}")
    check(status == 200 and headers.get("ETag") == '"1"', "GET project returns ETag")
    status, _, err = api("PATCH", f"/projects/{pid}", {"description": "x"})
    check(status == 428 and err["error"]["code"] == "PRECONDITION_REQUIRED", "PATCH without If-Match returns 428")
    status, headers, p = api("PATCH", f"/projects/{pid}", {"description": "Bouncing ball"}, {"If-Match": '"1"'})
    check(status == 200 and p["revision"] == 2 and headers.get("ETag") == '"2"', "PATCH with current ETag bumps revision")
    status, _, err = api("PATCH", f"/projects/{pid}", {"description": "stale"}, {"If-Match": '"1"'})
    check(status == 412 and err["error"]["code"] == "REVISION_CONFLICT", "stale If-Match returns 412 REVISION_CONFLICT")
    status, _, err = api("PATCH", f"/projects/{pid}", {}, {"If-Match": '"2"'})
    check(status == 422, "empty PATCH returns 422")
    status, _, p = api("PATCH", f"/projects/{pid}", {"status": "archived"}, {"If-Match": '"2"'})
    check(status == 200 and p["status"] == "archived" and p["revision"] == 3, "project can be archived")
    status, _, err = api("PATCH", f"/projects/{pid}", {"name": "rename"}, {"If-Match": '"3"'})
    check(status == 409 and err["error"]["code"] == "PROJECT_ARCHIVED", "editing archived project returns 409 PROJECT_ARCHIVED")
    check(container_healthy(pid), "archived project's container stays running")
    status, _, p = api("PATCH", f"/projects/{pid}", {"status": "active"}, {"If-Match": '"3"'})
    check(status == 200 and p["status"] == "active" and p["revision"] == 4, "archived project can be restored")
    expected_a = p

    seen, cursor, pages = set(), None, 0
    while True:
        q = "/projects?limit=1" + (f"&cursor={cursor}" if cursor else "")
        status, _, page = api("GET", q)
        assert status == 200, page
        pages += 1
        seen.update(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if not cursor or pages > 1000:
            break
    check({a["id"], b["id"]} <= seen and pages >= 2, "cursor pagination (limit=1) reaches both projects")
    status, _, _ = api("GET", "/projects?limit=0")
    check(status == 400, "limit=0 returns 400")
    status, _, ws = api("GET", f"/projects/{pid}/workspace")
    check(status == 200 and ws["project"] == expected_a and ws["counts"]["runs"] == 0 and ws["event_cursor"].startswith("evt_"),
          "workspace returns project snapshot, zero counts, and event cursor")
    status, _, err = api("GET", "/projects/prj_doesnotexist")
    check(status == 404 and err["error"]["code"] == "RESOURCE_NOT_FOUND", "unknown project returns 404")

    if args.skip_restart:
        print("Restart checks skipped.")
    else:
        print("5. Restart persistence and reconciliation")
        docker("compose", "restart", "api")
        wait_for(api_healthy, 90, "API health after restart")
        status, _, p = api("GET", f"/projects/{pid}")
        check(status == 200 and p == expected_a, "project metadata survives API restart")
        status, headers, replay = create(f"Smoke A {run}", key_a, {"research_question": "How much energy is lost per bounce?"})
        check(status == 201 and replay == a, "idempotent replay survives API restart")

        docker("restart", ctr_a)
        wait_for(lambda: container_healthy(pid), 60, "project A healthy after container restart")
        out = docker("exec", ctr_a, "cat", "/workspace/data/smoke.txt").stdout.strip()
        check(out == secret, "workspace data survives project container restart")

        docker("rm", "-f", ctr_a)
        docker("compose", "restart", "api")
        wait_for(api_healthy, 90, "API health after second restart")
        wait_for(lambda: container_healthy(pid), 90, "reconciliation recreating project A container")
        out = docker("exec", container_for(pid), "cat", "/workspace/data/smoke.txt").stdout.strip()
        check(out == secret, "reconciliation recreates removed container on the existing volume")

    print(f"\nPASS: {len(PASSED)} checks. Projects {a['id']} and {b['id']} were left in place.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError, KeyError, TypeError) as exc:
        print(f"\nFAIL after {len(PASSED)} passing checks: {exc!r}", file=sys.stderr)
        sys.exit(1)
