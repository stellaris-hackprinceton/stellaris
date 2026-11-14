#!/usr/bin/env python3
"""Docker integration checks for Slurm + Apptainer remote execution (Contracts 1.1, ADR-0001).

Run from the host (stdlib only) with the local simulated cluster up:

    cd backend
    docker compose --profile build-only build && docker compose build slurm
    docker compose --profile hpc up -d api slurm
    python3 scripts/hpc_test.py                 # includes a backend restart (job reattachment)
    python3 scripts/hpc_test.py --skip-slow     # skips the restart, timeout, and memory checks

Covers capabilities, request validation, the approval flow (approve, stale hash, repeated and
contradictory decisions, reject), successful execution with provenance and isolation checks,
worker failure, cancellation of a running job, and (unless --skip-slow) Slurm time and memory
limits plus reattachment after an API restart. Fixture data is SIMULATED test material.
Creates real projects, which are retained. Does not read any .env file.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("STELLARIS_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
PASSED = []

SCRIPT = r'''
"""hpc_test fixture (generated test material, not a real analysis)."""
import csv, json, os, socket, sys, time
m = json.load(open("/input/manifest.json"))
p = m["parameters"]
print("fixture start", p, flush=True)
for i in range(int(p.get("sleep", 0))):
    print(f"heartbeat {i}", flush=True)
    time.sleep(1)
if p.get("crash"):
    print("deliberate failure", file=sys.stderr, flush=True)
    sys.exit(3)
if p.get("mem_mb"):
    block = bytearray(int(p["mem_mb"]) * 1024 * 1024)
    for i in range(0, len(block), 4096):
        block[i] = 1
    time.sleep(10)
data = next(a for a in m["inputs"] if a["kind"] == "dataset")
values = [float(r["height_px"]) for r in csv.DictReader(open(data["path"], encoding="utf-8"))]
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3).close()
    tcp = True
except OSError:
    tcp = False
try:
    open("/input/probe", "w")
    input_writable = True
except OSError:
    input_writable = False
iso = {"uid": os.getuid(), "network_tcp": tcp, "input_writable": input_writable,
       "env_has_secrets": any(k.startswith(("AWS_", "OPENAI_", "SSH_")) for k in os.environ)}
json.dump(iso, open("/output/isolation.json", "w"))
json.dump({"measurements": [{
    "local_key": "mean", "series": "heights", "quantity": "mean_height", "value": sum(values) / len(values),
    "unit": "px", "time_s": None, "uncertainty": {"absolute": None, "method": None}, "status": "valid",
    "evidence": [{"artifact": {"input_artifact_id": data["artifact_id"]}, "frame_index": None, "time_s": None,
                  "row_index": 0}],
    "calibration_mode": "none", "data_origin": "derived", "assumptions": []}],
    "claims": [], "warnings": [],
    "artifacts": [{"local_key": "iso", "path": "isolation.json", "kind": "environment", "origin": "generated",
                   "mime_type": "application/json", "parents": []}]}, open("/output/result.json", "w"))
print("fixture done", flush=True)
'''


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    PASSED.append(message)
    print(f"  ok  {message}")


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
    status, _, payload = raw(method, path, data, hdrs)
    return status, json.loads(payload) if payload else None


def post(path, body, idem=None):
    return api("POST", path, body, {"Idempotency-Key": idem or f"hpc-{uuid.uuid4().hex}"})


def code(body):
    return (body or {}).get("error", {}).get("code")


def upload(pid, data, filename, mime, kind, origin):
    status, up = post(f"/projects/{pid}/uploads", {"filename": filename, "mime_type": mime, "size_bytes": len(data),
                                                   "sha256": hashlib.sha256(data).hexdigest(), "kind": kind,
                                                   "origin": origin})
    assert status == 201, up
    status, _, body = raw("PUT", f"/projects/{pid}/uploads/{up['id']}/content", data, {"Content-Type": mime})
    assert status == 204, body
    status, art = post(f"/projects/{pid}/uploads/{up['id']}/complete", {})
    assert status == 200, art
    return art


def wait(predicate, timeout, what, interval=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {what}")


def get_run(pid, rid):
    return api("GET", f"/projects/{pid}/runs/{rid}")[1]


def wait_status(pid, rid, statuses, timeout=300):
    return wait(lambda: (r := get_run(pid, rid)) and r["status"] in statuses and r, timeout, f"{rid} in {statuses}")


def approvals(pid, rid):
    return api("GET", f"/projects/{pid}/runs/{rid}/approvals")[1]["items"]


def decide(pid, approval, decision, sha=None, idem=None):
    return post(f"/projects/{pid}/approvals/{approval['id']}/decision",
                {"decision": decision, "action_sha256": sha or approval["action_sha256"]}, idem)


def submit_and_approve(pid, body, timeout=240):
    status, run = post(f"/projects/{pid}/runs", body)
    assert status == 202, run
    wait_status(pid, run["id"], ("awaiting_approval", "failed"), timeout=timeout)
    pending = approvals(pid, run["id"])[0]
    status, decided = decide(pid, pending, "approve")
    assert status == 200 and decided["status"] == "approved", decided
    return run["id"], pending


def logs(pid, rid):
    return "".join(e["text"] for e in api("GET", f"/projects/{pid}/runs/{rid}/logs?limit=100")[1]["items"])


def compose(*args):
    return subprocess.run(["docker", "compose", *args], cwd=BACKEND_DIR, capture_output=True, text=True)


def offline_transport_checks():
    """Exercise SSH transport bounds and host-key policy without Docker or a cluster."""
    sys.path.insert(0, os.path.join(BACKEND_DIR, "api"))
    from stellaris_api import hpc

    class Channel:
        def __init__(self, mode):
            self.mode, self.closed, self.started = mode, False, False

        def exec_command(self, _command):
            self.started = True

        def recv_ready(self):
            return False

        def recv_stderr_ready(self):
            return self.mode == "stderr" and self.started

        def recv_stderr(self, size):
            return b"x" * size

        def exit_status_ready(self):
            return False

        def recv_exit_status(self):
            return 0

        def close(self):
            self.closed = True

    class Transport:
        def __init__(self, channel):
            self.channel = channel

        def open_session(self, timeout):
            return self.channel

    for mode, limit in (("idle", 0.01), ("stderr", 60)):
        channel = Channel(mode)
        cluster = hpc.SlurmCluster.__new__(hpc.SlurmCluster)
        cluster._ssh = lambda: SimpleNamespace(get_transport=lambda: Transport(channel))
        dropped = []
        cluster._drop = lambda: dropped.append(True)
        try:
            cluster.run(["sinfo"], timeout=limit)
            raise AssertionError(f"{mode} channel unexpectedly succeeded")
        except hpc.ClusterUnavailable as exc:
            check("limit" in str(exc), f"{mode} SSH channel is bounded")
        check(channel.closed and dropped, f"{mode} SSH channel closes and connection is dropped")

    class FakeClient:
        instances = []

        def __init__(self):
            self.policy = None
            self.closed = False
            self.__class__.instances.append(self)

        def load_host_keys(self, _path):
            pass

        def set_missing_host_key_policy(self, policy):
            self.policy = policy

        def connect(self, *args, **kwargs):
            pass

        def save_host_keys(self, path):
            with open(path, "wb") as stream:
                stream.write(b"pinned")

        def get_transport(self):
            return SimpleNamespace(set_keepalive=lambda _seconds: None)

        def close(self):
            self.closed = True

    class AutoAddPolicy:
        pass

    class RejectPolicy:
        pass

    fake_paramiko = SimpleNamespace(SSHClient=FakeClient, AutoAddPolicy=AutoAddPolicy, RejectPolicy=RejectPolicy,
                                    Ed25519Key=SimpleNamespace(from_private_key_file=lambda _path: object()),
                                    SSHException=type("SSHException", (Exception,), {}))
    with tempfile.TemporaryDirectory(prefix="stellaris-hpc-transport-") as key_dir, \
            patch.dict(sys.modules, {"paramiko": fake_paramiko}):
        external = hpc.SlurmCluster.__new__(hpc.SlurmCluster)
        external.config = SimpleNamespace(slurm_host="external", slurm_cluster_kind="external",
                                          slurm_key_dir=key_dir, slurm_port=22, slurm_user="user")
        try:
            hpc.SlurmCluster._connect(external)
            raise AssertionError("external cluster unexpectedly trusted an unpinned key")
        except hpc.ClusterUnavailable as exc:
            check("host key" in str(exc), "external clusters require an operator-pinned host key")
        check(FakeClient.instances[-1].closed, "external host-key rejection closes the SSH client")

        local = hpc.SlurmCluster.__new__(hpc.SlurmCluster)
        local.config = SimpleNamespace(slurm_host="local", slurm_cluster_kind="local_simulated",
                                       slurm_key_dir=key_dir, slurm_port=22, slurm_user="user")
        local._key_path = lambda: os.path.join(key_dir, "unused-test-path")
        with patch.object(hpc.SlurmCluster, "_key_path", lambda _self: "unused-test-path"):
            # The fake key loader avoids accessing any real key file.
            result = hpc.SlurmCluster._connect(local)
        client = FakeClient.instances[-1]
        check(isinstance(client.policy, AutoAddPolicy),
              "local simulated cluster retains first-use key pinning")
        result.close()


def slurm_state(job_id):
    out = compose("exec", "-T", "slurm", "scontrol", "show", "job", "-o", str(job_id)).stdout
    return next((t.split("=", 1)[1] for t in out.split() if t.startswith("JobState=")), None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-slow", action="store_true")
    parser.add_argument("--offline-transport", action="store_true",
                        help="run only fake-channel SSH bounds and host-key policy checks")
    args = parser.parse_args()

    if args.offline_transport:
        offline_transport_checks()
        print(f"PASS: {len(PASSED)} offline HPC transport checks")
        return

    print("1. capabilities")
    _, caps = api("GET", "/capabilities")
    check("slurm" in caps["execution"]["allowed_backends"] and caps["features"]["remote_compute"],
          "slurm backend advertised")
    rc = caps["remote_compute"]
    check(rc["cluster_kind"] == "local_simulated" and rc["approval_required"] and rc["partitions"],
          f"remote_compute describes the local simulated cluster ({[p['name'] for p in rc['partitions']]})")
    part = rc["partitions"][0]

    status, project = post("/projects", {"name": "HPC test", "research_question": "Slurm execution test"})
    assert status == 201, project
    pid = project["id"]
    csv_art = upload(pid, b"t_s,height_px\n0.0,100\n0.5,64\n1.0,41\n", "SIMULATED-heights.csv", "text/csv",
                     "dataset", "simulated")
    script = upload(pid, SCRIPT.encode(), "hpc_fixture.py", "text/x-python", "code", "generated")
    _, exp = post(f"/projects/{pid}/experiments", {
        "title": "HPC fixture (SIMULATED)", "hypothesis": "The cluster runs the same worker contract.",
        "method": "computational", "protocol_markdown": "Run the fixture on Slurm.", "variables": [],
        "success_criteria": ["Run completes"], "input_artifact_ids": [csv_art["id"]],
        "calibration": {"mode": "none", "assumptions": []}, "limitations": ["Simulated fixture."]})

    def body(params=None, resources=None):
        execution = {"backend": "slurm"}
        if resources is not None:
            execution["resources"] = resources
        return {"kind": "analysis", "experiment_id": exp["id"], "experiment_revision": 1,
                "input_artifact_ids": [csv_art["id"]], "pipeline": "python_analysis_v1",
                "code_artifact_id": script["id"], "parameters": params or {}, "execution": execution}

    print("2. request validation")
    status, err = post(f"/projects/{pid}/runs", body(resources={"partition": "nope"}))
    check(status == 422, f"unknown partition rejected ({code(err)})")
    status, err = post(f"/projects/{pid}/runs", body(resources={"cpus": part["max_cpus"] + 1}))
    check(status == 422, f"CPU request above the partition limit rejected ({code(err)})")
    bad = body()
    bad["execution"] = {"backend": "isolated_python", "resources": {"cpus": 1}}
    status, err = post(f"/projects/{pid}/runs", bad)
    check(status == 422, "resources rejected for the local backend")

    print("3. approval flow and successful execution")
    status, run = post(f"/projects/{pid}/runs", body(resources={"cpus": 1, "memory_mb": 512, "wall_time_s": 300}))
    check(status == 202 and run["execution_backend"] == "slurm" and run["remote_job"] is None,
          "slurm run accepted with execution_backend slurm")
    run = wait_status(pid, run["id"], ("awaiting_approval", "failed"), timeout=300)
    check(run["status"] == "awaiting_approval", f"run waits for approval ({run.get('error')})")
    [pending] = approvals(pid, run["id"])
    snap = pending["action_snapshot"]
    check(pending["action_type"] == "remote_compute" and pending["status"] == "pending"
          and snap["resources"]["cpus"] == 1 and len(snap["sif_sha256"]) == 64 and snap["network"] == "none"
          and snap["code_artifact"]["sha256"] == script["sha256"], "approval binds cluster, resources, SIF, and code")
    time.sleep(3)
    check(get_run(pid, run["id"])["status"] == "awaiting_approval", "nothing executes before approval")
    status, err = decide(pid, pending, "approve", sha="0" * 64)
    check(status == 409 and code(err) == "APPROVAL_CHANGED", "stale action hash rejected")
    idem = f"hpc-{uuid.uuid4().hex}"
    status, decided = decide(pid, pending, "approve", idem=idem)
    check(status == 200 and decided["status"] == "approved", "approval accepted")
    status, again = decide(pid, pending, "approve")
    check(status == 200 and again["status"] == "approved", "repeated identical decision returns the stored result")
    status, err = decide(pid, pending, "reject")
    check(status == 409 and code(err) == "APPROVAL_ALREADY_DECIDED", "contradictory decision rejected")
    done = wait_status(pid, run["id"], ("succeeded", "failed", "cancelled"), timeout=300)
    check(done["status"] == "succeeded", f"slurm run succeeded ({done.get('error')})")
    job = done["remote_job"]
    check(job and job["job_id"].isdigit() and job["state"] == "COMPLETED" and job["ended_at"],
          f"remote_job records Slurm job {job and job['job_id']} COMPLETED")
    ms = api("GET", f"/projects/{pid}/runs/{run['id']}/measurements")[1]["items"]
    check(len(ms) == 1 and abs(ms[0]["value"] - 205 / 3) < 1e-9 and ms[0]["data_origin"] == "simulated",
          "measurement validated and relabelled simulated, as on the local backend")
    arts = api("GET", f"/projects/{pid}/artifacts?run_id={run['id']}&limit=100")[1]["items"]
    iso = json.loads(raw("GET", f"/projects/{pid}/artifacts/"
                            f"{next(a['id'] for a in arts if a['filename'] == 'isolation.json')}/content")[2])
    check(not iso["network_tcp"] and not iso["input_writable"] and not iso["env_has_secrets"],
          f"job had no network, read-only input, no credentials ({iso})")
    prov = json.loads(raw("GET", f"/projects/{pid}/artifacts/{done['provenance_artifact_id']}/content")[2])
    ex = prov["execution"]
    check(ex["backend"] == "slurm" and ex["cluster"]["kind"] == "local_simulated"
          and ex["scheduler_job"]["job_id"] == job["job_id"] and ex["worker_image"]["sif_sha256"] == snap["sif_sha256"],
          "provenance records cluster, job, and SIF digest")
    text = logs(pid, run["id"])
    check("fixture done" in text and f"Submitted Slurm job {job['job_id']}" in text, "job stdout streamed to run logs")
    check(slurm_state(job["job_id"]) == "COMPLETED", "Slurm itself reports the job COMPLETED")
    remote_dir = compose("exec", "-T", "slurm", "test", "-e", f"/state/scratch/stellaris/runs/{run['id']}")
    check(remote_dir.returncode != 0, "remote run directory removed after collection")

    print("4. rejection")
    status, run2 = post(f"/projects/{pid}/runs", body())
    run2 = wait_status(pid, run2["id"], ("awaiting_approval",))
    status, rejected = decide(pid, approvals(pid, run2["id"])[0], "reject")
    run2 = get_run(pid, run2["id"])
    res = api("GET", f"/projects/{pid}/runs/{run2['id']}/results")[1]
    check(rejected["status"] == "rejected" and run2["status"] == "cancelled"
          and any(w["code"] == "APPROVAL_REJECTED" for w in res["warnings"]) and run2["remote_job"] is None,
          "rejection cancels the run without submitting a job")

    print("5. failure and cancellation")
    rid, _ = submit_and_approve(pid, body({"crash": True}))
    failed = wait_status(pid, rid, ("succeeded", "failed", "cancelled"))
    check(failed["status"] == "failed" and failed["error"]["code"] == "WORKER_FAILED",
          f"non-zero exit fails with WORKER_FAILED ({failed['error']})")
    check("deliberate failure" in logs(pid, rid), "job stderr streamed to run logs")
    rid, _ = submit_and_approve(pid, body({"sleep": 300}))
    wait(lambda: (get_run(pid, rid).get("remote_job") or {}).get("state") == "RUNNING", 120, "job RUNNING")
    status, _ = post(f"/projects/{pid}/runs/{rid}/cancel", {})
    cancelled = wait_status(pid, rid, ("cancelled", "failed", "succeeded"), timeout=120)
    check(cancelled["status"] == "cancelled", "cancelling a running slurm run cancels it")
    check(slurm_state(cancelled["remote_job"]["job_id"]) == "CANCELLED", "scancel reached Slurm")
    status, run3 = post(f"/projects/{pid}/runs", body())
    run3 = wait_status(pid, run3["id"], ("awaiting_approval",))
    post(f"/projects/{pid}/runs/{run3['id']}/cancel", {})
    check(approvals(pid, run3["id"])[0]["status"] == "expired" and get_run(pid, run3["id"])["status"] == "cancelled",
          "cancelling while awaiting approval expires the approval")

    if not args.skip_slow:
        print("6. Slurm limits")
        rid, _ = submit_and_approve(pid, body({"sleep": 150}, {"wall_time_s": 60, "memory_mb": 512, "cpus": 1}))
        timed = wait_status(pid, rid, ("succeeded", "failed", "cancelled"), timeout=300)
        check(timed["error"] and timed["error"]["code"] == "EXECUTION_TIMEOUT",
              f"Slurm time limit maps to EXECUTION_TIMEOUT ({timed['error']})")
        rid, _ = submit_and_approve(pid, body({"mem_mb": 700}, {"memory_mb": 256, "cpus": 1, "wall_time_s": 120}))
        oom = wait_status(pid, rid, ("succeeded", "failed", "cancelled"), timeout=300)
        check(oom["status"] == "failed" and oom["error"]["code"] in ("RESOURCE_LIMIT_EXCEEDED", "WORKER_FAILED"),
              f"memory over the request is stopped ({oom['error']['code']}, Slurm state {oom['remote_job']['state']})")

        print("7. reattachment after an API restart")
        rid, _ = submit_and_approve(pid, body({"sleep": 45}))
        wait(lambda: (get_run(pid, rid).get("remote_job") or {}).get("state") == "RUNNING", 120, "job RUNNING")
        job_id = get_run(pid, rid)["remote_job"]["job_id"]
        assert compose("restart", "api").returncode == 0
        wait(lambda: api("GET", "/health")[0] == 200 if _up() else False, 120, "API healthy")
        after = wait_status(pid, rid, ("succeeded", "failed", "cancelled"), timeout=300)
        check(after["status"] == "succeeded" and after["remote_job"]["job_id"] == job_id,
              f"run reattached to job {job_id} and succeeded ({after.get('error')})")
        check(f"Reattached to Slurm job {job_id}" in logs(pid, rid), "reattachment logged")

    print(f"\n{len(PASSED)} checks passed (project {pid}).")


def _up():
    try:
        return api("GET", "/health")[0] == 200
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(main())
