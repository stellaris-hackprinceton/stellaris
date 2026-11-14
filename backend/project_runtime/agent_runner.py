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
AGENT_RECURSION_LIMIT = 200


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


_ARXIV_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "into", "is", "it", "its", "of",
    "on", "or", "not", "andnot", "the", "to", "using", "via", "what", "with", "paper", "papers", "study", "studies",
    # Conversational request words that otherwise become required terms when a user prompt is passed verbatim.
    "let", "lets", "please", "prove", "show", "find", "search", "relevant", "literature", "propose", "simple",
    "about", "we", "me", "i", "our", "some",
}
# Unicode letters and digits (no underscore), so terms such as "Schrödinger" stay whole words.
_ARXIV_WORD = re.compile(r"[^\W_]+")
MAX_ARXIV_TERMS = 6


def _normalized_words(text):
    return [w.casefold() for w in _ARXIV_WORD.findall(text or "")]


def _has_term(text, phrase):
    """Whole-word phrase match in space-padded normalized text; a plain plural "s" on the phrase is accepted,
    so "theorem" matches "theorems" but "work" does not match "workshop"."""
    return f" {phrase} " in text or f" {phrase}s " in text


def arxiv_terms(query):
    """Split a free-text query into required terms: quoted phrases and hyphenated words stay phrases,
    stopwords and arXiv operators are dropped, at most MAX_ARXIV_TERMS terms are kept."""
    terms = []
    chunks = re.findall(r'"([^"]*)"', query) + re.sub(r'"[^"]*"', " ", query).split()
    phrase_count = len(re.findall(r'"([^"]*)"', query))
    for i, chunk in enumerate(chunks):
        words = _normalized_words(chunk if i < phrase_count else chunk.replace("'", "").replace("’", ""))
        # A token or quoted phrase made only of stopwords (e.g. "and/or", "of the") is not a required term.
        if words and not all(w in _ARXIV_STOPWORDS for w in words):
            terms.append(tuple(words))
    unique = list(dict.fromkeys(terms))
    return unique[:MAX_ARXIV_TERMS]


def build_arxiv_query(terms):
    """arXiv's API treats unqualified space-separated words as alternatives after the first field prefix,
    so `all:work energy theorem` matched unrelated papers about any one word. Require every term instead."""
    return " AND ".join("all:" + (f'"{" ".join(t)}"' if len(t) > 1 else t[0]) for t in terms)


def parse_arxiv_entries(data, terms):
    """Parse an Atom response into (selected, rejected) records. A record is selected only when every
    required term appears in its retrieved title or abstract; others (for example, matched only via
    author or comment fields) are kept as rejected candidates so the retrieval stays auditable."""
    root = ET.fromstring(data)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    selected, rejected = [], []
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
        authors = [a.findtext("a:name", default="", namespaces=ns) for a in entry.findall("a:author", ns)]
        record = {"title": title, "url": "https://arxiv.org/abs/" + external_id, "external_id": external_id,
                  "authors": authors, "published_at": _published_day(
                      entry.findtext("a:published", default="", namespaces=ns)), "abstract": abstract}
        text = " " + " ".join(_normalized_words(title + " " + abstract)) + " "
        missing = [" ".join(t) for t in terms if not _has_term(text, " ".join(t))]
        if missing:
            rejected.append({"record": record, "missing_terms": missing})
        else:
            selected.append(record)
    return selected, rejected


_EXPERIMENT_SCOPE = (
    "Supported experiments: physical experiments recorded with the user's webcam/phone camera or uploaded video "
    "or images (the MVP workflow is a bouncing or dropped ball tracked across frames), plus CSV/text data, analyzed "
    "by isolated Python. Do not assume lab equipment such as air tracks, photogates, force sensors, or "
    "motion sensors is available; if a topic needs them, say so and propose a camera-based alternative. "
    "The built-in automatic video pipeline (bouncing_ball_v1) only measures bouncing-ball motion, bounce heights, "
    "and energy ratios; it is NOT gesture recognition or finger counting, and its object hint is metadata that "
    "does not select a detector. Custom analysis requires a supplied implementation run through the existing "
    "python_analysis_v1 pipeline with a ready code artifact. You may research and design other experiments, but "
    "state that a plan is not an executable analysis and that a matching implementation is still needed; never "
    "promise arbitrary computer vision from a target's name.")


