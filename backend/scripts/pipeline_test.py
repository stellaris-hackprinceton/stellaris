#!/usr/bin/env python3
"""Docker integration checks for runs, isolated workers, bouncing_ball_v1, python_analysis_v1,
Markdown reports, cancellation, isolation, and restart recovery.

Run from the host (stdlib only) after rebuilding all images and `docker compose up -d`:

    cd backend
    docker compose --profile build-only build && docker compose up -d
    python3 scripts/pipeline_test.py                  # includes an API restart (WORKER_LOST)
    python3 scripts/pipeline_test.py --skip-restart

ALL FIXTURE DATA IS SIMULATED. The bouncing-ball video is rendered by
scripts/make_bouncing_ball_fixture.py inside the worker image from known physics, uploaded
with origin "simulated" and a SIMULATED- filename, and its ground truth is used only to check
the measurement pipeline. It is never observed evidence. The CSV and Python fixtures are
likewise simulated/generated test material. Creates real projects, which are retained.
Live agent report generation is opt-in with --live-reports and may incur provider charges.
Does not read any .env file.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BACKEND_DIR, "scripts")
BASE = os.environ.get("STELLARIS_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
WORKER_IMAGE = "stellaris-worker:dev"
PASSED = []

spec = importlib.util.spec_from_file_location("fixture", os.path.join(SCRIPTS_DIR, "make_bouncing_ball_fixture.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)  # Constants + ground_truth() only; rendering imports run in Docker.


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    PASSED.append(message)
    print(f"  ok  {message}")


def key():
    return f"pt-{uuid.uuid4().hex}"


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
    return status, resp_headers, json.loads(payload) if payload else None


def post(path, body, idem=None):
    return api("POST", path, body, {"Idempotency-Key": idem or key()})


def code(body):
    return (body or {}).get("error", {}).get("code")


def docker(*args, check_rc=True, stdin=None):
    result = subprocess.run(["docker", *args], capture_output=True, cwd=BACKEND_DIR, input=stdin)
    if check_rc and result.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:3])} failed: {result.stderr.decode(errors='replace').strip()[:500]}")
    return result


def wait_for(predicate, timeout, what, interval=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {what}")


def wait_run(pid, rid, timeout=300):
    def done():
        _, _, run = api("GET", f"/projects/{pid}/runs/{rid}")
        return run if run["status"] in ("succeeded", "failed", "cancelled") else None
    return wait_for(done, timeout, f"run {rid} to finish", 1.0)


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


def content(pid, aid, inline=False):
    status, headers, data = raw("GET", f"/projects/{pid}/artifacts/{aid}/content" + ("?disposition=inline" if inline else ""))
    assert status == 200, (status, data[:200])
    return headers, data


def all_pages(path):
    items, cursor = [], None
    while True:
        sep = "&" if "?" in path else "?"
        _, _, page = api("GET", path + (f"{sep}limit=100&cursor={cursor}" if cursor else f"{sep}limit=100"))
        items += page["items"]
        cursor = page["next_cursor"]
        if not cursor:
            return items


def worker_containers(run_id):
    out = docker("ps", "-a", "--filter", f"label=stellaris.run_id={run_id}", "--format", "{{.Names}}").stdout.split()
    return [n.decode() for n in out]


def worker_volumes(run_id):
    return docker("volume", "ls", "-q", "--filter", f"label=stellaris.run_id={run_id}").stdout.split()


def api_healthy():
    try:
        return api("GET", "/health")[0] == 200
    except OSError:
        return False


PY_FIXTURE = r'''
"""Test analysis script for python_analysis_v1 (generated test material, not a real analysis)."""
import csv, json, os, socket, sys, time

manifest = json.load(open("/input/manifest.json"))
mode = manifest["parameters"].get("mode", "good")
data = next(a for a in manifest["inputs"] if a["kind"] == "dataset")
print(f"mode={mode} inputs={len(manifest['inputs'])}", flush=True)

if mode == "sleep":
    for i in range(600):
        print(f"heartbeat {i}", flush=True)
        time.sleep(1)
if mode == "crash":
    print("deliberate failure", file=sys.stderr, flush=True)
    sys.exit(3)

rows = list(csv.DictReader(open(data["path"], encoding="utf-8")))
values = [float(r["height_px"]) for r in rows]

def attempt(fn):
    try:
        fn()
        return True
    except Exception:
        return False

checks = {
    "uid": os.getuid(),
    "network_tcp": attempt(lambda: socket.create_connection(("1.1.1.1", 53), timeout=3).close()),
    "dns": attempt(lambda: socket.getaddrinfo("example.com", 80)),
    "input_file_writable": attempt(lambda: open(data["path"], "ab").close()),
    "input_dir_writable": attempt(lambda: open("/input/new.txt", "w").close()),
    "root_fs_writable": attempt(lambda: open("/usr/local/stellaris-test", "w").close()),
    "docker_socket": os.path.exists("/var/run/docker.sock"),
    "workspace_visible": os.path.exists("/workspace"),
    # GPG_KEY is the python base image's public release-key fingerprint, not a credential.
    "secret_like_env": sorted(k for k in os.environ if k != "GPG_KEY"
                              and any(s in k.upper() for s in ("KEY", "SECRET", "TOKEN", "OPENAI", "PASSWORD"))),
    "can_signal_keeper_pid1": attempt(lambda: os.kill(1, 0)),
}
os.makedirs("/output/data", exist_ok=True)
with open("/output/data/isolation.json", "w") as fh:
    json.dump(checks, fh)

measurement = {
    "local_key": "mean", "series": "summary", "quantity": "mean_height", "value": sum(values) / len(values),
    "unit": "px", "time_s": None, "uncertainty": {"absolute": None, "method": None}, "status": "valid",
    "evidence": [{"artifact": {"input_artifact_id": data["artifact_id"]}, "frame_index": None, "time_s": None,
                  "row_index": 0}],
    "calibration_mode": manifest["calibration"]["mode"], "data_origin": "derived",
    "assumptions": ["Arithmetic mean of the height_px column."]}
artifact = {"local_key": "iso", "path": "data/isolation.json", "kind": "dataset", "origin": "derived",
            "mime_type": "application/json", "parents": [{"input_artifact_id": data["artifact_id"]}]}
claims = []
if mode == "no_evidence":
    measurement["evidence"] = []
elif mode == "metric":
    measurement["unit"] = "m"
elif mode == "public_id":
    measurement["id"] = "msr_forged"
elif mode == "traversal":
    artifact["path"] = "../etc/passwd"
elif mode == "symlink":
    os.symlink("/input/manifest.json", "/output/link.json")
    artifact["path"] = "link.json"
elif mode == "observed_artifact":
    artifact["origin"] = "observed"
elif mode == "foreign_source":
    claims.append({"local_key": "c", "kind": "inference", "text": "Cites a source the run did not snapshot.",
                   "measurement_keys": ["mean"], "citations": [{"source_id": manifest["parameters"]["source_id"],
                                                                "locator": None, "excerpt": None}],
                   "evidence": [], "assumptions": ["x"], "limitations": []})
if mode != "no_result":
    with open("/output/result.json", "w") as fh:
        json.dump({"measurements": [measurement], "claims": claims, "artifacts": [artifact], "warnings": []}, fh)
print("done", flush=True)
'''


def make_fixture_video():
    with open(os.path.join(SCRIPTS_DIR, "make_bouncing_ball_fixture.py"), "rb") as fh:
        script = fh.read()
    result = docker("run", "--rm", "-i", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=64m",
                    "--entrypoint", "python", WORKER_IMAGE, "-I", "-", stdin=script)
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-restart", action="store_true")
    parser.add_argument("--live-reports", action="store_true", help="Explicitly allow paid model calls for report generation")
    args = parser.parse_args()
    tag = uuid.uuid4().hex[:8]

    print("1. Capabilities and project layout protection")
    _, _, caps = api("GET", "/capabilities")
    check(caps["features"]["video_analysis"] and isinstance(caps["features"]["markdown_reports"], bool)
          and caps["execution"]["allowed_backends"] == ["isolated_python"] and caps["execution"]["network_access"] is False
          and caps["execution"]["max_wall_time_s"] > 0 and caps["max_log_chunk_bytes"] > 0,
          "capabilities report video analysis, Markdown reports, and real execution limits")
    status, _, proj = post("/projects", {"name": f"Pipeline {tag}", "research_question":
                                         "What fraction of a ball's height is retained per bounce?"})
    status_b, _, proj_b = post("/projects", {"name": f"Pipeline other {tag}"})
    check(status == 201 and status_b == 201, "created projects")
    P, PB = proj["id"], proj_b["id"]
    ctr = docker("ps", "--filter", f"label=stellaris.project_id={P}", "--filter", "label=stellaris.role=project-runtime",
                 "--format", "{{.Names}}").stdout.decode().strip()
    modes = docker("exec", ctr, "stat", "-c", "%n %u %a", "/workspace", "/workspace/data",
                   "/workspace/data/artifacts").stdout.decode().split("\n")
    check(modes[:3] == ["/workspace 0 1777", "/workspace/data 0 1777", "/workspace/data/artifacts 0 755"],
          f"protected ancestors are root-owned ({modes[:3]})")
    for argv, label in ((["mv", "/workspace/data/artifacts", "/workspace/data/moved"], "rename artifacts/"),
                        (["mv", "/workspace/data", "/workspace/moved"], "rename data/"),
                        (["rm", "-rf", "/workspace/data/artifacts"], "delete artifacts/"),
                        (["ln", "-sfn", "/workspace/scratch", "/workspace/data/artifacts"], "replace artifacts/ with a link")):
        docker("exec", ctr, *argv, check_rc=False)
        check(docker("exec", ctr, "test", "-d", "/workspace/data/artifacts", "-a", "!", "-L",
                     "/workspace/data/artifacts", check_rc=False).returncode == 0
              and docker("exec", ctr, "stat", "-c", "%u", "/workspace/data/artifacts").stdout.strip() == b"0",
              f"project user cannot {label}")
    check(docker("exec", ctr, "sh", "-c", "echo ok > /workspace/scratch/t && echo ok > /workspace/data/t",
                 check_rc=False).returncode == 0, "scratch and data stay writable for the project user")

    print("2. SIMULATED fixture upload and experiment")
    video = make_fixture_video()
    check(video[4:8] == b"ftyp" and len(video) > 10_000, f"fixture video rendered in the worker image ({len(video)} bytes)")
    vid = upload(P, video, "SIMULATED-bouncing-ball.mp4", "video/mp4", "video", "simulated")
    check(vid["origin"] == "simulated" and vid["metadata"]["width_px"] == fixture.WIDTH
          and abs(vid["metadata"]["duration_ms"] - fixture.DURATION_S * 1000) <= 50,
          f"fixture uploaded as simulated with server-inspected metadata ({vid['metadata']})")
    exp_body = {"title": "Bounce height retention (SIMULATED fixture)", "hypothesis": "Each bounce keeps a constant "
                "fraction of the previous apex height.", "method": "physical",
                "protocol_markdown": "Drop a ball in front of a fixed camera and record several bounces.",
                "variables": [{"name": "apex height", "role": "dependent", "description": "Ball centre rise", "unit": "px"}],
                "success_criteria": ["At least three bounce apexes measured"], "input_artifact_ids": [vid["id"]],
                "calibration": {"mode": "none", "assumptions": ["No physical scale in the frame"]},
                "limitations": ["Fixture is simulated; it validates the pipeline only."]}
    _, _, exp = post(f"/projects/{P}/experiments", exp_body)
    run_body = {"kind": "analysis", "experiment_id": exp["id"], "experiment_revision": 1,
                "input_artifact_ids": [vid["id"]], "pipeline": "bouncing_ball_v1", "code_artifact_id": None,
                "parameters": {}}

    print("3. Run acceptance validation")
    oversized_calibration = {"mode": "reference_length", "artifact_id": vid["id"], "frame_index": 0,
                             "point_a_px": [0, 0], "point_b_px": [1, 1],
                             "reference_length_m": 10 ** 400, "reference_uncertainty_m": None,
                             "assumptions": []}
    status, _, err = post(f"/projects/{P}/experiments", {**exp_body, "calibration": oversized_calibration})
    check(status == 422 and code(err) == "VALIDATION_FAILED", "oversized calibration integer is rejected without 500")
    for body, expect, label in (
        ({**run_body, "parameters": {"threshold": 3}}, (422, "VALIDATION_FAILED"), "unknown parameter"),
        ({**run_body, "parameters": {"start_time_s": 2.0, "end_time_s": 1.0}}, (422, "VALIDATION_FAILED"), "reversed interval"),
        ({**run_body, "parameters": {"end_time_s": 99.0}}, (422, "VALIDATION_FAILED"), "interval beyond the video"),
        ({**run_body, "experiment_revision": 7}, (409, "EXPERIMENT_REVISION_CONFLICT"), "stale experiment revision"),
        ({**run_body, "code_artifact_id": vid["id"]}, (422, "VALIDATION_FAILED"), "code artifact on bouncing_ball_v1"),
        ({**run_body, "input_artifact_ids": []}, (422, "VALIDATION_FAILED"), "empty inputs"),
        ({**run_body, "kind": "agent"}, (422, "VALIDATION_FAILED"), "agent run outside chat"),
    ):
        status, _, err = post(f"/projects/{P}/runs", body)
        check((status, code(err)) == expect, f"run with {label} returns {expect[0]} {expect[1]}")

    print("4. bouncing_ball_v1 on the SIMULATED fixture (pixels)")
    k = key()
    status, headers, run = post(f"/projects/{P}/runs", run_body, k)
    check(status == 202 and run["status"] == "queued" and run["input"]["parameters"] == {
        "start_time_s": 0, "end_time_s": None, "object_hint": "ball"}, "analysis run accepted with 202 and normalized parameters")
    status, headers, again = post(f"/projects/{P}/runs", run_body, k)
    check(status == 202 and again["id"] == run["id"] and headers.get("Idempotent-Replayed") == "true",
          "run creation is idempotent")
    status, _, _ = api("GET", f"/projects/{PB}/runs/{run['id']}")
    check(status == 404, "run is not visible under another project")
    R1 = wait_run(P, run["id"])
    check(R1["status"] == "succeeded" and R1["provenance_artifact_id"] and R1["revision"] > 2,
          f"bouncing-ball run succeeded ({R1['status']}, {R1['error']}, {R1['result_summary']})")
    check(not worker_containers(R1["id"]) and not worker_volumes(R1["id"]), "worker container and input volume removed")
    ms = all_pages(f"/projects/{P}/runs/{R1['id']}/measurements")
    heights = sorted((m for m in ms if m["series"] == "apex_height_px" and m["status"] == "valid"), key=lambda m: m["time_s"])
    truth = fixture.ground_truth()
    check(len(heights) == len(truth), f"detected {len(heights)} apexes (ground truth {len(truth)})")
    for m, t in zip(heights, truth):
        check(abs(m["value"] - t["height_px"]) <= 3.0 and abs(m["time_s"] - t["time_s"]) <= 0.02 and m["unit"] == "px",
              f"apex at {t['time_s']:.3f} s: measured {m['value']:.2f} px vs truth {t['height_px']:.2f} px")
    ratios = [m for m in ms if m["series"] == "height_ratio" and m["status"] == "valid"]
    check(len(ratios) == len(truth) - 1 and all(abs(m["value"] - fixture.RATIO) <= 0.04 for m in ratios),
          f"height ratios match {fixture.RATIO} ({[round(m['value'], 3) for m in ratios]})")
    energy = [m for m in ms if m["series"] == "energy_retention" and m["status"] == "valid"]
    check(len(energy) == len(ratios) and all(m["assumptions"] for m in energy), "energy retention reported with assumptions")
    accel = [m for m in ms if m["series"] == "flight_fit" and m["unit"] == "px/s^2"]
    check(accel and all(abs(m["value"] - fixture.G_PX_S2) <= 100 for m in accel),
          f"fitted vertical acceleration matches {fixture.G_PX_S2} px/s^2")
    check(all(m["data_origin"] == "simulated" and m["calibration_mode"] == "none" and m["evidence"] for m in ms)
          and not any(m["unit"] in ("m", "m/s", "m/s^2") for m in ms),
          "every measurement is simulated, uncalibrated (pixels only), and evidence-linked")
    check(all(m["uncertainty"]["absolute"] is None or m["uncertainty"]["method"] for m in ms),
          "uncertainties are either null (unknown) or carry a method")
    res = api("GET", f"/projects/{P}/runs/{R1['id']}/results")[2]
    check(res["measurement_count"] == len(ms) and res["chart_artifact_ids"] and res["annotated_media_artifact_ids"]
          and res["claim_ids"] and res["report_artifact_id"] is None, "results list charts, annotated frames, claims")
    check(any(w["code"] == "SIMULATED_INPUT" for w in res["warnings"]), "results warn that the input is simulated")
    h, chart = content(P, res["chart_artifact_ids"][0], inline=True)
    check(chart[:8] == b"\x89PNG\r\n\x1a\n" and h.get("Content-Disposition", "").startswith("inline"), "chart PNG downloads inline")
    _, frame = content(P, res["annotated_media_artifact_ids"][0])
    check(frame[:8] == b"\x89PNG\r\n\x1a\n", "annotated frame is a PNG")
    arts = {a["id"]: a for a in all_pages(f"/projects/{P}/artifacts?run_id={R1['id']}")}
    code_art = next(a for a in arts.values() if a["kind"] == "code")
    with open(os.path.join(BACKEND_DIR, "worker", "bouncing_ball_v1.py"), "rb") as fh:
        source = fh.read()
    check(content(P, code_art["id"])[1] == source and code_art["origin"] == "generated",
          "executed pipeline code is an immutable artifact identical to worker/bouncing_ball_v1.py")
    derived = [a for a in arts.values() if a["kind"] in ("dataset", "chart", "image")]
    check(derived and all(a["origin"] == "simulated" and code_art["id"] in a["parent_artifact_ids"] for a in derived),
          "derived outputs keep the simulated origin and link to the executed code")
    prov = json.loads(content(P, R1["provenance_artifact_id"])[1])
    check(prov["execution"]["worker_image"]["image_id"].startswith("sha256:") and prov["environment"]["libraries"]["opencv"]
          and prov["code"]["sha256"] == hashlib.sha256(source).hexdigest()
          and prov["accepted_snapshot"]["experiment"]["revision"] == 1
          and prov["worker_reported"]["baseline"]["method"] and prov["calibration"]["mode"] == "none",
          "provenance pins image ID, versions, code hash, snapshot, and baseline method")
    check("/input/" not in json.dumps(prov), "provenance contains no worker-local paths")
    claims = all_pages(f"/projects/{P}/claims?run_id={R1['id']}")
    check(claims and all("SIMULATED" in c["text"] for c in claims) and any(c["measurement_ids"] for c in claims),
          "claims are labelled simulated and linked to measurements")
    logs = all_pages(f"/projects/{P}/runs/{R1['id']}/logs")
    seqs = [entry["sequence"] for entry in logs]
    check(logs and seqs == sorted(set(seqs)) and any("bouncing_ball_v1" in entry["text"] for entry in logs),
          "logs are persisted with increasing sequences")
    _, _, after = api("GET", f"/projects/{P}/runs/{R1['id']}/logs?after_sequence={seqs[0]}")
    check(after["items"][0]["sequence"] == seqs[1], "after_sequence selects later log entries")

    print("5. Calibrated run (reference length)")
    _, h, _ = api("GET", f"/projects/{P}/experiments/{exp['id']}")
    status, _, exp2 = api("PATCH", f"/projects/{P}/experiments/{exp['id']}", {"calibration": {
        "mode": "reference_length", "artifact_id": vid["id"], "frame_index": 0,
        "point_a_px": list(fixture.REF_A_PX), "point_b_px": list(fixture.REF_B_PX),
        "reference_length_m": fixture.REF_LENGTH_M, "reference_uncertainty_m": 0.01,
        "assumptions": ["Reference lies in the plane of the ball's motion (fixture truth)."]}}, {"If-Match": h["ETag"]})
    check(status == 200 and exp2["revision"] == 2, "experiment calibrated (revision 2)")
    status, _, err = post(f"/projects/{P}/runs", run_body)
    check(status == 409 and code(err) == "EXPERIMENT_REVISION_CONFLICT", "old revision is rejected after the edit")
    _, _, run2 = post(f"/projects/{P}/runs", {**run_body, "experiment_revision": 2})
    R2 = wait_run(P, run2["id"])
    check(R2["status"] == "succeeded", f"calibrated run succeeded ({R2['error']})")
    ms2 = all_pages(f"/projects/{P}/runs/{R2['id']}/measurements")
    mpp = fixture.REF_LENGTH_M / (fixture.REF_B_PX[0] - fixture.REF_A_PX[0])
    hm = sorted((m for m in ms2 if m["series"] == "apex_height_m" and m["status"] == "valid"), key=lambda m: m["time_s"])
    check(len(hm) == len(truth) and all(abs(m["value"] - t["height_px"] * mpp) <= 0.015 and m["unit"] == "m"
                                        and m["calibration_mode"] == "reference_length" for m, t in zip(hm, truth)),
          f"metre heights match truth x {mpp} m/px ({[round(m['value'], 3) for m in hm]})")
    check(all(m["uncertainty"]["absolute"] is not None for m in hm), "metre heights carry propagated uncertainty")
    g_m = [m for m in ms2 if m["unit"] == "m/s^2"]
    check(g_m and all(abs(m["value"] - fixture.G_PX_S2 * mpp) <= 0.6 for m in g_m),
          f"calibrated acceleration matches {fixture.G_PX_S2 * mpp} m/s^2")
    prov2 = json.loads(content(P, R2["provenance_artifact_id"])[1])
    check(abs(prov2["calibration"]["conversion"]["meters_per_pixel"] - mpp) < 1e-12,
          "provenance records the meters-per-pixel conversion")
    check(json.loads(content(P, R1["provenance_artifact_id"])[1])["accepted_snapshot"]["experiment"]["revision"] == 1,
          "the first run keeps its original plan snapshot after the experiment edit")

    print("6. Markdown report")
    _, _, src = post(f"/projects/{P}/sources", {"title": "Coefficient of restitution (manual reference)",
                                                "url": "https://example.org/restitution"})
    status, _, err = post(f"/projects/{P}/runs", {"kind": "report", "experiment_id": exp["id"], "evidence_run_ids": [],
                                                  "source_ids": [], "title": "x", "format": "markdown"})
    check(status == 422, "report without evidence runs is rejected")
    _, _, other_exp = post(f"/projects/{P}/experiments", {**exp_body, "title": "Other plan"})
    status, _, err = post(f"/projects/{P}/runs", {"kind": "report", "experiment_id": other_exp["id"],
                                                  "evidence_run_ids": [R1["id"]], "source_ids": [], "title": "x",
                                                  "format": "markdown"})
    check(status == 422 and code(err) == "VALIDATION_FAILED", "report with evidence from another experiment is rejected")
    if args.live_reports:
        _, _, rr = post(f"/projects/{P}/runs", {"kind": "report", "experiment_id": exp["id"],
                                                "evidence_run_ids": [R1["id"], R2["id"]], "source_ids": [src["id"]],
                                                "title": "Bounce retention report (SIMULATED fixture)", "format": "markdown"})
        RR = wait_run(P, rr["id"], 600)
        rres = api("GET", f"/projects/{P}/runs/{RR['id']}/results")[2]
        check(RR["status"] == "succeeded" and rres["report_artifact_id"] and RR["provenance_artifact_id"],
              f"report run succeeded with a report artifact and provenance ({RR['error']})")
        report_art = api("GET", f"/projects/{P}/artifacts/{rres['report_artifact_id']}")[2]
        _, md_bytes = content(P, report_art["id"], inline=True)
        md = md_bytes.decode("utf-8")
        check(report_art["mime_type"] == "text/markdown" and report_art["kind"] == "report" and report_art["filename"].endswith(".md"),
              "report is an immutable Markdown artifact")
        check("SIMULATED" in md and "not an observation" in md, "report labels simulated results")
        check(all(f"{m['value']:.6g}" in md for m in heights + hm), "report contains the measured apex heights (px and m)")
        check(R1["id"] in md and R2["id"] in md and src["url"] in md and RR["provenance_artifact_id"] in md
              and R1["provenance_artifact_id"] in md, "report links runs, sources, and provenance")
        check("revision 1" in md and "revision 2" in md and "m/px" in md, "report uses each run's accepted snapshot")
        check("does not mean any experiment" in md, "report states that generation success is not experimental success")
        _, _, ws = api("GET", f"/projects/{P}/workspace")
        check(ws["latest_report_artifact_id"] == report_art["id"] and ws["counts"]["runs"] >= 3 and ws["active_run_ids"] == [],
              "workspace shows run count, no active runs, and the latest report")
    else:
        print("Agent report generation skipped. Use --live-reports only with live provider authorization.")

    print("7. python_analysis_v1 and untrusted output")
    csv_bytes = b"t_s,height_px\n0.0,100\n0.5,64\n1.0,41\n"
    csv_art = upload(P, csv_bytes, "SIMULATED-heights.csv", "text/csv", "dataset", "simulated")
    script = upload(P, PY_FIXTURE.encode(), "it_analysis.py", "text/x-python", "code", "generated")
    _, _, exp3 = post(f"/projects/{P}/experiments", {**exp_body, "title": "Python check", "input_artifact_ids": [csv_art["id"]]})
    py_body = {"kind": "analysis", "experiment_id": exp3["id"], "experiment_revision": 1,
               "input_artifact_ids": [csv_art["id"]], "pipeline": "python_analysis_v1", "code_artifact_id": script["id"],
               "parameters": {"mode": "good"}}
    _, _, good = post(f"/projects/{P}/runs", py_body)
    G = wait_run(P, good["id"])
    gms = all_pages(f"/projects/{P}/runs/{G['id']}/measurements")
    check(G["status"] == "succeeded" and len(gms) == 1 and abs(gms[0]["value"] - 205 / 3) < 1e-9
          and gms[0]["data_origin"] == "simulated" and gms[0]["evidence"][0]["artifact_id"] == csv_art["id"],
          f"python_analysis_v1 succeeded with an evidence-linked measurement ({G['error']})")
    gres = api("GET", f"/projects/{P}/runs/{G['id']}/results")[2]
    check(any(w["code"] == "ORIGIN_RELABELLED" for w in gres["warnings"]), "derived output on simulated input is relabelled")
    iso_art = next(a for a in all_pages(f"/projects/{P}/artifacts?run_id={G['id']}") if a["filename"] == "isolation.json")
    iso = json.loads(content(P, iso_art["id"])[1])
    check(iso["uid"] == 10002 and not iso["network_tcp"] and not iso["dns"], f"worker has no network and runs as 10002 ({iso})")
    check(not iso["input_file_writable"] and not iso["input_dir_writable"] and not iso["root_fs_writable"],
          "inputs and root filesystem are read-only for the script")
    check(not iso["docker_socket"] and not iso["workspace_visible"] and not iso["secret_like_env"]
          and not iso["can_signal_keeper_pid1"], "no Docker socket, project volume, secrets, or control of the keeper")
    for mode, expect in (("no_evidence", "INVALID_OUTPUT"), ("metric", "INVALID_OUTPUT"), ("public_id", "INVALID_OUTPUT"),
                         ("traversal", "INVALID_OUTPUT"), ("symlink", "INVALID_OUTPUT"),
                         ("observed_artifact", "INVALID_OUTPUT"), ("no_result", "INVALID_OUTPUT"),
                         ("foreign_source", "INVALID_OUTPUT"), ("crash", "WORKER_FAILED")):
        params = {"mode": mode, **({"source_id": src["id"]} if mode == "foreign_source" else {})}
        _, _, bad = post(f"/projects/{P}/runs", {**py_body, "parameters": params})
        B = wait_run(P, bad["id"])
        count = api("GET", f"/projects/{P}/runs/{B['id']}/results")[2]["measurement_count"]
        check(B["status"] == "failed" and B["error"]["code"] == expect and count == 0 and B["provenance_artifact_id"],
              f"{mode}: run failed with {expect}, no measurements published, provenance kept ({B['error']['message'][:90]})")

    print("8. Cancellation and worker isolation")
    _, _, slow = post(f"/projects/{P}/runs", {**py_body, "parameters": {"mode": "sleep"}})
    wait_for(lambda: any("heartbeat" in e["text"] for e in api("GET", f"/projects/{P}/runs/{slow['id']}/logs")[2]["items"]),
             120, "sleeping worker output")
    name = f"stellaris-run-{slow['id']}-worker"
    info = json.loads(docker("inspect", name).stdout)[0]
    hc = info["HostConfig"]
    mounts = info["Mounts"]
    check(hc["NetworkMode"] == "none" and hc["ReadonlyRootfs"] and hc["CapDrop"] == ["ALL"]
          and any("no-new-privileges" in s for s in hc["SecurityOpt"]) and hc["Memory"] > 0 and hc["PidsLimit"] > 0
          and hc["NanoCpus"] > 0, "worker: no network, read-only root, no capabilities, resource limits")
    check(len(mounts) == 1 and mounts[0]["Type"] == "volume" and mounts[0]["Destination"] == "/input"
          and mounts[0]["RW"] is False and set(hc.get("Tmpfs") or {}) == {"/output", "/tmp"}
          and all("docker.sock" not in (m.get("Source") or "") for m in mounts),
          "worker: only a read-only input volume plus bounded tmpfs output, no socket or host mounts")
    check(info["Config"]["User"] == "10003:10003" and info["Config"]["Labels"].get("stellaris.run_id") == slow["id"],
          "worker keep-alive runs as a separate non-root user and is labelled with its run")
    st = docker("exec", name, "stat", "-c", "%u %a", "/input/manifest.json").stdout.decode().strip()
    check(st == "0 444", "input files are root-owned and read-only")
    status, _, c1 = post(f"/projects/{P}/runs/{slow['id']}/cancel", {})
    check(status == 202 and c1["status"] == "cancelling", "cancel of a running run returns 202 cancelling")
    C = wait_run(P, slow["id"], 60)
    check(C["status"] == "cancelled" and C["provenance_artifact_id"], "run ends cancelled with provenance kept")
    check(not worker_containers(C["id"]) and not worker_volumes(C["id"]), "cancelled worker resources removed")
    status, _, c2 = post(f"/projects/{P}/runs/{slow['id']}/cancel", {})
    check(status == 200 and c2["status"] == "cancelled", "cancel of a terminal run returns 200")
    check(api("GET", f"/projects/{P}/runs/{C['id']}/logs")[2]["items"], "partial logs of the cancelled run remain")

    if args.skip_restart:
        print("Restart recovery skipped.")
    else:
        print("9. Restart recovery")
        _, _, lost = post(f"/projects/{P}/runs", {**py_body, "parameters": {"mode": "sleep"}})
        wait_for(lambda: worker_containers(lost["id"]) and api("GET", f"/projects/{P}/runs/{lost['id']}")[2]["status"]
                 == "running", 120, "running worker")
        docker("compose", "restart", "api")
        wait_for(api_healthy, 120, "API health after restart", 1.0)
        L = api("GET", f"/projects/{P}/runs/{lost['id']}")[2]
        check(L["status"] == "failed" and L["error"]["code"] == "WORKER_LOST", "interrupted run becomes failed/WORKER_LOST")
        wait_for(lambda: not worker_containers(lost["id"]) and not worker_volumes(lost["id"]), 90,
                 "lost worker cleanup")
        check(True, "the lost run's labelled worker container and volume were removed")
        check(api("GET", f"/projects/{P}/runs/{R1['id']}")[2] == R1, "completed runs are unchanged by the restart")

    print(f"\nPASS: {len(PASSED)} checks. Projects {P} and {PB} were left in place.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError, KeyError, TypeError, IndexError, ValueError, StopIteration) as exc:
        print(f"\nFAIL after {len(PASSED)} passing checks: {exc!r}", file=sys.stderr)
        sys.exit(1)
