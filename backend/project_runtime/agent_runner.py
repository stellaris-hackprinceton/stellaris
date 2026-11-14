"""One-shot Deep Agents runner for a single project-scoped request."""

import asyncio
import json
import math
import os
import re
import sys
import threading
import time
from collections import Counter
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
from report_agent import create_report_agent, extract_final_analysis

_write_lock = threading.Lock()
_SAFE_ERROR_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
AGENT_RECURSION_LIMIT = 200
MAX_TOOL_CHARS = 12_000
INGEST_WAIT_S = 400
MAX_AGENT_INGESTIONS = 2
TOOL_REPLY_WAIT_S = 480
MAX_BACKEND_TOOL_REQUESTS = 100
_TOKEN = re.compile(r"[a-z0-9]+")


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
    "Design experiments that fit the user's question and the actual project materials and execution capabilities. "
    "A plan alone is not an executed analysis. Generated code must be saved as an immutable implementation and "
    "run through the isolated analysis tool. Use only the runtimes and inputs the backend accepts; report missing "
    "dependencies or unavailable modalities honestly. Never invent observations or claim execution without a "
    "successful run and actual output artifacts.")


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
        problems.append("input_artifact_ids must contain actual project artifact IDs from the supplied project_artifacts "
                        "or list_materials artifact_id fields (not catalog file IDs). Use [] when no input is needed.")
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


def _unversioned(arxiv_key):
    return re.sub(r"v\d+$", "", arxiv_key or "")


def _outline(entry):
    paper = entry["paper"]
    lines = [f"Full text of {entry['title']!r} (cite as source_id {entry['citation_key']!r}). Sections:"]
    for section in paper["sections"]:
        lines.append(f"- {section['id']}: {section['locator']} {section['title']} ({len(section['paragraphs'])} paragraphs)")
    if paper.get("references"):
        lines.append(f"{len(paper['references'])} bibliography entries extracted.")
    return "\n".join(lines)[:MAX_TOOL_CHARS]


