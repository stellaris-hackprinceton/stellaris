"""Focused terminal API check against a running local backend; performs no model calls."""
import base64
import json
import os
import shutil
import subprocess
import time
import uuid
import urllib.error
import urllib.request


def request(base, method, path, body=None, key=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if key: headers["Idempotency-Key"] = key
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = response.read()
            return response.status, json.loads(payload) if response.headers.get_content_type() == "application/json" else payload
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def output_bytes(base, path, expected=(), timeout=5):
    end = time.monotonic() + timeout
    latest = b""
    while time.monotonic() < end:
        status, page = request(base, "GET", path)
        assert status == 200, (status, page)
        latest = b"".join(base64.b64decode(chunk["data_base64"]) for chunk in page["items"])
        if all(part in latest for part in expected):
            return latest
        time.sleep(.1)
    return latest


def main():
    run_key = uuid.uuid4().hex
    base = os.environ.get("STELLARIS_TEST_URL", "http://127.0.0.1:8000")
    project = os.environ.get("STELLARIS_TEST_PROJECT_ID")
    other = os.environ.get("STELLARIS_TEST_OTHER_PROJECT_ID")
    if not project or not other:
        raise SystemExit("Set STELLARIS_TEST_PROJECT_ID and STELLARIS_TEST_OTHER_PROJECT_ID to existing local projects.")
    root = f"/api/v1/projects/{project}/terminals"
    status, session = request(base, "POST", root, {"rows": 24, "cols": 80}, "terminal-test-start-1-"+run_key)
    assert status == 202, (status, session)
    sid = session["id"]
    for _ in range(100):
        _, session = request(base, "GET", root + "/" + sid)
        if session["status"] != "starting": break
        time.sleep(.1)
    assert session["status"] == "running", session
    assert request(base, "POST", root, {"rows": 24, "cols": 80}, "terminal-test-start-duplicate-"+run_key)[0] == 409
    # Inspect only structural isolation properties; never print or persist environment values.
    if shutil.which("docker"):
        inspected = subprocess.run(["docker", "inspect", f"stellaris-terminal-{sid}"], check=True, capture_output=True, text=True)
        spec = json.loads(inspected.stdout)[0]
        env_names = {entry.split("=", 1)[0] for entry in spec["Config"].get("Env", [])}
        mount_targets = {mount["Destination"] for mount in spec.get("Mounts", [])}
        assert not (env_names & {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"})
        assert "/var/run/docker.sock" not in mount_targets
        assert spec["HostConfig"]["NetworkMode"] == "none"

    seq = 0
    def send(data):
        nonlocal seq
        seq += 1
        return request(base, "PUT", root + f"/{sid}/input/{seq}", {"data_base64": base64.b64encode(data).decode()})

    assert send(b"printf 'PTY_OK\\n'; printf '\\377'; touch /workspace/persist-check; sleep 30\n")[0] == 202
    assert request(base, "PUT", root + f"/{sid}/input/1", {"data_base64": base64.b64encode(b"printf 'PTY_OK\\n'; printf '\\377'; touch /workspace/persist-check; sleep 30\n").decode()})[0] == 202
    conflict = base64.b64encode(b"echo BAD\n").decode()
    assert request(base, "PUT", root + f"/{sid}/input/1", {"data_base64": conflict})[0] == 409
    other_path = f"/api/v1/projects/{other}/terminals/{sid}"
    assert request(base, "GET", other_path)[0] == 404
    assert request(base, "PUT", root + f"/{sid}/size", {"rows": 35, "cols": 100})[0] == 200
    time.sleep(.2)
    assert send(b"\x03")[0] == 202
    time.sleep(.1)
    assert send(b"stty size; echo CTRL_C_OK\n")[0] == 202
    decoded = output_bytes(base, root + f"/{sid}/output?after_sequence=0&limit=100",
                           (b"PTY_OK", b"35 100", b"CTRL_C_OK", b"\xff"))
    assert all(part in decoded for part in (b"PTY_OK", b"35 100", b"CTRL_C_OK", b"\xff")), decoded
    assert request(base, "POST", root + f"/{sid}/close", {}, "terminal-test-close--"+run_key+uuid.uuid4().hex)[0] == 200
    _, transcript = request(base, "GET", root + f"/{sid}/transcript")
    assert transcript == decoded, (len(transcript), len(decoded))
    status, second = request(base, "POST", root, {"rows": 24, "cols": 80}, "terminal-test-start-2-"+run_key)
    assert status == 202, (status, second)
    sid2 = second["id"]
    for _ in range(100):
        _, second = request(base, "GET", root + "/" + sid2)
        if second["status"] != "starting": break
        time.sleep(.1)
    assert second["status"] == "running", second
    status, _ = request(base, "PUT", root + f"/{sid2}/input/1", {"data_base64": base64.b64encode(b"test -f /workspace/persist-check && echo VOLUME_OK\n").decode()})
    assert status == 202
    decoded2 = output_bytes(base, root + f"/{sid2}/output?after_sequence=0&limit=100", (b"VOLUME_OK",))
    assert b"VOLUME_OK" in decoded2, decoded2
    assert request(base, "POST", root + f"/{sid2}/close", {}, "terminal-test-close-2-"+run_key)[0] == 200
    print("terminal PTY, Ctrl-C, resize, binary replay, project scoping, volume persistence, and transcript checks passed")


if __name__ == "__main__": main()