def experiment_problems(payload, known_artifacts):
    """Mirror backend experiment validation (stellaris_api/experiments.py) so a malformed plan returns to the
    model as a correctable tool error instead of failing the whole run. The backend stays authoritative.
    The agent may not supply reference-length calibration: it cannot see frames, so pixel points or lengths
    would be invented. It must use mode "none" and state what calibration the user still needs to add."""
    problems = []
    if not isinstance(payload["title"], str) or not 1 <= len(payload["title"].strip()) <= 200:
        problems.append("title must contain 1-200 characters.")
    variables = payload["variables"]
    if len(variables) > 100:
        problems.append("variables must contain at most 100 objects.")
    for i, item in enumerate(variables):
        if not isinstance(item, dict) or set(item) != {"name", "role", "description", "unit"}:
            problems.append(f"variables[{i}] must be an object with exactly name, role, description, and unit.")
            continue
        if not isinstance(item["name"], str) or not 1 <= len(item["name"].strip()) <= 200:
            problems.append(f"variables[{i}].name must contain 1-200 characters.")
        if item["role"] not in ("independent", "dependent", "controlled"):
            problems.append(f"variables[{i}].role must be independent, dependent, or controlled.")
        if not isinstance(item["description"], str):
            problems.append(f"variables[{i}].description must be a string.")
        if item["unit"] is not None and not (isinstance(item["unit"], str) and 1 <= len(item["unit"]) <= 50):
            problems.append(f"variables[{i}].unit must be a 1-50 character string or null.")
    for field in ("success_criteria", "limitations"):
        if any(not isinstance(x, str) for x in payload[field]):
            problems.append(f"{field} must contain only strings.")
    ids = payload["input_artifact_ids"]
    if any(not isinstance(x, str) or not x for x in ids) or len(set(map(str, ids))) != len(ids):
        problems.append("input_artifact_ids must be unique artifact ID strings.")
    elif any(x not in known_artifacts for x in ids):
        problems.append("input_artifact_ids may only contain IDs of files attached to this request; use [] when "
                        "the user has not provided the recording yet.")
    cal = payload["calibration"]
    mode = cal.get("mode")
    if mode == "reference_length":
        problems.append('calibration mode "reference_length" cannot be proposed by the agent because its pixel '
                        'points must be measured by the user on an attached frame. Use {"mode":"none","assumptions":'
                        '[...]} and describe the reference object of known length the user should add in Studio.')
    elif mode != "none":
        problems.append('calibration.mode must be "none" (the only agent-proposable mode); for example '
                        '{"mode":"none","assumptions":["Measurements stay in pixels until the user adds a '
                        'reference-length calibration."]}.')
    elif set(cal) != {"mode", "assumptions"} or not isinstance(cal["assumptions"], list) or any(
            not isinstance(x, str) for x in cal["assumptions"]):
        problems.append('calibration must be exactly {"mode":"none","assumptions":[<strings>]}.')
    return problems


