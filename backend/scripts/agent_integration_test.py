#!/usr/bin/env python3
"""Provider-free chat/SSE and deterministic Deep Agents integration checks.

Run after rebuilding both images and starting the API. The API test refuses to submit a
message when provider configuration is present, so it cannot accidentally make a live call.
Projects are retained because the MVP has no project deletion operation.
"""

import http.client
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = os.environ.get("STELLARIS_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
PARSED = urllib.parse.urlsplit(BASE)
PASSED = []


def check(ok, message):
    if not ok:
        raise AssertionError(message)
    PASSED.append(message)
    print(f"  ok  {message}")


def api(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = dict(headers or {})
    if body is not None:
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None, response.headers
    except urllib.error.HTTPError as error:
        raw = error.read()
        return error.code, json.loads(raw) if raw else None, error.headers


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"docker {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def project_id():
    configured = os.environ.get("STELLARIS_AGENT_TEST_PROJECT_ID")
    if configured:
        return configured
    name = f"Agent integration {uuid.uuid4().hex[:8]}"
    status, project, _ = api("POST", "/projects", {"name": name},
                             {"Idempotency-Key": f"agent-it-{uuid.uuid4().hex}"})
    check(status == 201, "integration creates a dedicated retained project")
    return project["id"]


def run_agent_runtime_test(project):
    names = docker("ps", "--filter", f"label=stellaris.project_id={project}",
                   "--filter", "label=stellaris.role=project-runtime", "--format", "{{.Names}}").splitlines()
    check(len(names) == 1, "project has one isolated runtime container")
    output = docker("exec", names[0], "python", "/opt/stellaris/agent_runtime_test.py")
    check("Deep Agents deterministic tool flow passed." in output,
          "Deep Agents invokes a backend proposal tool with the test-only deterministic model")


def run_transport_test(project):
    run_id = "run_" + uuid.uuid4().hex
    code = (
        "import sys; from stellaris_api.agent_runs import _put_request,_cleanup_agent_files; "
        "from stellaris_api.config import load_config; from stellaris_api.runtime import ProjectRuntime; "
        "runtime=ProjectRuntime(load_config()); c=runtime.client().containers.get('stellaris-'+sys.argv[1]); "
        "p=_put_request(c,sys.argv[2],{'transport_probe':'bounded stdin transfer'}); "
        "r=c.exec_run(['python','-c','import json,sys; print(json.load(open(sys.argv[1]))[\"transport_probe\"])',p]); "
        "_cleanup_agent_files(c,sys.argv[2]); "
        "(r.exit_code==0 and r.output.decode().strip()=='bounded stdin transfer') or sys.exit(2); "
        "print('Agent request transport passed.')"
    )
    output = docker("compose", "exec", "-T", "api", "python", "-c", code, project, run_id)
    check("Agent request transport passed." in output,
          "request transfer uses bounded stdin and writable runtime tmpfs")


def run_provider_config_test():
    code = (
        "from stellaris_api.agent_runs import selected_model_config; "
        "p,m,e,c,_=selected_model_config({'OPENAI_API_KEY':'fixture','OPENAI_MODEL':'fixture'}); "
        "assert p=='bedrock' and c=='MODEL_CONFIGURATION_MISSING' and not e; "
        "source={'STELLARIS_MODEL_PROVIDER':'bedrock','AWS_ACCESS_KEY_ID':'fixture',"
        "'AWS_SECRET_ACCESS_KEY':'fixture','AWS_REGION':'us-east-1',"
        "'BEDROCK_MODEL_ID':'us.amazon.nova-2-lite-v1:0','OPENAI_API_KEY':'not-selected'}; "
        "p,m,e,c,_=selected_model_config(source); "
        "assert c is None and e['AWS_EC2_METADATA_DISABLED']=='true' and 'OPENAI_API_KEY' not in e; "
        "p,m,e,c,_=selected_model_config({'STELLARIS_MODEL_PROVIDER':'openai',"
        "'OPENAI_API_KEY':'fixture','OPENAI_MODEL':'fixture','AWS_ACCESS_KEY_ID':'not-selected'}); "
        "assert c is None and 'AWS_ACCESS_KEY_ID' not in e; print('Provider config isolation passed.')"
    )
    output = docker("compose", "exec", "-T", "api", "python", "-c", code)
    check("Provider config isolation passed." in output,
          "provider selection never falls back or forwards unselected credentials")


def run_missing_config_api_test(project):
    status, capabilities, _ = api("GET", "/capabilities")
    check(status == 200, "capabilities endpoint responds")
    if capabilities["features"].get("research_chat"):
        print(f"  skip  missing-configuration API check (selected provider: {capabilities['model_provider']}; configured)")
        return
    status, workspace, _ = api("GET", f"/projects/{project}/workspace")
    check(status == 200, "project workspace is readable")

    connection = http.client.HTTPConnection(PARSED.hostname, PARSED.port or 80, timeout=2)
    path = f"{PARSED.path}/projects/{project}/events?after={urllib.parse.quote(workspace['event_cursor'])}"
    connection.request("GET", path, headers={"Accept": "text/event-stream"})
    response = connection.getresponse()
    check(response.status == 200, "project SSE stream opens from the current event cursor")

    body = {"content_markdown": "Test missing provider configuration."}
    status, missing_key, _ = api("POST", f"/projects/{project}/messages", body)
    check(status == 428 and missing_key["error"]["code"] == "PRECONDITION_REQUIRED",
          "chat requires an idempotency key")
    key = "agent-message-it-" + uuid.uuid4().hex
    headers = {"Idempotency-Key": key}
    status, created, _ = api("POST", f"/projects/{project}/messages", body, headers)
    check(status == 202, "chat message is atomically accepted as a queued run")
    replay_status, replay, replay_headers = api("POST", f"/projects/{project}/messages", body, headers)
    check(replay_status == 202 and replay == created and replay_headers.get("Idempotent-Replayed") == "true",
          "same key and body replay the original user, assistant, and run")
    conflict_status, conflict, _ = api("POST", f"/projects/{project}/messages",
                                       {"content_markdown": "Changed body."}, headers)
    check(conflict_status == 409 and conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT",
          "same key with a different chat body is rejected")
    run_id = created["run"]["id"]
    assistant_id = created["assistant_message"]["id"]
    seen = set()
    deadline = time.monotonic() + 30
    buffer = b""
    while time.monotonic() < deadline and not {"message.updated", "run.updated"} <= seen:
        try:
            chunk = response.read1(4096)
        except TimeoutError:
            continue
        if not chunk:
            continue
        buffer += chunk
        while b"\n\n" in buffer:
            frame, buffer = buffer.split(b"\n\n", 1)
            fields = {}
            for line in frame.splitlines():
                if b":" in line:
                    key, value = line.split(b":", 1)
                    fields[key.decode()] = value.lstrip().decode()
            if "data" not in fields:
                continue
            event = json.loads(fields["data"])
            payload = event["payload"]
            if event["type"] == "message.updated" and payload["message"]["id"] == assistant_id:
                check(payload["message"]["status"] == "interrupted", "assistant message is finalized as interrupted")
                seen.add("message.updated")
            if event["type"] == "run.updated" and payload["run"]["id"] == run_id:
                expected = "AWS_ACCESS_KEY_ID" if capabilities["model_provider"] == "bedrock" else "OPENAI_API_KEY"
                check(payload["run"]["status"] == "failed" and
                      payload["run"]["error"]["code"] == "MODEL_CONFIGURATION_MISSING" and
                      expected in payload["run"]["error"]["message"],
                      f"missing {capabilities['model_provider']} configuration fails without a canned response")
                seen.add("run.updated")
    connection.close()
    check({"message.updated", "run.updated"} <= seen, "SSE delivers message finalization and terminal run update")
    status, message, _ = api("GET", f"/projects/{project}/messages/{assistant_id}")
    check(status == 200 and message["status"] == "interrupted", "interrupted assistant message persists through REST")
    status, page, _ = api("GET", f"/projects/{project}/messages")
    check(status == 200 and any(item["id"] == assistant_id for item in page["items"]),
          "message history persists through REST")


def main():
    project = project_id()
    run_transport_test(project)
    run_provider_config_test()
    run_agent_runtime_test(project)
    run_missing_config_api_test(project)
    print(f"Passed {len(PASSED)} agent integration checks.")


if __name__ == "__main__":
    main()
