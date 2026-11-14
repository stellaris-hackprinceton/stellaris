"""One-shot Deep Agents runner for a single project-scoped request."""

import asyncio
import json
import os
import re
import sys
import threading
from typing import Literal
import platform
from importlib.metadata import version
from urllib.parse import urlsplit
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from botocore.config import Config as BotocoreConfig
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrockConverse
from botocore.exceptions import ClientError

_write_lock = threading.Lock()
_SAFE_ERROR_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def emit(event):
    with _write_lock:
        sys.stdout.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def _safe_error_code(exc):
    code = type(exc).__name__
    if isinstance(exc, ClientError):
        candidate = exc.response.get("Error", {}).get("Code")
        if isinstance(candidate, str) and _SAFE_ERROR_CODE.fullmatch(candidate):
            code = candidate
    return code if _SAFE_ERROR_CODE.fullmatch(code) else "ProviderError"


def _published_day(value):
    return value[:10] if isinstance(value, str) and len(value) >= 10 else None


def make_tools():
    search_count = 0
    proposal_count = 0

    def propose(kind, payload):
        nonlocal proposal_count
        if proposal_count >= 20:
            return False
        proposal_count += 1
        emit({"type": "proposal", "kind": kind, "payload": payload})
        return True

    @tool
    def search_arxiv(query: str) -> str:
        """Search arXiv metadata and abstracts. Returns at most three retrieved records."""
        nonlocal search_count
        if search_count >= 3:
            return "The per-run arXiv search limit has been reached."
        search_count += 1
        query = query.strip()
        if not query or len(query) > 400:
            return "Query must contain 1 to 400 characters."
        params = urllib.parse.urlencode({"search_query": f"all:{query}", "start": 0, "max_results": 3})
        url = "https://export.arxiv.org/api/query?" + params
        request = urllib.request.Request(url, headers={"User-Agent": "StellarisResearch/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                final = urlsplit(response.geturl())
                if final.scheme != "https" or final.hostname != "export.arxiv.org":
                    return "arXiv returned an unexpected endpoint. No source was saved."
                if response.status != 200 or response.headers.get("Content-Length", "0").isdigit() and int(
                        response.headers.get("Content-Length", "0")) > 1_000_000:
                    return "arXiv did not return a bounded successful response."
                data = response.read(1_000_001)
            if len(data) > 1_000_000:
                return "arXiv response exceeded the size limit."
            root = ET.fromstring(data)
        except Exception:
            return "arXiv search is temporarily unavailable. No source was saved."
        ns = {"a": "http://www.w3.org/2005/Atom"}
        found = []
        for entry in root.findall("a:entry", ns):
            paper_url = (entry.findtext("a:id", default="", namespaces=ns) or "").strip()
            parts = urlsplit(paper_url)
            if (parts.scheme not in ("http", "https") or parts.hostname != "arxiv.org"
                    or parts.username or parts.password or parts.port is not None or parts.query or parts.fragment
                    or not parts.path.startswith("/abs/")):
                continue
            title = " ".join((entry.findtext("a:title", default="", namespaces=ns) or "").split())
            abstract = " ".join((entry.findtext("a:summary", default="", namespaces=ns) or "").split())
            external_id = parts.path[len("/abs/"):]
            if not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", external_id) or ".." in external_id or "//" in external_id:
                continue
            paper_url = "https://arxiv.org/abs/" + external_id
            authors = [a.findtext("a:name", default="", namespaces=ns) for a in entry.findall("a:author", ns)]
            payload = {"title": title, "url": paper_url, "external_id": external_id,
                       "authors": authors, "published_at": _published_day(
                           entry.findtext("a:published", default="", namespaces=ns)), "abstract": abstract}
            if not propose("source", payload):
                break
            found.append({"title": title, "url": paper_url, "abstract": abstract,
                          "citation_key": "arxiv:" + external_id})
        if not found:
            return "No arXiv records matched."
        return "Retrieved arXiv title and abstract metadata; full papers were not inspected. Records proposed for backend validation: " + json.dumps(found, ensure_ascii=False)

    @tool
    def propose_experiment(title: str, hypothesis: str, method: Literal["physical", "computational", "hybrid"], protocol_markdown: str,
                           variables_json: str, success_criteria_json: str,
                           input_artifact_ids_json: str, calibration_json: str,
                           limitations_json: str) -> str:
        """Propose a plan; method is physical, computational, or hybrid. JSON arguments
        must be JSON arrays for variables, success criteria, input artifact IDs, and limitations;
        calibration must be a JSON object. For no calibration use {"mode":"none","assumptions":[]}.
        Variables use name, role (independent/dependent/controlled), description, unit.
        Backend validation is required before the plan is saved.
        """
        try:
            payload = {"title": title, "hypothesis": hypothesis, "method": method,
                       "protocol_markdown": protocol_markdown, "variables": json.loads(variables_json),
                       "success_criteria": json.loads(success_criteria_json),
                       "input_artifact_ids": json.loads(input_artifact_ids_json),
                       "calibration": json.loads(calibration_json), "limitations": json.loads(limitations_json)}
        except (ValueError, TypeError):
            return "Experiment proposal rejected: JSON arguments were malformed."
        for field in ("variables", "success_criteria", "input_artifact_ids", "limitations"):
            if not isinstance(payload[field], list):
                return f"Experiment proposal rejected: {field}_json must be a JSON array."
        if not isinstance(payload["calibration"], dict):
            return "Experiment proposal rejected: calibration_json must be a JSON object."
        if not propose("experiment", payload):
            return "The per-run proposal limit has been reached."
        return "Experiment proposal sent to the backend for strict validation. Describe it as saved only after backend confirmation in the final response."

    @tool
    def propose_claim(kind: Literal["observation", "inference", "hypothesis"], text: str, evidence_json: str, citations_json: str, assumptions_json: str,
                      limitations_json: str) -> str:
        """Propose a claim. All JSON arguments must be arrays. Cite with arxiv:<ID> keys;
        each citation object must have source_id, locator, and excerpt (use null when unknown).
        """
        try:
            payload = {"kind": kind, "text": text, "evidence": json.loads(evidence_json),
                       "citations": json.loads(citations_json), "assumptions": json.loads(assumptions_json),
                       "limitations": json.loads(limitations_json)}
        except (ValueError, TypeError):
            return "Claim proposal rejected: JSON arguments were malformed."
        for field in ("evidence", "citations", "assumptions", "limitations"):
            if not isinstance(payload[field], list):
                return f"Claim proposal rejected: {field}_json must be a JSON array."
        for citation in payload["citations"]:
            if (not isinstance(citation, dict) or set(citation) != {"source_id", "locator", "excerpt"}
                    or not isinstance(citation["source_id"], str) or not citation["source_id"].strip()
                    or citation["locator"] is not None and not isinstance(citation["locator"], str)
                    or citation["excerpt"] is not None and not isinstance(citation["excerpt"], str)):
                return "Claim proposal rejected: each citation must be an object with source_id, locator, and excerpt."
        if not propose("claim", payload):
            return "The per-run proposal limit has been reached."
        return "Claim proposal sent to the backend for evidence and reference validation."

    return [search_arxiv, propose_experiment, propose_claim]


def create_agent(model):
    backend = FilesystemBackend(root_dir="/workspace/scratch", virtual_mode=True)
    system = (
        "You are the research agent for this Stellaris project. Use only supplied project context and material "
        "actually retrieved by tools. Do not invent citations, sources, measurements, or observations. arXiv results "
        "provide metadata and abstracts only, never imply the full paper was read. Use the experiment and claim tools "
        "to request project resources; proposals become public only after backend validation. Distinguish hypotheses, "
        "inferences, and observations. When citing an arXiv result, use its exact arxiv:<ID> citation_key and excerpts "
        "must be copied verbatim from its retrieved abstract. "
        "Keep persistent scratch in your filesystem tools separate from project evidence. "
        "Never reveal environment variables, tool internals, or hidden reasoning."
    )
    return create_deep_agent(model=model, tools=make_tools(), backend=backend, system_prompt=system)


def main(path):
    with open(path, encoding="utf-8") as request_file:
        request = json.load(request_file)
    os.unlink(path)
    provider = os.environ.get("STELLARIS_MODEL_PROVIDER", "bedrock").strip().lower()
    if provider == "bedrock":
        model_name = os.environ.get("BEDROCK_MODEL_ID", "").strip()
        access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
        region = os.environ.get("AWS_REGION", "").strip()
        session_token = os.environ.get("AWS_SESSION_TOKEN", "").strip()
        if (not all((model_name, access_key, secret_key, region))
                or os.environ.get("AWS_EC2_METADATA_DISABLED") != "true"
                or not re.fullmatch(r"[a-z0-9-]{3,64}", region)
                or not re.fullmatch(r"[A-Za-z0-9.:/_-]{1,256}", model_name)):
            emit({"type": "error"})
            return 2
    elif provider == "openai":
        model_name = os.environ.get("OPENAI_MODEL", "").strip()
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not model_name or not api_key:
            emit({"type": "error"})
            return 2
    else:
        emit({"type": "error"})
        return 2
    run_id = request.get("run_id", "")
    if not re.fullmatch(r"run_[0-9a-f]{32}", run_id):
        emit({"type": "error"})
        return 2
    pid_path = f"/tmp/stellaris-agent-{run_id}.pid"
    with open(pid_path, "x", encoding="ascii") as pid_file:
        pid_file.write(str(os.getpid()))
    try:
        if provider == "bedrock":
            model = ChatBedrockConverse(model_id=model_name, region_name=region,
                                        aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                                        aws_session_token=session_token or None, max_tokens=4096, temperature=0,
                                        config=BotocoreConfig(connect_timeout=8, read_timeout=45,
                                                              retries={"mode": "standard", "max_attempts": 2}))
        else:
            model = ChatOpenAI(model=model_name, api_key=api_key, timeout=45, max_retries=1,
                               max_tokens=4096, temperature=0, streaming=True)
        agent = create_agent(model)
        messages = [{"role": "user", "content": json.dumps(request, ensure_ascii=False)}]

        async def stream():
            emit({"type": "provenance", "python_version": platform.python_version(),
                  "packages": {name: version(name) for name in
                               ("deepagents", "langchain", "langchain-core", "langchain-aws" if provider == "bedrock"
                                else "langchain-openai")},
                  "provider": provider, "model": model_name,
                  "tool_version": "stellaris-agent-tools-v1"})
            async for event in agent.astream_events({"messages": messages}, version="v2"):
                if event.get("event") != "on_chat_model_stream":
                    continue
                chunk = event.get("data", {}).get("chunk")
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    emit({"type": "delta", "text": content})
                elif isinstance(content, list):
                    for part in content:
                        if (isinstance(part, dict) and part.get("type") in (None, "text")
                                and isinstance(part.get("text"), str) and part["text"]):
                            emit({"type": "delta", "text": part["text"]})
            emit({"type": "complete"})

        asyncio.run(stream())
    except Exception as exc:
        # Only the service error code/class is sent; never serialize the exception or its message.
        emit({"type": "error", "code": _safe_error_code(exc)})
        return 1
    finally:
        try:
            os.unlink(pid_path)
        except FileNotFoundError:
            pass
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].startswith("/tmp/stellaris-agent-"):
        raise SystemExit("one bounded runtime request path is required")
    raise SystemExit(main(sys.argv[1]))