def make_tools(artifact_ids=None):
    known_artifacts = set(artifact_ids or ())
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
        """Search arXiv metadata and abstracts; at most three searches per run. Use 2-5 specific keywords;
        every keyword is required, and "quoted phrases" or hyphenated words match as phrases, e.g.
        `"work energy theorem" kinetic`. Only records whose title or abstract contain every term are saved
        as sources; other retrieved records are reported as rejected candidates."""
        nonlocal search_count
        if search_count >= 3:
            return "The per-run arXiv search limit has been reached."
        query = query.strip()
        if not query or len(query) > 400:
            return "Query must contain 1 to 400 characters."
        terms = arxiv_terms(query)
        if not terms:
            return "Query needs at least one specific keyword besides stopwords."
        search_count += 1
        search_query = build_arxiv_query(terms)
        params = urllib.parse.urlencode({"search_query": search_query, "start": 0, "max_results": 3,
                                         "sortBy": "relevance", "sortOrder": "descending"})
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
            selected, rejected = parse_arxiv_entries(data, terms)
        except Exception:
            return "arXiv search is temporarily unavailable. No source was saved."
        return _record_arxiv_results(query, search_query, selected, rejected)

    def _record_arxiv_results(query, search_query, selected, rejected):
        # Provenance of every retrieved candidate, including rejected ones, is recorded by the backend.
        emit({"type": "retrieval", "provider": "arxiv", "query": query, "search_query": search_query,
              "candidates": [{"external_id": r["external_id"], "title": r["title"][:300], "selected": True,
                              "missing_terms": []} for r in selected]
              + [{"external_id": c["record"]["external_id"], "title": c["record"]["title"][:300],
                  "selected": False, "missing_terms": c["missing_terms"]} for c in rejected]})
        found = []
        for payload in selected:
            if not propose("source", payload):
                break
            found.append({"title": payload["title"], "url": payload["url"], "abstract": payload["abstract"],
                          "citation_key": "arxiv:" + payload["external_id"]})
        notes = [{"title": c["record"]["title"], "missing_terms": c["missing_terms"]} for c in rejected]
        if not found:
            return ("No retrieved arXiv record contained every search term in its title or abstract; no source was "
                    "saved. Do not cite these candidates. Rejected candidates: " + json.dumps(notes, ensure_ascii=False))
        message = ("Retrieved arXiv title and abstract metadata; full papers were not inspected. Records proposed for "
                   "backend validation: " + json.dumps(found, ensure_ascii=False))
        if notes:
            message += " Rejected candidates (not saved; do not cite): " + json.dumps(notes, ensure_ascii=False)
        return message

    @tool
    def propose_experiment(title: str, hypothesis: str, method: Literal["physical", "computational", "hybrid"], protocol_markdown: str,
                           variables_json: str, success_criteria_json: str,
                           input_artifact_ids_json: str, calibration_json: str,
                           limitations_json: str) -> str:
        """Propose an experiment plan; method is physical, computational, or hybrid. variables_json,
        success_criteria_json, input_artifact_ids_json, and limitations_json must be JSON arrays.
        Each variable is {"name","role","description","unit"}; role is independent, dependent, or
        controlled; unit is a string or null. input_artifact_ids_json lists only IDs of files attached
        to this request, otherwise []. calibration_json must be exactly
        {"mode":"none","assumptions":[...]}: the agent cannot measure reference-length calibration, so
        state in assumptions which reference object of known length the user should calibrate in Studio.
        Plans must fit the supported camera/video experiment scope. Backend validation is required
        before the plan is saved; if this tool reports problems, fix them and call it again.
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
        problems = experiment_problems(payload, known_artifacts)
        if problems:
            return ("Experiment proposal not sent; nothing was saved. Fix these problems and call "
                    "propose_experiment again: " + " ".join(problems))
        if not propose("experiment", payload):
            return "The per-run proposal limit has been reached."
        return "Experiment proposal sent to the backend for strict validation. Describe it as saved only after backend confirmation in the final response."

    @tool
    def propose_claim(kind: Literal["observation", "inference", "hypothesis"], text: str, evidence_json: str, citations_json: str, assumptions_json: str,
                      limitations_json: str) -> str:
        """Propose a claim. All JSON arguments must be arrays. Cite with arxiv:<ID> keys;
        each citation object must have source_id, locator, and excerpt (use null when unknown).
        Choose kind by what supports the claim:
        - observation: something measured in this project. evidence_json must list at least one
          {"artifact_id", "frame_index", "time_s", "row_index"} reference to a project file.
          Never use observation for findings from papers.
        - inference: a conclusion drawn from cited papers or project evidence. Needs at least one
          citation or evidence item AND at least one assumption in assumptions_json.
        - hypothesis: a proposal not yet tested. No evidence or citations required.
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
        problem = _claim_kind_problem(payload)
        if problem:
            return f"Claim proposal rejected before sending: {problem}"
        if not propose("claim", payload):
            return "The per-run proposal limit has been reached."
        return "Claim proposal sent to the backend for evidence and reference validation."

    return [search_arxiv, propose_experiment, propose_claim]


