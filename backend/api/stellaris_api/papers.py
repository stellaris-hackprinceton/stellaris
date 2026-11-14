"""paper_ingest runs: full-text retrieval and extraction (Contracts.md 1.1, ADR-0002).

Flow per run (executor thread, or inline from an agent run):
  1. Document: arXiv runs fetch metadata (export.arxiv.org API) and the e-print (LaTeX source
     archive or PDF) in this trusted process, with bounded size, a host allowlist, and a
     redirect check. The raw bytes become an immutable `reference` artifact. Upload runs use
     the selected, already immutable PDF artifact.
  2. The exact paper_extract_v1 source from the accepted snapshot is published as the run's
     code artifact. The document is parsed only inside the isolated worker (no network).
  3. The worker result is validated like any other (analysis.validate_result), then
     paper.json is strictly validated here before anything is published.
  4. One transaction commits paper.json/paper.txt, a new immutable Source snapshot with
     `full_text`, and the normalized text used for citation verification (paper_texts).
"""

import hashlib
import io
import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from docker.errors import DockerException

from . import analysis, runs, worker
from .db import transaction
from .errors import ApiError, validation_error
from .executor import RunFailure
from .http import now_ts, strict_loads
from .refs import require_one
from .research import publish_source
from .runtime import ArtifactMissing, RuntimeUnavailable
from .validation import Validator, is_int

log = logging.getLogger(__name__)

PIPELINE = {"name": "paper_extract_v1", "version": "1.0.0", "source_file": "paper_extract_v1.py"}
FIELDS = {"kind", "document", "metadata"}
METADATA_FIELDS = {"title", "authors", "doi", "published_at", "url"}
ARXIV_ID = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z][a-z.-]{0,30}(?:\.[A-Z]{2})?/\d{7})(?:v\d{1,3})?$")
ARXIV_HOSTS = {"export.arxiv.org", "arxiv.org"}
USER_AGENT = "StellarisResearch/1.0"
MAX_EPRINT_BYTES = 50 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_PAPER_JSON_BYTES = 16 * 1024 * 1024
FAILURE_WARNINGS = {"DOCUMENT_PARSE_FAILED", "NO_TEXT_LAYER"}
PAPER_KEYS = {"schema", "format", "title", "abstract", "page_count", "sections", "references", "truncated",
              "extraction_notes"}
SECTION_KEYS = {"id", "number", "title", "level", "locator", "paragraphs"}
PARAGRAPH_KEYS = {"id", "locator", "kind", "text"}
_SECTION_ID = re.compile(r"^s[1-9]\d{0,5}$")
_PARAGRAPH_ID = re.compile(r"^s[1-9]\d{0,5}p[1-9]\d{0,5}$")


# -- acceptance ----------------------------------------------------------------------

def valid_arxiv_id(value) -> bool:
    return isinstance(value, str) and bool(ARXIV_ID.fullmatch(value))


def validate_structure(body: dict) -> None:
    v = Validator()
    if "requested_by_run_id" in body:
        v.error("/requested_by_run_id", "requested_by_run_id is set by the backend.")
    v.unknown(body, FIELDS)
    doc = body.get("document")
    if not isinstance(doc, dict) or len(doc) != 1 or not ({"arxiv_id"} >= set(doc) or {"artifact_id"} >= set(doc)):
        v.error("/document", "document must be {arxiv_id} or {artifact_id}.")
    elif "arxiv_id" in doc and not valid_arxiv_id(doc["arxiv_id"]):
        v.error("/document/arxiv_id", "arxiv_id must be an arXiv identifier such as 2401.01234 or 2401.01234v2.")
    elif "artifact_id" in doc:
        v.string(doc, "artifact_id", "/document", min_len=1, max_len=100)
    meta = body.get("metadata")
    if meta is not None:
        if not isinstance(meta, dict):
            v.error("/metadata", "metadata must be an object.")
        elif isinstance(doc, dict) and "artifact_id" not in doc:
            v.error("/metadata", "metadata is only accepted for uploaded documents (artifact_id).")
        else:
            v.unknown(meta, METADATA_FIELDS, "/metadata")
            v.string(meta, "title", "/metadata", required=False, min_len=1, max_len=1000, strip=True)
            v.strings(meta, "authors", "/metadata", required=False, max_items=500, min_len=1, max_len=500)
            for key in ("doi", "published_at", "url"):
                v.string(meta, key, "/metadata", required=False, nullable=True, min_len=1, max_len=2048)
    v.check()


