"""Deep Agents handler running in the owning project's persistent runtime."""

import json
import hashlib
import logging
import os
import re
import socket
import threading
import time

from . import experiments, research
from .db import transaction
from .errors import ApiError
from .events import record_event
from .executor import RunFailure
from .http import dumps, new_id, now_ts

log = logging.getLogger(__name__)
_PROJECT_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
MAX_AGENT_CONTEXT_BYTES = 8 * 1024 * 1024
MAX_AGENT_OUTPUT_CHARS = 200_000
MAX_AGENT_SECONDS = 300
DEFAULT_MODEL_PROVIDER = "bedrock"
DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_BEDROCK_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
_SAFE_PROVIDER_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_RETRYABLE_PROVIDER_CODES = {
    "ThrottlingException", "ServiceUnavailableException", "InternalServerException",
    "ModelNotReadyException", "ModelTimeoutException", "RequestTimeout", "ReadTimeoutError",
    "ConnectTimeoutError", "EndpointConnectionError", "ConnectionClosedError",
}


def selected_model_config(environ=None):
    """Return (provider, model_id, exec_environment, error_code, safe_error_message).

    Credentials are read only from the API process environment, then only the selected
    provider's explicit values are passed to that project's one-shot runtime exec.
    """
    environ = os.environ if environ is None else environ
    provider = environ.get("STELLARIS_MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER).strip().lower() or DEFAULT_MODEL_PROVIDER
    if provider == "bedrock":
        region = environ.get("AWS_REGION", DEFAULT_AWS_REGION).strip() or DEFAULT_AWS_REGION
        model_id = environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID).strip() or DEFAULT_BEDROCK_MODEL_ID
        missing = [name for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY") if not environ.get(name, "").strip()]
        if missing:
            return provider, model_id, {}, "MODEL_CONFIGURATION_MISSING", (
                "Research chat requires " + " and ".join(missing) + " for the selected Bedrock provider.")
        if (not re.fullmatch(r"[a-z0-9-]{3,64}", region)
                or not re.fullmatch(r"[A-Za-z0-9.:/_-]{1,256}", model_id)):
            return provider, model_id, {}, "MODEL_CONFIGURATION_INVALID", (
                "AWS_REGION or BEDROCK_MODEL_ID is invalid for the selected Bedrock provider.")
        runtime_env = {
            "STELLARIS_MODEL_PROVIDER": provider,
            "AWS_ACCESS_KEY_ID": environ["AWS_ACCESS_KEY_ID"].strip(),
            "AWS_SECRET_ACCESS_KEY": environ["AWS_SECRET_ACCESS_KEY"].strip(),
            "AWS_REGION": region,
            "BEDROCK_MODEL_ID": model_id,
            "AWS_EC2_METADATA_DISABLED": "true",
        }
        session_token = environ.get("AWS_SESSION_TOKEN", "").strip()
        if session_token:
            runtime_env["AWS_SESSION_TOKEN"] = session_token
        return provider, model_id, runtime_env, None, None

    if provider == "openai":
        model_id = environ.get("OPENAI_MODEL", "").strip()
        api_key = environ.get("OPENAI_API_KEY", "").strip()
        if not api_key or not model_id:
            return provider, model_id, {}, "MODEL_CONFIGURATION_MISSING", (
                "Research chat requires OPENAI_API_KEY and OPENAI_MODEL for the selected OpenAI provider.")
        return provider, model_id, {"STELLARIS_MODEL_PROVIDER": provider,
                                    "OPENAI_API_KEY": api_key, "OPENAI_MODEL": model_id}, None, None

    return provider, "", {}, "MODEL_CONFIGURATION_INVALID", (
        "STELLARIS_MODEL_PROVIDER must be 'bedrock' or 'openai'.")


def _project_lock(project_id):
    with _LOCKS_GUARD:
        return _PROJECT_LOCKS.setdefault(project_id, threading.Lock())


def _save_delta(ctx, text, index):
    if not text:
        return
    with transaction(ctx.conn):
        row = ctx.conn.execute("SELECT doc FROM messages WHERE id = ? AND project_id = ?",
                               (ctx.input["assistant_message_id"], ctx.project_id)).fetchone()
        if row is None:
            raise RunFailure("RESOURCE_NOT_FOUND", "The assistant message no longer exists.")
        message = json.loads(row["doc"])
        if message["status"] != "streaming":
            return
        last_index = message["last_chunk_index"]
        if index != (-1 if last_index is None else last_index) + 1:
            raise RunFailure("INVALID_AGENT_STREAM", "The agent returned an invalid message sequence.")
        message["content_markdown"] += text
        message["last_chunk_index"] = index
        message["updated_at"] = now_ts()
        ctx.conn.execute("UPDATE messages SET doc = ? WHERE id = ?", (dumps(message), message["id"]))
        record_event(ctx.conn, ctx.project_id, "message.delta",
                     {"message_id": message["id"], "chunk_index": index, "text": text}, run_id=ctx.run_id)


def _finish_message(ctx, *, status, claim_ids=None, extra_text=""):
    with transaction(ctx.conn):
        row = ctx.conn.execute("SELECT doc FROM messages WHERE id = ? AND project_id = ?",
                               (ctx.input["assistant_message_id"], ctx.project_id)).fetchone()
        if row is None:
            return
        message = json.loads(row["doc"])
        if extra_text:
            message["content_markdown"] += extra_text
        message["status"] = status
        if claim_ids is not None:
            message["claim_ids"] = claim_ids
        message["updated_at"] = now_ts()
        ctx.conn.execute("UPDATE messages SET doc = ? WHERE id = ?", (dumps(message), message["id"]))
        record_event(ctx.conn, ctx.project_id, "message.updated", {"message": message}, run_id=ctx.run_id)


def _apply_proposal(ctx, event, claim_ids):
    kind, payload = event.get("kind"), event.get("payload")
    if not isinstance(payload, dict):
        raise RunFailure("INVALID_AGENT_OUTPUT", "The agent proposed an invalid resource.")
    try:
        with transaction(ctx.conn):
            if kind == "source":
                allowed = {"title", "url", "authors", "external_id", "published_at", "doi", "abstract"}
                if set(payload) - allowed:
                    raise RunFailure("INVALID_AGENT_OUTPUT", "The source proposal contained unsupported fields.")
                source = research.publish_source(ctx.conn, ctx.project_id, provider="arxiv",
                                                 retrieval_status="abstract_retrieved", **payload)
                return {"source_id": source["id"], "title": source["title"]}
            if kind == "experiment":
                allowed = set(experiments.FIELDS)
                if set(payload) != allowed:
                    raise RunFailure("INVALID_AGENT_OUTPUT", "The experiment proposal was incomplete.")
                exp = experiments.create_experiment(ctx.conn, ctx.project_id, payload)
                return {"experiment_id": exp["id"], "revision": exp["revision"]}
            if kind == "claim":
                allowed = {"kind", "text", "measurement_ids", "citations", "evidence", "assumptions", "limitations"}
                if set(payload) - allowed:
                    raise RunFailure("INVALID_AGENT_OUTPUT", "The claim proposal contained unsupported fields.")
                payload = dict(payload)
                citations = []
                for citation in payload.get("citations", []):
                    citation = dict(citation)
                    source_ref = citation.get("source_id")
                    if isinstance(source_ref, str) and source_ref.startswith("arxiv:"):
                        external_id = source_ref[len("arxiv:"):]
                        rows = ctx.conn.execute("SELECT doc FROM sources WHERE project_id = ? AND provider = 'arxiv' "
                                                "ORDER BY created_at, id", (ctx.project_id,)).fetchall()
                        source = next((json.loads(row["doc"]) for row in rows
                                       if json.loads(row["doc"]).get("external_id") == external_id), None)
                        if source is None:
                            raise RunFailure("INVALID_AGENT_OUTPUT", "The cited arXiv source was not retrieved in this project.")
                        citation["source_id"] = source["id"]
                    citations.append(citation)
                payload["citations"] = citations
                claim = research.publish_claim(ctx.conn, ctx.project_id, run_id=ctx.run_id, **payload)
                claim_ids.append(claim["id"])
                return {"claim_id": claim["id"]}
    except ApiError as exc:
        raise RunFailure("INVALID_AGENT_OUTPUT", f"Backend rejected the {kind or 'resource'} proposal: {exc.message}") from exc
    raise RunFailure("INVALID_AGENT_OUTPUT", "The agent proposed an unsupported resource type.")


def _put_request(container, run_id, request):
    raw = dumps(request).encode("utf-8")
    if len(raw) > MAX_AGENT_CONTEXT_BYTES:
        raise RunFailure("AGENT_CONTEXT_TOO_LARGE", "The project context is too large for an agent run.")
    if not re.fullmatch(r"run_[0-9a-f]{32}", run_id):
        raise RunFailure("INTERNAL_ERROR", "The agent run identifier is invalid.")
    filename = f"/tmp/stellaris-agent-{run_id}.json"
    writer = ("import os,sys; n=int(sys.argv[1]); p=sys.argv[2]; "
              "data=sys.stdin.buffer.read(n); "
              "(len(data)==n) or sys.exit(2); "
              "f=open(p,'xb'); f.write(data); f.close(); os.chmod(p,0o600)")
    api = container.client.api
    try:
        created = api.exec_create(container.id, ["python", "-c", writer, str(len(raw)), filename],
                                  stdin=True, stdout=True, stderr=True, tty=False)
        stream = api.exec_start(created["Id"], socket=True, tty=False)
        sock = getattr(stream, "_sock", stream)
        sock.settimeout(15)
        sock.sendall(raw)
        sock.shutdown(socket.SHUT_WR)
        # Drain the Docker multiplexed stream, but never persist or log its bytes.
        while sock.recv(4096):
            pass
        stream.close()
        if api.exec_inspect(created["Id"]).get("ExitCode") != 0:
            raise RuntimeError("request writer failed")
    except Exception as exc:
        log.warning("Could not transfer project agent request for %s (%s)", run_id, type(exc).__name__)
        raise RunFailure("PROJECT_RUNTIME_UNAVAILABLE", "Could not pass the request to the project agent runtime.", True) from exc
    return filename


def _artifact_text_context(ctx):
    text_types = {"text/plain", "text/markdown", "text/csv", "text/x-python"}
    contents = {}
    total = 0
    for artifact in ctx.snapshot.get("artifacts", []):
        if artifact.get("mime_type") not in text_types or artifact.get("size_bytes", 0) > 512 * 1024:
            continue
        try:
            size, reader, close = ctx.runtime.open_artifact(ctx.project_id, artifact["id"])
            try:
                data = reader.read(size + 1)
            finally:
                close()
        except Exception as exc:
            raise RunFailure("ARTIFACT_UNAVAILABLE", "A selected project artifact could not be read.", True) from exc
        if len(data) != size or hashlib.sha256(data).hexdigest() != artifact.get("sha256"):
            raise RunFailure("ARTIFACT_UNAVAILABLE", "A selected project artifact failed integrity verification.")
        total += len(data)
        if total > 2 * 1024 * 1024:
            raise RunFailure("AGENT_CONTEXT_TOO_LARGE", "Selected text artifacts exceed the agent context limit.")
        contents[artifact["id"]] = data.decode("utf-8")
    return contents


def _stop_agent(container, run_id, signal_number=15):
    if not re.fullmatch(r"run_[0-9a-f]{32}", run_id):
        return
    pid_file = f"/tmp/stellaris-agent-{run_id}.pid"
    request_file = f"/tmp/stellaris-agent-{run_id}.json"
    script_file = "/opt/stellaris/agent_runner.py"
    code = ("import os,signal,sys; p,expected_script,expected_request,n=sys.argv[1:]; "
            "raw=open(p).read().strip() if os.path.exists(p) else ''; "
            "pid=int(raw) if raw.isdigit() else 0; "
            "args=open('/proc/%d/cmdline'%pid,'rb').read().split(bytes([0])) if pid>1 else []; "
            "ok=expected_script.encode() in args and expected_request.encode() in args; "
            "ok and os.kill(pid,int(n))")
    try:
        container.exec_run(["python", "-c", code, pid_file, script_file, request_file, str(signal_number)],
                           stdout=False, stderr=False, demux=True)
    except Exception:
        log.warning("Could not signal project agent process for %s", run_id)


def _terminate_agent(container, run_id):
    """Stop only this run's validated runner PID, escalating after a short grace period."""
    _stop_agent(container, run_id, 15)
    time.sleep(1)
    _stop_agent(container, run_id, 9)


def _cleanup_agent_files(container, run_id):
    if not re.fullmatch(r"run_[0-9a-f]{32}", run_id):
        return
    paths = [f"/tmp/stellaris-agent-{run_id}.json", f"/tmp/stellaris-agent-{run_id}.pid"]
    code = "import os,sys; [os.path.exists(p) and os.unlink(p) for p in sys.argv[1:]]"
    try:
        container.exec_run(["python", "-c", code, *paths], stdout=False, stderr=False)
    except Exception:
        log.warning("Could not clean temporary project agent files for %s", run_id)


def cleanup_lost_agents(runtime, project_runs):
    """Stop and clean agent processes orphaned by an API restart.

    `project_runs` contains (project_id, run_id) pairs recovered as interrupted.
    Only the labelled container for that project and the run-specific PID are touched.
    """
    for project_id, run_id in project_runs:
        if not isinstance(project_id, str) or not re.fullmatch(r"prj_[0-9a-f]{32}", project_id):
            continue
        try:
            container = runtime.client().containers.get(f"stellaris-{project_id}")
            if (container.labels.get("stellaris.project_id") != project_id
                    or container.labels.get("stellaris.role") != "project-runtime"):
                log.warning("Skipping orphaned agent cleanup for mislabeled project %s", project_id)
                continue
            _terminate_agent(container, run_id)
            _cleanup_agent_files(container, run_id)
        except Exception as exc:
            log.warning("Could not clean orphaned project agent %s (%s)", run_id, type(exc).__name__)


def _run_agent(ctx, request, env, claim_ids, agent_metadata, provider, model_id):
    runtime = ctx.runtime
    container = None
    try:
        runtime.ensure(ctx.project_id, create_volume=False, wait_healthy=True)
        container = runtime.client().containers.get(f"stellaris-{ctx.project_id}")
        if container.labels.get("stellaris.project_id") != ctx.project_id or container.labels.get("stellaris.role") != "project-runtime":
            raise RunFailure("PROJECT_RUNTIME_UNAVAILABLE", "The project agent runtime is unavailable.", True)
        container.reload()
        agent_metadata["image_id"] = (container.attrs.get("Image") or "")
        request_path = _put_request(container, ctx.run_id, request)
        command = ["python", "/opt/stellaris/agent_runner.py", request_path]
        created = runtime.client().api.exec_create(container.id, command, environment=env,
                                                   stdout=True, stderr=True, stdin=False, tty=False)
        output = runtime.stream_client().api.exec_start(created["Id"], stream=True, demux=True)
    except RunFailure:
        if container is not None:
            _terminate_agent(container, ctx.run_id)
            _cleanup_agent_files(container, ctx.run_id)
        raise
    except Exception as exc:
        if container is not None:
            _terminate_agent(container, ctx.run_id)
            _cleanup_agent_files(container, ctx.run_id)
        log.warning("Could not start project agent for %s (%s)", ctx.run_id, type(exc).__name__)
        raise RunFailure("PROJECT_RUNTIME_UNAVAILABLE", "The project agent runtime could not be started.", True) from exc

    pending = b""
    delta_index = 0
    total_chars = 0
    deadline = time.monotonic() + MAX_AGENT_SECONDS
    stop_watch = threading.Event()
    timed_out = threading.Event()

    def watchdog():
        while not stop_watch.wait(0.25):
            if ctx.cancel_requested():
                _terminate_agent(container, ctx.run_id)
                return
            if time.monotonic() >= deadline:
                timed_out.set()
                _terminate_agent(container, ctx.run_id)
                return

    watch = threading.Thread(target=watchdog, name=f"stellaris-agent-watch-{ctx.run_id}", daemon=True)
    watch.start()
    saw_complete = False
    try:
        for stdout, stderr in output:
            if ctx.cancel_requested():
                raise RunFailure("CANCELLED", "The agent run was cancelled.")
            if timed_out.is_set():
                raise RunFailure("AGENT_TIMEOUT", "The research agent exceeded its time limit.", True)
            if stderr:
                ctx.log.write("stderr", stderr)
            if not stdout:
                continue
            pending += stdout
            if len(pending) > MAX_AGENT_OUTPUT_CHARS * 8:
                raise RunFailure("AGENT_OUTPUT_TOO_LARGE", "The research agent output exceeded its size limit.")
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except (UnicodeDecodeError, ValueError) as exc:
                    raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an invalid event.") from exc
                if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                    raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an invalid event.")
                if event.get("type") == "delta":
                    if set(event) != {"type", "text"}:
                        raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an invalid text event.")
                    text = event.get("text")
                    if not isinstance(text, str):
                        raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an invalid text delta.")
                    total_chars += len(text)
                    if total_chars > MAX_AGENT_OUTPUT_CHARS:
                        raise RunFailure("AGENT_OUTPUT_TOO_LARGE", "The research agent response exceeded its size limit.")
                    _save_delta(ctx, text, delta_index)
                    delta_index += 1
                elif event.get("type") == "proposal":
                    if set(event) != {"type", "kind", "payload"}:
                        raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an invalid proposal event.")
                    result = _apply_proposal(ctx, event, claim_ids)
                    ctx.log.system(f"Validated {event.get('kind')} proposal: {dumps(result)}")
                    agent_metadata.setdefault("resource_outputs", []).append({"kind": event["kind"], **result})
                elif event.get("type") == "complete":
                    if set(event) != {"type"}:
                        raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an invalid completion event.")
                    saw_complete = True
                elif event.get("type") == "error":
                    if set(event) not in ({"type"}, {"type", "code"}):
                        raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an invalid error event.")
                    code = event.get("code", "ProviderError")
                    if not isinstance(code, str) or not _SAFE_PROVIDER_CODE.fullmatch(code):
                        raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an invalid error code.")
                    raise RunFailure("AGENT_PROVIDER_ERROR", f"Configured model request failed ({code}).",
                                     code in _RETRYABLE_PROVIDER_CODES)
                elif event.get("type") == "provenance":
                    if set(event) != {"type", "python_version", "packages", "tool_version", "provider", "model"}:
                        raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned invalid provenance.")
                    if (not isinstance(event["python_version"], str) or
                            not isinstance(event["packages"], dict) or
                            any(not isinstance(k, str) or not isinstance(v, str) for k, v in event["packages"].items()) or
                            not isinstance(event["tool_version"], str) or event["provider"] != provider
                            or event["model"] != model_id):
                        raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned invalid provenance.")
                    agent_metadata.update({k: event[k] for k in ("python_version", "packages", "tool_version")})
                else:
                    raise RunFailure("INVALID_AGENT_STREAM", "The project agent returned an unsupported event.")
        if ctx.cancel_requested():
            raise RunFailure("CANCELLED", "The agent run was cancelled.")
        if timed_out.is_set():
            raise RunFailure("AGENT_TIMEOUT", "The research agent exceeded its time limit.", True)
        if pending:
            raise RunFailure("INVALID_AGENT_STREAM", "The project agent ended with an incomplete event.")
        if not saw_complete:
            raise RunFailure("AGENT_RUNTIME_LOST", "The project agent ended before completing its response.", True)
        result = runtime.client().api.exec_inspect(created["Id"])
        if result.get("ExitCode") != 0:
            raise RunFailure("AGENT_PROVIDER_ERROR", "The configured model request failed.", True)
        return claim_ids
    finally:
        stop_watch.set()
        watch.join(timeout=1)
        if not saw_complete or ctx.cancel_requested() or timed_out.is_set():
            _terminate_agent(container, ctx.run_id)
        _cleanup_agent_files(container, ctx.run_id)


def handle_agent_run(ctx):
    with _project_lock(ctx.project_id):
        provider, model_id, provider_env, error_code, error_message = selected_model_config()
        if error_code:
            _finish_message(ctx, status="interrupted")
            raise RunFailure(error_code, error_message)

        user_id = ctx.input["user_message_id"]
        row = ctx.conn.execute("SELECT doc FROM messages WHERE id = ? AND project_id = ?",
                               (user_id, ctx.project_id)).fetchone()
        if row is None:
            _finish_message(ctx, status="interrupted")
            raise RunFailure("RESOURCE_NOT_FOUND", "The submitted user message could not be loaded.")
        request = {"project_id": ctx.project_id, "run_id": ctx.run_id,
                   "snapshot": ctx.snapshot, "message": json.loads(row["doc"]),
                   "artifact_text": _artifact_text_context(ctx)}
        if ctx.cancel_requested():
            _finish_message(ctx, status="interrupted")
            ctx.finish("cancelled", summary="Cancelled.")
            return
        ctx.progress("research", 0.1, "Running the project research agent.", force=True)
        claim_ids = []
        agent_metadata = {"provider": provider, "model": model_id}
        try:
            _run_agent(ctx, request, provider_env, claim_ids, agent_metadata, provider, model_id)
            self = ctx.conn.execute("SELECT doc FROM messages WHERE id = ?", (ctx.input["assistant_message_id"],)).fetchone()
            answer = json.loads(self["doc"])["content_markdown"]
            if not answer.strip():
                raise RunFailure("EMPTY_AGENT_RESPONSE", "The research agent returned no visible response.", True)
            provenance = ctx.stage_text(dumps({"version": 1, "kind": "agent", "provider": provider,
                                               "model": model_id, "run_id": ctx.run_id,
                                               "execution_runtime": {"kind": "project_container", **agent_metadata},
                                               "accepted_context": ctx.snapshot}),
                                        filename="agent-provenance.json", mime_type="application/json",
                                        kind="environment", origin="generated")
            ctx.log.system("Research agent completed successfully.")
            retained_log = ctx.stage_text(ctx.log.text(), filename="agent-run-log.txt", mime_type="text/plain",
                                          kind="log", origin="generated")

            def publish(_conn):
                row = _conn.execute("SELECT doc FROM messages WHERE id = ? AND project_id = ?",
                                    (ctx.input["assistant_message_id"], ctx.project_id)).fetchone()
                message = json.loads(row["doc"])
                message["status"] = "complete"
                message["claim_ids"] = claim_ids
                message["updated_at"] = now_ts()
                _conn.execute("UPDATE messages SET doc = ? WHERE id = ?", (dumps(message), message["id"]))
                record_event(_conn, ctx.project_id, "message.updated", {"message": message}, run_id=ctx.run_id)

            ctx.finish("succeeded", summary=answer[:500], publish=publish, retained=[retained_log],
                       provenance=provenance)
            return
        except RunFailure as exc:
            _finish_message(ctx, status="interrupted")
            if exc.code == "CANCELLED":
                ctx.finish("cancelled", summary="Cancelled.")
                return
            raise
        except Exception as exc:
            _finish_message(ctx, status="interrupted")
            log.warning("Agent run %s failed (%s)", ctx.run_id, type(exc).__name__)
            raise RunFailure("AGENT_PROVIDER_ERROR", "The configured model request failed.", True) from exc