def _claim_kind_problem(payload):
    """Mirror the backend's claim-kind rules (stellaris_api/research.py publish_claim) so a misfiled
    claim is returned to the model to correct instead of failing the whole run in the backend.
    The backend stays authoritative and still validates everything."""
    kind, evidence = payload["kind"], payload["evidence"]
    if not str(payload["text"]).strip():
        return "text must not be empty."
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("artifact_id"), str) or not item["artifact_id"].strip():
            return "each evidence item must be an object with an artifact_id of a project file."
    if kind == "observation" and not evidence:
        return ("an observation needs at least one evidence reference to a project file. A finding from papers is "
                "an inference: resend it with kind \"inference\", its citations, and at least one assumption.")
    if kind == "inference":
        if not (evidence or payload["citations"]):
            return "an inference needs at least one citation or evidence reference."
        if not [a for a in payload["assumptions"] if isinstance(a, str) and a.strip()]:
            return "an inference must state at least one assumption in assumptions_json."
    return None


def known_artifact_ids(snapshot):
    """Artifact IDs the agent was actually given: request attachments/context and existing plan inputs."""
    if not isinstance(snapshot, dict):
        return set()
    ids = {a.get("id") for a in snapshot.get("artifacts") or [] if isinstance(a, dict)}
    for experiment in snapshot.get("experiments") or []:
        if isinstance(experiment, dict):
            ids.update(x for x in experiment.get("input_artifact_ids") or [] if isinstance(x, str))
    return {x for x in ids if isinstance(x, str) and x}


def create_agent(model, artifact_ids=None):
    backend = FilesystemBackend(root_dir="/workspace/scratch", virtual_mode=True)
    system = (
        "You are the research agent for this Stellaris project. Use only supplied project context and material "
        "actually retrieved by tools. Do not invent citations, sources, measurements, or observations. arXiv results "
        "provide metadata and abstracts only, never imply the full paper was read. Use the experiment and claim tools "
        "to request project resources; proposals become public only after backend validation. Distinguish hypotheses, "
        "inferences, and observations: an observation is only something measured in this project and must link "
        "project evidence; a finding from papers is an inference with citations and stated assumptions; an untested "
        "idea is a hypothesis. When citing an arXiv result, use its exact arxiv:<ID> citation_key and excerpts "
        "must be copied verbatim from its retrieved abstract. Cite only records the search tool saved, never "
        "rejected candidates; if no relevant paper was saved, say so. " + _EXPERIMENT_SCOPE + " A tool reply "
        "that reports problems means nothing was saved: correct the input and retry, or explain the limitation. "
        "Keep persistent scratch in your filesystem tools separate from project evidence. "
        "Never reveal environment variables, tool internals, or hidden reasoning."
    )
    return create_deep_agent(model=model, tools=make_tools(artifact_ids), backend=backend, system_prompt=system)


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
        agent = create_agent(model, known_artifact_ids(request.get("snapshot")))
        messages = [{"role": "user", "content": json.dumps(request, ensure_ascii=False)}]

        async def stream():
            emit({"type": "provenance", "python_version": platform.python_version(),
                  "packages": {name: version(name) for name in
                               ("deepagents", "langchain", "langchain-core", "langchain-aws" if provider == "bedrock"
                                else "langchain-openai")},
                  "provider": provider, "model": model_name,
                  "tool_version": "stellaris-agent-tools-v1"})
            # Explicit step budget: without it this stack falls back to LangGraph's limit of 25 steps
            # (~12 tool rounds), which multi-step requests exceed (GraphRecursionError). The API's
            # MAX_AGENT_SECONDS remains the hard bound on cost.
            async for event in agent.astream_events({"messages": messages}, config={"recursion_limit": AGENT_RECURSION_LIMIT},
                                                    version="v2"):
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