def _pipeline_source(config) -> str:
    path = os.path.join(config.pipelines_dir, PIPELINE["source_file"])
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except OSError:
        raise ApiError(409, "FEATURE_UNAVAILABLE", "The paper_extract_v1 pipeline is not installed.")


def build_snapshot(conn, config, project_id: str, body: dict, requested_by_run_id=None):
    """Returns (run_input, snapshot). Call inside the acceptance transaction."""
    doc = body["document"]
    artifact = None
    if "artifact_id" in doc:
        artifact = require_one(conn, "artifacts", project_id, doc["artifact_id"], "/document/artifact_id")
        if artifact["mime_type"] != "application/pdf" or artifact["kind"] != "document":
            raise validation_error([{"path": "/document/artifact_id",
                                     "message": "artifact_id must be a ready application/pdf document artifact."}])
        artifact = runs._artifact_snapshot(artifact)
        if artifact["size_bytes"] > min(MAX_EPRINT_BYTES, config.max_file_bytes):
            raise ApiError(413, "INPUT_TOO_LARGE", "The uploaded PDF exceeds the 50 MiB ingestion limit.")
    metadata = body.get("metadata")
    if metadata is not None and isinstance(metadata.get("title"), str):
        metadata = {**metadata, "title": metadata["title"].strip()}
    if metadata is not None and metadata.get("published_at") is not None:
        if not re.match(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$", metadata["published_at"]):
            raise validation_error([{"path": "/metadata/published_at",
                                     "message": "published_at must be YYYY, YYYY-MM, or YYYY-MM-DD."}])
    source = _pipeline_source(config)
    run_input = {"kind": "paper_ingest", "document": dict(doc), "metadata": metadata,
                 "requested_by_run_id": requested_by_run_id}
    snapshot = {
        "version": 1, "kind": "paper_ingest", "document": dict(doc), "artifact": artifact, "metadata": metadata,
        "pipeline": {"name": PIPELINE["name"], "version": PIPELINE["version"], "source": source,
                     "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()},
        "parameters": {"max_text_bytes": MAX_TEXT_BYTES},
        "limits": runs._limits(config), "requested_by_run_id": requested_by_run_id, "accepted_at": now_ts(),
    }
    return run_input, snapshot


# -- arXiv retrieval -----------------------------------------------------------------

class _ArxivRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if (parts.scheme != "https" or parts.hostname not in ARXIV_HOSTS or parts.username or parts.password
                or parts.port not in (None, 443)):
            raise RunFailure("FULL_TEXT_UNAVAILABLE", "arXiv redirected to an unexpected endpoint.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_arxiv(url: str, timeout: float):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    response = urllib.request.build_opener(_ArxivRedirects()).open(request, timeout=timeout)
    final = urlsplit(response.geturl())
    if final.scheme != "https" or final.hostname not in ARXIV_HOSTS:
        response.close()
        raise RunFailure("FULL_TEXT_UNAVAILABLE", "arXiv redirected to an unexpected endpoint.")
    return response


def fetch_arxiv_metadata(arxiv_id: str) -> dict:
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": arxiv_id, "max_results": 1})
    try:
        with _open_arxiv(url, 20) as response:
            data = response.read(1_000_001)
    except RunFailure:
        raise
    except Exception as exc:
        raise RunFailure("FULL_TEXT_UNAVAILABLE", f"arXiv metadata could not be retrieved ({type(exc).__name__}).",
                         True) from exc
    if len(data) > 1_000_000:
        raise RunFailure("FULL_TEXT_UNAVAILABLE", "The arXiv metadata response exceeded its size limit.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise RunFailure("FULL_TEXT_UNAVAILABLE", "arXiv returned unreadable metadata.", True) from exc
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    for entry in root.findall("a:entry", ns):
        parts = urlsplit((entry.findtext("a:id", default="", namespaces=ns) or "").strip())
        external_id = parts.path[len("/abs/"):] if parts.path.startswith("/abs/") else ""
        if parts.hostname != "arxiv.org" or not valid_arxiv_id(external_id):
            continue
        title = " ".join((entry.findtext("a:title", default="", namespaces=ns) or "").split())
        if not title:
            continue
        published = entry.findtext("a:published", default="", namespaces=ns) or ""
        doi = (entry.findtext("x:doi", default="", namespaces=ns) or "").strip() or None
        return {"external_id": external_id, "title": title[:1000],
                "authors": [n.strip()[:500] for a in entry.findall("a:author", ns)
                            if (n := a.findtext("a:name", default="", namespaces=ns) or "").strip()][:500],
                "abstract": " ".join((entry.findtext("a:summary", default="", namespaces=ns) or "").split()) or None,
                "published_at": published[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", published) else None,
                "doi": doi[:255] if doi else None, "url": "https://arxiv.org/abs/" + external_id}
    raise RunFailure("FULL_TEXT_UNAVAILABLE", f"arXiv has no record for {arxiv_id}.")


def fetch_eprint(arxiv_id: str, dest: str, max_bytes: int):
    """Download the e-print to dest. Returns (mime_type, extension). Classifies by content."""
    url = "https://export.arxiv.org/e-print/" + arxiv_id
    total = 0
    try:
        with _open_arxiv(url, 60) as response, open(dest, "wb") as fh:
            if response.status != 200:
                raise RunFailure("FULL_TEXT_UNAVAILABLE", f"arXiv returned HTTP {response.status} for the e-print.", True)
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise RunFailure("FULL_TEXT_UNAVAILABLE", "The arXiv e-print exceeds the download size limit.")
                fh.write(chunk)
    except RunFailure:
        raise
    except Exception as exc:
        raise RunFailure("FULL_TEXT_UNAVAILABLE", f"The arXiv e-print could not be retrieved ({type(exc).__name__}).",
                         True) from exc
    with open(dest, "rb") as fh:
        head = fh.read(1024)
    if head.startswith(b"%PDF-"):
        return "application/pdf", "pdf"
    if head[:2] == b"\x1f\x8b":
        return "application/gzip", "gz"
    if len(head) > 262 and head[257:262] == b"ustar":
        return "application/x-tar", "tar"
    raise RunFailure("FULL_TEXT_UNAVAILABLE", "arXiv provides neither LaTeX source nor a PDF for this paper "
                                              "(it may be withdrawn or in an unsupported format).")


# -- worker input ----------------------------------------------------------------------

def _build_input(ctx, work_dir, doc, code_doc, code_bytes):
    manifest = {
        "schema": "stellaris.worker_manifest.v1", "pipeline": PIPELINE["name"],
        "pipeline_version": PIPELINE["version"], "run_id": ctx.run_id,
        "inputs": [{"artifact_id": doc["id"], "kind": doc["kind"], "mime_type": doc["mime_type"],
                    "filename": doc["filename"], "sha256": doc["sha256"], "size_bytes": doc["size_bytes"],
                    "path": f"/input/artifacts/{doc['id']}"}],
        "code": {"artifact_id": code_doc["id"], "sha256": code_doc["sha256"],
                 "path": f"/input/artifacts/{code_doc['id']}"},
        "parameters": ctx.snapshot["parameters"], "output_dir": "/output", "result_path": "/output/result.json",
        "limits": ctx.snapshot["limits"],
    }
    tar_path = os.path.join(work_dir, "input.tar")
    now = int(time.time())
    with tarfile.open(tar_path, mode="w", format=tarfile.PAX_FORMAT) as tar:
        directory = tarfile.TarInfo("artifacts")
        directory.type, directory.mode, directory.mtime = tarfile.DIRTYPE, 0o555, now
        tar.addfile(directory)
        code_member = tarfile.TarInfo(f"artifacts/{code_doc['id']}")
        code_member.size, code_member.mode, code_member.mtime = len(code_bytes), 0o444, now
        tar.addfile(code_member, io.BytesIO(code_bytes))
        member = tarfile.TarInfo(f"artifacts/{doc['id']}")
        member.size, member.mode, member.mtime = doc["size_bytes"], 0o444, now
        digest = hashlib.sha256()
        try:
            size, reader, close = ctx.runtime.open_artifact(ctx.project_id, doc["id"])
        except (RuntimeUnavailable, ArtifactMissing) as exc:
            raise RunFailure("INPUT_UNAVAILABLE", f"Document artifact {doc['id']} could not be read: {exc}", True)
        try:
            if size != doc["size_bytes"]:
                raise RunFailure("INPUT_INTEGRITY_FAILED", "Stored document bytes differ in size from the snapshot.")
            tar.addfile(member, analysis._hash_reader(reader, digest))
        finally:
            close()
        if digest.hexdigest() != doc["sha256"]:
            raise RunFailure("INPUT_INTEGRITY_FAILED", "Stored document bytes do not match the recorded sha256.")
        data = json.dumps(manifest, indent=1, allow_nan=False).encode("utf-8")
        info = tarfile.TarInfo("manifest.json")
        info.size, info.mode, info.mtime = len(data), 0o444, now
        tar.addfile(info, io.BytesIO(data))
    return tar_path


# -- paper.json validation -------------------------------------------------------------

def _opt_str(value, max_len):
    return value is None or (isinstance(value, str) and len(value) <= max_len)


def validate_paper(raw: bytes):
    """Strictly validate untrusted paper.json. Returns (paper, verification_text, locators)."""
    errors = []
    if len(raw) > MAX_PAPER_JSON_BYTES:
        raise analysis.InvalidOutput(["paper.json exceeds its size limit"])
    try:
        paper = strict_loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise analysis.InvalidOutput([f"paper.json is not valid UTF-8 JSON ({exc})"])
    if not isinstance(paper, dict) or set(paper) != PAPER_KEYS:
        raise analysis.InvalidOutput([f"paper.json must have exactly the keys {sorted(PAPER_KEYS)}"])
    if paper["schema"] != "stellaris.paper.v1" or paper["format"] not in ("latex_source", "pdf_text"):
        errors.append("paper.json schema/format is not supported")
    if not _opt_str(paper["title"], 1000) or not _opt_str(paper["abstract"], 200_000):
        errors.append("paper.json title/abstract must be bounded strings or null")
    if not (paper["page_count"] is None or (is_int(paper["page_count"]) and 0 <= paper["page_count"] <= 100_000)):
        errors.append("paper.json page_count must be a nonnegative integer or null")
    if not isinstance(paper["truncated"], bool):
        errors.append("paper.json truncated must be a boolean")
    notes = paper["extraction_notes"]
    if not isinstance(notes, list) or len(notes) > 200 or not all(isinstance(n, str) and len(n) <= 2000 for n in notes):
        errors.append("paper.json extraction_notes must be at most 200 bounded strings")
    refs = paper["references"]
    if not isinstance(refs, list) or len(refs) > 5000 or not all(
            isinstance(r, dict) and set(r) == {"key", "text"} and _opt_str(r["key"], 500)
            and isinstance(r["text"], str) and 0 < len(r["text"]) <= 4000 for r in refs):
        errors.append("paper.json references must be at most 5000 {key, text} entries")
    sections = paper["sections"]
    if not isinstance(sections, list) or not 0 < len(sections) <= 5000:
        raise analysis.InvalidOutput(errors + ["paper.json must contain 1-5000 sections"])
    ids, texts, locators, total, count = set(), [], set(), 0, 0
    for i, s in enumerate(sections):
        p = f"sections/{i}"
        if not isinstance(s, dict) or set(s) != SECTION_KEYS:
            errors.append(f"{p} must have exactly the keys {sorted(SECTION_KEYS)}")
            continue
        if not isinstance(s["id"], str) or not _SECTION_ID.match(s["id"]) or s["id"] in ids:
            errors.append(f"{p}/id must be a unique section id")
            continue
        ids.add(s["id"])
        if (not _opt_str(s["number"], 20) or not isinstance(s["title"], str) or not 0 < len(s["title"]) <= 1000
                or s["level"] not in (1, 2, 3) or not isinstance(s["locator"], str) or not 0 < len(s["locator"]) <= 200):
            errors.append(f"{p} has an invalid number, title, level, or locator")
            continue
        locators.add(s["locator"])
        paras = s["paragraphs"]
        if not isinstance(paras, list) or not 0 < len(paras) <= 20_000:
            errors.append(f"{p}/paragraphs must be a nonempty array")
            continue
        for j, para in enumerate(paras):
            q = f"{p}/paragraphs/{j}"
            if (not isinstance(para, dict) or set(para) != PARAGRAPH_KEYS or not isinstance(para["id"], str)
                    or not _PARAGRAPH_ID.match(para["id"]) or not para["id"].startswith(s["id"] + "p")
                    or para["id"] in ids or para["kind"] not in ("text", "caption")
                    or not isinstance(para["locator"], str) or not 0 < len(para["locator"]) <= 250
                    or not isinstance(para["text"], str) or not 0 < len(para["text"]) <= 200_000):
                errors.append(f"{q} is invalid")
                continue
            ids.add(para["id"])
            locators.add(para["locator"])
            texts.append(para["text"])
            total += len(para["text"].encode("utf-8"))
            count += 1
    if count > 200_000 or total > MAX_TEXT_BYTES + 64 * 1024:
        errors.append("paper.json exceeds the extracted text limits")
    if errors:
        raise analysis.InvalidOutput(errors)
    # Keep a delimiter-indexed map in the auxiliary verification value so the claim validator
    # can bind an excerpt to the cited paragraph (not merely to another location in the paper).
    tagged = []
    for section in sections:
        for para in section["paragraphs"]:
            tagged.append(f"\n⟦{section['locator']}|{para['locator']}⟧\n{para['text']}")
    verification = "\n".join(([paper["abstract"]] if paper["abstract"] else []) + tagged)
    return paper, verification, sorted(locators)


# -- handler -----------------------------------------------------------------------------

def handle_paper_ingest(ctx):
    state = {"doc": None, "code_doc": None, "outcome": None, "meta": None}
    work_dir = tempfile.mkdtemp(prefix=f"{ctx.run_id}-", dir=analysis._run_tmp(ctx.config))
    try:
        _ingest(ctx, work_dir, state)
    except RunFailure as exc:
        if state["doc"] is None and state["code_doc"] is None:
            raise  # Nothing published yet; the executor records the failure with the logs.
        ctx.log.system(f"Run failed: {exc.code}: {exc.message}")
        _finish_without_source(ctx, state, "failed", {"code": exc.code, "message": exc.message,
                                                      "retryable": exc.retryable})
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _safe_name(arxiv_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]", "_", arxiv_id)


def _ingest(ctx, work_dir, state):
    snap = ctx.snapshot
    staged = []
    if "arxiv_id" in snap["document"]:
        arxiv_id = snap["document"]["arxiv_id"]
        ctx.progress("retrieving", 0.05, f"Retrieving arXiv {arxiv_id}.", force=True)
        state["meta"] = fetch_arxiv_metadata(arxiv_id)
        ctx.log.system(f"arXiv metadata retrieved for {state['meta']['external_id']}: {state['meta']['title']}")
        path = os.path.join(work_dir, "eprint.bin")
        mime, ext = fetch_eprint(arxiv_id, path, min(MAX_EPRINT_BYTES, ctx.config.max_file_bytes))
        ctx.log.system(f"arXiv e-print retrieved as {mime} ({os.path.getsize(path)} bytes).")
        staged.append(ctx.stage(local_path=path, filename=f"arxiv-{_safe_name(state['meta']['external_id'])}.{ext}",
                                mime_type=mime, kind="document", origin="reference"))
    if ctx.cancel_requested():
        raise RunFailure("CANCELLED", "Cancelled before extraction.")
    code_bytes = snap["pipeline"]["source"].encode("utf-8")
    code_path = os.path.join(work_dir, "pipeline.py")
    with open(code_path, "wb") as fh:
        fh.write(code_bytes)
    staged.append(ctx.stage(local_path=code_path, filename=f"{PIPELINE['name']}.py", mime_type="text/x-python",
                            kind="code", origin="generated"))
    committed = ctx.commit_now(staged)
    state["code_doc"] = committed[-1]
    state["doc"] = committed[0] if len(committed) == 2 else snap["artifact"]
    doc, code_doc = state["doc"], state["code_doc"]
    ctx.log.system(f"Document artifact {doc['id']}; extraction code artifact {code_doc['id']}.")

    tar_path = _build_input(ctx, work_dir, doc, code_doc, code_bytes)
    ctx.progress("extracting", 0.3, "Extracting text in an isolated worker.", force=True)
    try:
        outcome = worker.run_worker(
            ctx.runtime, ctx.config, project_id=ctx.project_id, run_id=ctx.run_id, input_tar=tar_path,
            argv=["python", "-I", "-B", f"/input/artifacts/{code_doc['id']}"], work_dir=work_dir,
            on_output=lambda stream, data: ctx.log.write(stream, data), cancel_requested=ctx.cancel_requested)
    except worker.WorkerUnavailable as exc:
        log.error("Run %s: %s", ctx.run_id, exc)
        raise RunFailure("WORKER_UNAVAILABLE", "The isolated worker could not be started.", True)
    except DockerException as exc:
        log.error("Run %s: Docker failure during extraction: %s", ctx.run_id, exc)
        raise RunFailure("WORKER_LOST", "Contact with the isolated worker was lost.", True)
    state["outcome"] = outcome
    ctx.log.system(f"Worker finished: {outcome.status} (exit code {outcome.exit_code}, {outcome.wall_time_s} s)."
                   + (f" {outcome.message}" if outcome.message else ""))
    if outcome.status != "completed":
        failure = analysis.EXECUTION_FAILURES[outcome.status]
        if failure is None:
            _finish_without_source(ctx, state, "cancelled", None)
            return
        raise RunFailure(failure[0], outcome.message or "Extraction failed.", failure[1])

    ctx.progress("validating", 0.8, "Validating the extracted text.", force=True)
    try:
        if "result.json" not in outcome.files:
            raise analysis.InvalidOutput(["/output/result.json is missing"])
        with open(outcome.files["result.json"], "rb") as fh:
            raw = fh.read(analysis.MAX_RESULT_BYTES + 1)
        result = analysis.validate_result(raw, outcome.files, outcome.rejected,
                                          input_ids={doc["id"], code_doc["id"]}, calibration_mode="none",
                                          simulated=False, source_ids=set())
        failure = next((w for w in result["warnings"] if w["code"] in FAILURE_WARNINGS), None)
        if failure:
            raise RunFailure(failure["code"], failure["message"])
        if result["measurements"] or result["claims"]:
            raise analysis.InvalidOutput(["paper extraction must not report measurements or claims"])
        by_key = {a["local_key"]: a for a in result["artifacts"]}
        if set(by_key) != {"paper_json", "paper_txt"} or by_key["paper_json"]["path"] != "paper.json" \
                or by_key["paper_json"]["mime_type"] != "application/json" or by_key["paper_txt"]["mime_type"] != "text/plain":
            raise analysis.InvalidOutput(["the result must declare exactly paper.json and paper.txt"])
        with open(outcome.files["paper.json"], "rb") as fh:
            paper, verification, locators = validate_paper(fh.read(MAX_PAPER_JSON_BYTES + 1))
    except analysis.InvalidOutput as exc:
        for line in exc.errors[:50]:
            ctx.log.system(f"invalid output: {line}")
        raise RunFailure("INVALID_OUTPUT", "The extraction result was rejected: " + str(exc)[:900])
    for w in result["warnings"]:
        ctx.warn(w["code"], w["message"])

    ctx.progress("publishing", 0.9, "Storing extracted text and the source snapshot.", force=True)
    try:
        outputs = {key: ctx.stage(local_path=outcome.files[a["path"]], filename=a["filename"], mime_type=a["mime_type"],
                                  kind="document", origin="derived", parent_artifact_ids=[doc["id"], code_doc["id"]])
                   for key, a in by_key.items()}
    except ApiError as exc:
        ctx.discard_staged()
        raise RunFailure("INVALID_OUTPUT", f"An extraction output was rejected: {exc.message}")

    meta = state["meta"]
    user_meta = snap["metadata"] or {}
    sections = paper["sections"]
    full_text = {"format": paper["format"], "text_artifact_id": outputs["paper_json"]["id"],
                 "ingest_run_id": ctx.run_id, "section_count": len(sections), "page_count": paper["page_count"],
                 "truncated": paper["truncated"], "license_url": None}
    if meta is not None:
        source_fields = {"provider": "arxiv", "external_id": meta["external_id"], "title": meta["title"],
                         "authors": meta["authors"], "url": meta["url"], "doi": meta["doi"],
                         "published_at": meta["published_at"], "abstract": meta["abstract"]}
    else:
        title = user_meta.get("title") or (paper["title"] or "").strip()[:1000] or doc["filename"]
        source_fields = {"provider": "manual", "external_id": None, "title": title,
                         "authors": user_meta.get("authors") or [],
                         "url": user_meta.get("url") or f"/api/v1/projects/{ctx.project_id}/artifacts/{doc['id']}/content",
                         "doi": user_meta.get("doi"), "published_at": user_meta.get("published_at"),
                         "abstract": paper["abstract"]}
        if not user_meta.get("title") and paper["title"]:
            ctx.warn("UNTRUSTED_METADATA", "The source title was taken from the PDF's embedded metadata.")
    paragraphs = sum(len(s["paragraphs"]) for s in sections)
    summary = (f"Full text extracted ({paper['format']}): {len(sections)} sections, {paragraphs} paragraphs"
               + (f", {paper['page_count']} pages" if paper["page_count"] is not None else "")
               + (f", {len(paper['references'])} references" if paper["references"] else "")
               + (". Text was truncated." if paper["truncated"] else "."))
    created = {}

    def publish(conn):
        from .artifacts import commit_artifact
        for staged_output in outputs.values():
            commit_artifact(conn, staged_output)
        created["source"] = publish_source(
            conn, ctx.project_id, retrieval_status="full_text_retrieved", document_artifact_id=doc["id"],
            full_text=full_text, paper_text=(verification, locators), allow_archived=True, **source_fields)
        ctx.log.system(f"Published source snapshot {created['source']['id']}.")

    ctx.log.system(f"Result accepted: {summary}")
    log_staged = ctx.stage_text(ctx.log.text(), filename="run-log.txt", mime_type="text/plain", kind="log",
                                origin="generated")
    prov = _provenance(ctx, state, list(outputs.values()), log_staged, summary)
    prov_staged = ctx.stage_text(json.dumps(prov, indent=1, allow_nan=False), filename="provenance.json",
                                 mime_type="application/json", kind="environment", origin="generated")
    ctx.finish("succeeded", summary=summary, publish=publish, retained=[log_staged], provenance=prov_staged)


def _provenance(ctx, state, outputs, log_staged, note):
    outcome = state["outcome"]
    snap = ctx.snapshot
    return {
        "schema": "stellaris.provenance.v1", "run_id": ctx.run_id, "project_id": ctx.project_id,
        "generated_at": now_ts(),
        "accepted_snapshot": {"accepted_at": snap["accepted_at"], "input": ctx.input, "document": snap["document"],
                              "artifact": snap["artifact"], "metadata": snap["metadata"],
                              "parameters": snap["parameters"], "execution_limits": snap["limits"]},
        "retrieval": ({"provider": "arxiv", "metadata_endpoint": "https://export.arxiv.org/api/query",
                       "eprint_endpoint": "https://export.arxiv.org/e-print/" + snap["document"]["arxiv_id"],
                       "metadata": state["meta"]} if state["meta"] else {"provider": "upload"}),
        "document": ({k: state["doc"][k] for k in ("id", "filename", "mime_type", "sha256", "size_bytes")}
                     if state["doc"] else None),
        "code": ({"artifact_id": state["code_doc"]["id"], "sha256": state["code_doc"]["sha256"],
                  "pipeline": PIPELINE["name"], "pipeline_version": PIPELINE["version"]} if state["code_doc"] else None),
        "execution": {
            "backend": "isolated_python", "worker_image": outcome.image if outcome else None,
            "user": worker.ANALYSIS_USER, "network": "none", "read_only_root": True, "read_only_input": True,
            "started_at": analysis._iso(outcome.started_at) if outcome else None,
            "finished_at": analysis._iso(outcome.finished_at) if outcome else None,
            "wall_time_s": outcome.wall_time_s if outcome else None,
            "exit_code": outcome.exit_code if outcome else None,
            "outcome": outcome.status if outcome else None, "note": note,
        },
        "environment": outcome.versions if outcome else None,
        "outputs": [{"artifact_id": s["id"], "filename": s["filename"], "kind": s["kind"], "origin": s["origin"],
                     "mime_type": s["mime_type"], "sha256": s["sha256"], "size_bytes": s["size_bytes"]} for s in outputs],
        "log_artifact_id": log_staged["id"] if log_staged else None,
        "warnings": ctx.warnings,
        "reproducibility_limits": [
            "arXiv may serve a newer e-print version for unversioned identifiers; the retrieved bytes are retained.",
            "TeX is not compiled: macros, figures, and rendered math are not interpreted.",
            "PDF extraction has no OCR and may misorder multi-column text.",
        ],
    }


def _finish_without_source(ctx, state, status, error):
    ctx.log.flush()
    retained, prov_staged = [], None
    try:
        log_staged = ctx.stage_text(ctx.log.text() or "(no output)\n", filename="run-log.txt",
                                    mime_type="text/plain", kind="log", origin="generated")
        retained.append(log_staged)
        prov = _provenance(ctx, state, [], log_staged, (error or {}).get("message") or status)
        prov_staged = ctx.stage_text(json.dumps(prov, indent=1, allow_nan=False), filename="provenance.json",
                                     mime_type="application/json", kind="environment", origin="generated")
    except (ApiError, RuntimeUnavailable, OSError) as exc:
        log.warning("Run %s: could not stage partial outputs: %s", ctx.run_id, exc)
    summary = "Cancelled." if status == "cancelled" else f"Failed: {error['code']}."
    ctx.finish(status, error=error, summary=summary, retained=retained, provenance=prov_staged)


# -- agent integration -------------------------------------------------------------------

def load_paper(runtime, conn, project_id: str, artifact_id: str):
    row = conn.execute("SELECT doc FROM artifacts WHERE id = ? AND project_id = ?", (artifact_id, project_id)).fetchone()
    if row is None:
        return None, None
    art = json.loads(row["doc"])
    size, reader, close = runtime.open_artifact(project_id, artifact_id)
    try:
        data = reader.read(size + 1)
    finally:
        close()
    if len(data) != art["size_bytes"] or hashlib.sha256(data).hexdigest() != art["sha256"]:
        raise RunFailure("ARTIFACT_UNAVAILABLE", "A paper text artifact failed integrity verification.")
    return json.loads(data), art


def citation_key(source: dict) -> str:
    return f"arxiv:{source['external_id']}" if source["provider"] == "arxiv" and source.get("external_id") \
        else source["id"]


def papers_for_agent(ctx, budget_bytes: int):
    """Full-text sources from the agent snapshot, newest snapshot per paper, within a byte budget.
    Returns ({source_id: entry}, supplied provenance list)."""
    papers, supplied, seen, used = {}, [], set(), 0
    for source in reversed(ctx.snapshot.get("sources", [])):
        full = source.get("full_text")
        if not full:
            continue
        identity = (source["provider"], source.get("external_id") or source.get("document_artifact_id"))
        if identity in seen:
            continue
        seen.add(identity)
        try:
            paper, art = load_paper(ctx.runtime, ctx.conn, ctx.project_id, full["text_artifact_id"])
        except (RuntimeUnavailable, ArtifactMissing, ValueError) as exc:
            raise RunFailure("ARTIFACT_UNAVAILABLE", "A paper text artifact could not be read.", True) from exc
        if paper is None or used + art["size_bytes"] > budget_bytes:
            continue
        used += art["size_bytes"]
        papers[source["id"]] = {"source_id": source["id"], "citation_key": citation_key(source),
                                "title": source["title"], "paper": paper}
        supplied.append({"source_id": source["id"], "text_artifact_id": art["id"], "sha256": art["sha256"]})
    return papers, supplied


def ingest_for_agent(ctx, arxiv_id) -> dict:
    """Run a paper_ingest run inline for an agent run (not through the queue, which could
    deadlock on max_concurrent_runs). Returns a delivery dict for the agent runtime."""
    if not valid_arxiv_id(arxiv_id):
        return {"status": "failed", "code": "VALIDATION_FAILED", "message": "Invalid arXiv identifier."}
    try:
        with transaction(ctx.conn):
            run_input, snapshot = build_snapshot(ctx.conn, ctx.config, ctx.project_id,
                                                 {"kind": "paper_ingest", "document": {"arxiv_id": arxiv_id}},
                                                 requested_by_run_id=ctx.run_id)
            run = runs.insert_run(ctx.conn, ctx.project_id, run_input, snapshot, config=ctx.config)
    except ApiError as exc:
        return {"status": "failed", "code": exc.code, "message": exc.message}
    ctx.log.system(f"Paper ingestion run {run['id']} started for arXiv {arxiv_id}.")
    ctx.manager.execute_now(run["id"])
    doc = json.loads(ctx.conn.execute("SELECT doc FROM runs WHERE id = ?", (run["id"],)).fetchone()["doc"])
    if doc["status"] != "succeeded":
        error = doc.get("error") or {}
        return {"status": "failed", "run_id": run["id"], "code": error.get("code", "FAILED"),
                "message": error.get("message") or doc.get("result_summary") or "Ingestion did not succeed."}
    for row in ctx.conn.execute("SELECT doc FROM sources WHERE project_id = ? ORDER BY created_at DESC, id DESC",
                                (ctx.project_id,)):
        source = json.loads(row["doc"])
        if (source.get("full_text") or {}).get("ingest_run_id") == run["id"]:
            paper, art = load_paper(ctx.runtime, ctx.conn, ctx.project_id, source["full_text"]["text_artifact_id"])
            return {"status": "ok", "run_id": run["id"],
                    "entry": {"source_id": source["id"], "citation_key": citation_key(source),
                              "title": source["title"], "paper": paper},
                    "supplied": {"source_id": source["id"], "text_artifact_id": art["id"], "sha256": art["sha256"]}}
    return {"status": "failed", "run_id": run["id"], "code": "INTERNAL_ERROR", "message": "No source was published."}