def make_tools(artifact_ids=None, papers=None, run_id=""):
    known_artifacts = set(artifact_ids or ())
    papers = dict(papers or {})
    search_count = 0
    proposal_count = 0
    ingest_count = 0
    tool_request_count = 0

    def backend_tool(name, payload):
        """Synchronous, run-correlated request to the trusted API process."""
        nonlocal tool_request_count
        if tool_request_count >= MAX_BACKEND_TOOL_REQUESTS:
            return {"ok": False, "error": "The per-run backend tool limit has been reached."}
        tool_request_count += 1
        request_id = f"{run_id}-{tool_request_count}"
        emit({"type": "tool_request", "request_id": request_id, "name": name, "payload": payload})
        path = f"/tmp/stellaris-agent-{request_id}-reply.json"
        deadline = time.monotonic() + TOOL_REPLY_WAIT_S
        while not os.path.exists(path):
            if time.monotonic() >= deadline:
                return {"ok": False, "error": "The backend tool request timed out."}
            time.sleep(.2)
        try:
            with open(path, encoding="utf-8") as fh:
                reply = json.load(fh)
            if not isinstance(reply, dict) or set(reply) - {"ok", "result", "error"}:
                return {"ok": False, "error": "The backend returned an invalid tool response."}
            return reply
        except (OSError, ValueError):
            return {"ok": False, "error": "The backend tool response could not be read."}

    def find_paper(source):
        source = (source or "").strip()
        if source in papers:
            return papers[source]
        for entry in papers.values():
            key = entry["citation_key"]
            if source == key or (key.startswith("arxiv:") and source.startswith("arxiv:")
                                 and _unversioned(key) == _unversioned(source)):
                return entry
        return None

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
    def read_paper(source: str, section: str = "", start_paragraph: int = 1) -> str:
        """Read supplied full text by section ID/title, returning exact paragraph locators."""
        entry = find_paper(source)
        if entry is None:
            return f"No full text is available for {source!r}."
        if not section.strip():
            return _outline(entry)
        wanted = section.strip().lower()
        match = next((s for s in entry["paper"]["sections"] if wanted in
                      (s["id"].lower(), (s.get("number") or "").lower(), s["locator"].lower(), s["title"].lower(),
                       s["locator"].lstrip("§").lower())), None)
        if match is None:
            return f"No section {section!r}. " + _outline(entry)
        out, used = [f"{match['locator']} {match['title']}"], 0
        start = max(1, int(start_paragraph or 1))
        for i, para in enumerate(match["paragraphs"][start - 1:], start=start):
            line = f"[{para['locator']}] {para['text']}"
            if used + len(line) > MAX_TOOL_CHARS:
                out.append(f"(Continue with start_paragraph={i}.)")
                break
            out.append(line); used += len(line)
        return "\n\n".join(out)

    @tool
    def search_paper(query: str, source: str = "") -> str:
        """Deterministic keyword search in supplied full-text paragraphs; results include exact locators."""
        entries = [find_paper(source)] if source.strip() else list(papers.values())
        entries = [e for e in entries if e]
        terms = _TOKEN.findall(query.lower())
        if not entries:
            return "No full-text papers are available."
        if not terms:
            return "The query has no searchable terms."
        docs = [(e, p, Counter(_TOKEN.findall(p["text"].lower())))
                for e in entries for s in e["paper"]["sections"] for p in s["paragraphs"]]
        n = len(docs); avg = sum(sum(c.values()) for _, _, c in docs) / max(1, n)
        df = Counter(t for _, _, c in docs for t in set(terms) if t in c)
        scores = []
        for entry, para, counts in docs:
            length = sum(counts.values())
            score = sum(math.log(1 + (n - df[t] + .5) / (df[t] + .5)) * counts[t] * 2.5 /
                        (counts[t] + 1.5 * (.25 + .75 * length / max(avg, 1))) for t in terms if counts[t])
            if score: scores.append((score, entry, para))
        scores.sort(key=lambda x: -x[0])
        return "\n\n".join(f"{e['citation_key']} [{p['locator']}] {p['text'][:800]}" for _, e, p in scores[:8])[:MAX_TOOL_CHARS] or "No paragraphs matched."

    @tool
    def request_full_text(arxiv_id: str) -> str:
        """Retrieve full text for one arXiv paper and make it available to the reading tools."""
        nonlocal ingest_count
        arxiv_id = arxiv_id.strip().removeprefix("arxiv:")
        existing = find_paper("arxiv:" + arxiv_id)
        if existing is not None:
            return "Already available. " + _outline(existing)
        if ingest_count >= MAX_AGENT_INGESTIONS:
            return "The per-run full-text retrieval limit has been reached."
        index = ingest_count; ingest_count += 1
        emit({"type": "proposal", "kind": "paper_ingest", "payload": {"arxiv_id": arxiv_id}})
        path = f"/tmp/stellaris-agent-{run_id}-paper-{index}.json"
        deadline = time.monotonic() + INGEST_WAIT_S
        while not os.path.exists(path):
            if time.monotonic() > deadline:
                return "Full-text retrieval timed out; rely on the abstract and say the full paper was not read."
            time.sleep(.5)
        with open(path, encoding="utf-8") as fh:
            delivery = json.load(fh)
        if delivery.get("status") != "ok":
            return f"Full-text retrieval failed ({delivery.get('code')}); the full paper was not read."
        entry = delivery["entry"]; papers[entry["source_id"]] = entry
        return "Full text retrieved and saved. " + _outline(entry)

    @tool
    def propose_experiment(title: str, hypothesis: str, method: Literal["physical", "computational", "hybrid"], protocol_markdown: str,
                           variables_json: str, success_criteria_json: str,
                           input_artifact_ids_json: str, calibration_json: str,
                           limitations_json: str) -> str:
        """Propose an experiment plan; method is physical, computational, or hybrid. variables_json,
        success_criteria_json, input_artifact_ids_json, and limitations_json must be JSON arrays.
        Each variable is {"name","role","description","unit"}; role is independent, dependent, or
        controlled; unit is a string or null. input_artifact_ids_json lists actual project artifact IDs from
        project_artifacts or list_materials, otherwise []. Chat attachment is not required; do not pass catalog
        file IDs. calibration_json must be exactly
        {"mode":"none","assumptions":[...]}: the agent cannot measure reference-length calibration, so
        state in assumptions which reference object of known length the user should calibrate in Studio.
        This tool saves a plan only; it does not create or attach executable code. On success, take its real
        experiment_id and call save_experiment_implementation when fulfilling an experiment design/create request,
        unless the user explicitly asks for a plan only or code is infeasible.
        Do not describe the experiment as runnable until that tool returns a real code_artifact_id. Do not assume
        the project is about bouncing balls. Backend validation is required before the plan is saved.
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
        reply = backend_tool("propose_experiment", payload)
        if not reply.get("ok"):
            return "Experiment was not saved: " + str(reply.get("error", "backend rejected the request"))
        result = reply.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("experiment_id"), str):
            return "The plan may have been saved, but the backend did not return its experiment ID. Do not claim it is runnable."
        return (f"Plan saved as experiment_id {result['experiment_id']} (revision {result.get('revision')}); "
                "no implementation is attached yet. Next call save_experiment_implementation with this exact "
                "experiment_id. Do not say runnable until that tool returns a code_artifact_id. Skip code only "
                "when the user explicitly asked for a plan only or you explain a concrete blocker.")

    @tool
    def save_experiment_implementation(experiment_id: str, language: Literal["python", "javascript", "shell"],
                                       source: str, filename: str) -> str:
        """Save generated executable source as an immutable project artifact and update the experiment revision.
        language selects its runtime. The source must be complete and filename a simple basename. Use the returned
        artifact ID when executing."""
        if not all(isinstance(x, str) for x in (experiment_id, language, source, filename)):
            return "Implementation was not saved: all arguments must be strings."
        try:
            source_size = len(source.encode("utf-8", "strict"))
        except UnicodeEncodeError:
            return "Implementation was not saved: source must be valid UTF-8."
        if source_size > 256 * 1024:
            return "Implementation was not saved: source exceeds 256 KiB."
        reply = backend_tool("save_experiment_implementation", {
            "experiment_id": experiment_id, "runtime": language, "source": source, "filename": filename})
        if not reply.get("ok"):
            return "Implementation was not saved: " + str(reply.get("error", "backend rejected the request"))
        result = reply.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("code_artifact_id"), str):
            return "The backend did not confirm a code artifact ID; do not claim an implementation was attached."
        return "Implementation saved and attached to the experiment: " + json.dumps(result, ensure_ascii=False)

    @tool
    def execute_analysis(experiment_id: str, code_artifact_id: str, input_artifact_ids_json: str = "[]") -> str:
        """Run the saved experiment implementation in a temporary isolated worker. Supply genuine project input
        artifact IDs from project_artifacts/list_materials, or [] if this analysis requires no input. A CSV shown
        in Materials need not be reattached to chat; use its artifact_id, not its catalog id. Returns actual run
        status, bounded logs and outputs;
        failed execution can be corrected by saving a new immutable implementation and retrying.

        Code reads /input/manifest.json (schema stellaris.worker_manifest.v1); inputs[] gives artifact_id and
        read-only path. Read input files only. Write derived files under /output and /output/result.json with
        exactly {"measurements":[],"claims":[],"artifacts":[],"warnings":[]}.
        Measurement entries require local_key, series, quantity, value, unit, time_s, uncertainty
        ({"absolute":number-or-null,"method":string-or-null}), status, evidence, calibration_mode,
        data_origin, assumptions. status is valid, missing, or rejected; missing/rejected values are null and
        assumptions explain why. data_origin is observed, derived, or simulated. calibration_mode must exactly
        equal manifest.calibration.mode; state genuine source-column units in assumptions and never invent a
        conversion. Each evidence item has artifact, frame_index, time_s, row_index; artifact
        is {"input_artifact_id":"..."} or {"output_artifact_key":"..."}. Every measurement needs evidence.
        Claims require local_key, kind (observation/inference/hypothesis), text, measurement_keys, citations,
        evidence, assumptions, limitations. Artifact entries require local_key, relative output path, kind, origin
        (derived/simulated/generated), mime_type, and parents; use kind "dataset" for CSV output (never "table"),
        and parents use those same input/output references. Warnings require code and message. Never invent
        observations or evidence. Use only libraries/commands
        already installed for the selected runtime; network access and package downloads are unavailable."""
        try:
            input_ids = json.loads(input_artifact_ids_json)
        except (TypeError, ValueError):
            return "Execution was not started: input_artifact_ids_json must be a JSON array."
        if not isinstance(input_ids, list) or any(not isinstance(x, str) for x in input_ids):
            return "Execution was not started: input_artifact_ids_json must be a JSON array of artifact IDs."
        reply = backend_tool("execute_analysis", {
            "experiment_id": experiment_id, "code_artifact_id": code_artifact_id,
            "input_artifact_ids": input_ids})
        if not reply.get("ok"):
            return "Execution request failed: " + str(reply.get("error", "backend rejected the request"))
        return "Execution result: " + json.dumps(reply.get("result", {}), ensure_ascii=False)

    @tool
    def list_materials(limit: int = 10, cursor: str = "") -> str:
        """List active project catalog materials for organization. limit is 1-100 (default 10); pass the opaque
        next_cursor from a prior result to continue paging. This lists catalog entries and never moves or edits
        original evidence files."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            return "Material listing failed: limit must be an integer from 1 to 100."
        if not isinstance(cursor, str):
            return "Material listing failed: cursor must be a string."
        reply = backend_tool("list_materials", {"limit": limit, "cursor": cursor})
        if not reply.get("ok"):
            return json.dumps({"error": reply.get("error")}, ensure_ascii=False)
        result = reply.get("result", {})
        rendered = json.dumps(result, ensure_ascii=False)
        if len(rendered) > MAX_TOOL_CHARS:
            return "Material page is too large to return. Retry with a smaller limit (for example 5), using the same cursor."
        for item in result.get("items", []) if isinstance(result, dict) else []:
            if isinstance(item, dict) and isinstance(item.get("artifact_id"), str):
                known_artifacts.add(item["artifact_id"])
        return rendered

    @tool
    def organize_materials(operation_json: str) -> str:
        """Request one project organization operation; operation_json must be exactly one supported operation:
        {"operation":"assign_tags"|"remove_tags","file_id":"...","tags":["lowercase-slug",...]}
        (1-32 slugs, each up to 48 lowercase letters/digits/hyphens);
        {"operation":"create_collection","name":"...","description":"..."?} (name 1-120 chars);
        or {"operation":"add_collection_members"|"remove_collection_members","collection_id":"...",
        "file_ids":["...",...]} (1-100 IDs). list_materials supplies project-scoped file IDs.
        Permission off rejects changes; ask creates a pending request; allow applies it after validation. This only
        organizes tags and collections; it does not move or modify original evidence or artifacts."""
        try:
            payload = json.loads(operation_json)
        except (TypeError, ValueError):
            return "Organization request rejected: operation_json must be a JSON object."
        if not isinstance(payload, dict):
            return "Organization request rejected: operation_json must be a JSON object."
        reply = backend_tool("organize_materials", payload)
        return json.dumps(reply.get("result") if reply.get("ok") else {"error": reply.get("error")}, ensure_ascii=False)

    @tool
    def propose_claim(kind: Literal["observation", "inference", "hypothesis"], text: str, evidence_json: str, citations_json: str, assumptions_json: str,
                      limitations_json: str) -> str:
        """Propose a claim. All JSON arguments must be arrays. Cite arXiv with arxiv:<ID> keys
        and uploaded papers with their source IDs; each citation has source_id, locator, excerpt.
        Copy excerpts verbatim from retrieved material, and use an exact locator from the paper tools.
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

    return [search_arxiv, request_full_text, read_paper, search_paper, propose_experiment,
            save_experiment_implementation, execute_analysis, list_materials, organize_materials, propose_claim]


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
    """Project artifact IDs from chat context, project metadata, and existing experiment inputs."""
    if not isinstance(snapshot, dict):
        return set()
    ids = {a.get("id") for a in snapshot.get("artifacts") or [] if isinstance(a, dict)}
    ids.update(a.get("id") for a in snapshot.get("project_artifacts") or [] if isinstance(a, dict))
    for experiment in snapshot.get("experiments") or []:
        if isinstance(experiment, dict):
            ids.update(x for x in experiment.get("input_artifact_ids") or [] if isinstance(x, str))
    return {x for x in ids if isinstance(x, str) and x}


def create_agent(model, artifact_ids=None, papers=None, run_id="", chat_generation=0):
    scratch = (f"/workspace/scratch/conversations/{chat_generation}" if chat_generation > 0
               else "/workspace/scratch")
    backend = FilesystemBackend(root_dir=scratch, virtual_mode=True)
    system = (
        "You are the research agent for this Stellaris project. Use only supplied project context and material "
        "actually retrieved by tools. Do not invent citations, sources, measurements, or observations. arXiv results "
        "provide metadata and abstracts only. Use read_paper/search_paper for supplied full text and request_full_text for explicit retrieval. Never imply a paper was read unless its text is available through those tools. Use the experiment and claim tools "
        "to request project resources; proposals become public only after backend validation. Distinguish hypotheses, "
        "inferences, and observations: an observation is only something measured in this project and must link "
        "project evidence; a finding from papers is an inference with citations and stated assumptions; an untested "
        "idea is a hypothesis. When citing an arXiv result, use its exact arxiv:<ID> citation_key and excerpts "
        "must be copied verbatim from retrieved abstract or full text, with exact full-text locators. Cite only records the search tool saved, never "
        "rejected candidates; if no relevant paper was saved, say so. " + _EXPERIMENT_SCOPE + " A tool reply "
        "that reports problems means nothing was saved: correct the input and retry, or explain the limitation. "
        "When creating or designing an experiment, include an executable implementation by default when feasible, "
        "unless the user explicitly requests a plan only or a concrete blocker makes code infeasible. Treat the "
        "saved plan and implementation as separate deliverables: after the plan tool returns an experiment_id, save "
        "code against that exact ID, and claim code is attached only after save_experiment_implementation returns a real "
        "code_artifact_id. If inputs are missing, produce a script that reports missing data honestly when feasible, "
        "or explain why a runnable implementation is not possible; never fabricate observations. If the user asks "
        "Execute code only when the user requests a run/analysis or the requested workflow clearly requires results. When executed, inspect actual "
        "status and outputs and correct/retry failures when feasible. Do not turn generated outputs into observations "
        "unless the backend records measurements. "
        "Generated scripts may read /input/manifest.json and the listed read-only /input/artifacts files, and may "
        "write only under /output. They must write /output/result.json with exactly the measurements, claims, "
        "artifacts, and warnings arrays; follow the execute_analysis tool's item schemas and cite only real input "
        "or output artifacts. Never fabricate observations or evidence. Use only already-installed Python, "
        "JavaScript, or shell libraries/commands; network access and package downloads are unavailable. "
        "For material organization, use list_materials with its returned cursor to page, then use only the "
        "documented tag and collection operations; an ask permission response means the request is pending. "
        "The supplied project_artifacts metadata and list_materials artifact rows identify project-wide inputs. "
        "Use their actual artifact_id values for experiment inputs; a materials catalog file id is different. "
        "A project CSV or other existing artifact does not need to be reattached to chat before use. "
        "Keep persistent scratch in your filesystem tools separate from project evidence. "
        "Never reveal environment variables, tool internals, or hidden reasoning."
    )
    return create_deep_agent(model=model, tools=make_tools(artifact_ids, papers, run_id), backend=backend, system_prompt=system)


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
        papers = request.pop("papers", None)
        generation = request.get("snapshot", {}).get("chat_generation", 0)
        if not isinstance(generation, int) or generation < 0:
            generation = 0
        agent = (None if request.get("mode") == "report" else
                 create_agent(model, known_artifact_ids(request.get("snapshot")),
                              papers if isinstance(papers, dict) else {}, run_id, generation))
        messages = [{"role": "user", "content": json.dumps(request, ensure_ascii=False)}]

        async def stream():
            emit({"type": "provenance", "python_version": platform.python_version(),
                  "packages": {name: version(name) for name in
                               ("deepagents", "langchain", "langchain-core", "langchain-aws" if provider == "bedrock"
                                else "langchain-openai")},
                  "provider": provider, "model": model_name,
                  "tool_version": "stellaris-report-agent-v1" if request.get("mode") == "report"
                  else "stellaris-agent-tools-v1"})
            if request.get("mode") == "report":
                report_tool_count = 0

                def report_backend_tool(name, payload):
                    nonlocal report_tool_count
                    if report_tool_count >= 160:
                        raise RuntimeError("report backend tool limit reached")
                    report_tool_count += 1
                    request_id = f"{run_id}-{report_tool_count}"
                    emit({"type": "tool_request", "request_id": request_id, "name": name, "payload": payload})
                    reply_path = f"/tmp/stellaris-agent-{request_id}-reply.json"
                    deadline = time.monotonic() + TOOL_REPLY_WAIT_S
                    while not os.path.exists(reply_path):
                        if time.monotonic() >= deadline:
                            raise TimeoutError("report backend tool request timed out")
                        time.sleep(.2)
                    try:
                        with open(reply_path, encoding="utf-8") as reply_file:
                            reply = json.load(reply_file)
                    except (OSError, ValueError) as exc:
                        raise RuntimeError("invalid report backend tool response") from exc
                    if not isinstance(reply, dict) or set(reply) - {"ok", "result", "error"}:
                        raise RuntimeError("report backend tool request failed")
                    return reply if not reply.get("ok") else reply.get("result", {})

                report_agent, report_messages = create_report_agent(model, request, report_backend_tool)
                result = await report_agent.ainvoke({"messages": report_messages},
                                                    config={"recursion_limit": AGENT_RECURSION_LIMIT})
                emit({"type": "report_analysis", "analysis": extract_final_analysis(result)})
                emit({"type": "complete"})
                return
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
