#!/usr/bin/env python3
"""Docker integration checks for full-text paper ingestion (Contracts.md 1.1, ADR-0002).

Run from the host (stdlib only) after rebuilding all images and `docker compose up -d api`:

    cd backend
    docker compose --profile build-only build && docker compose up -d --force-recreate api
    python3 scripts/paper_ingest_test.py                 # includes one live arXiv retrieval
    python3 scripts/paper_ingest_test.py --skip-arxiv    # offline checks only

The PDF fixtures are generated here with known text (test documents, not real papers).
Covers: PDF upload validation, run validation, uploaded-PDF extraction, the no-text-layer
failure, verbatim excerpt/locator verification, and (optionally) arXiv LaTeX-source
ingestion. Creates real projects, which are retained. Does not read any .env file.
"""

import argparse
import hashlib
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
PASSED = []
PAGE_TEXT = [
    ["Coefficient of restitution from video.", "We track a ball and measure apex heights.",
     "The mean height ratio was close to 0.64 in the simulated fixture."],
    ["Methods: background subtraction isolates the moving ball.", "Perspective error is not corrected."],
]


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
    status, resp_headers, payload = raw(method, path, data, hdrs)
    return status, resp_headers, json.loads(payload) if payload else None


def post(path, body):
    return api("POST", path, body, {"Idempotency-Key": f"pi-{uuid.uuid4().hex}"})


def code(body):
    return (body or {}).get("error", {}).get("code")


def make_pdf(pages):
    """Minimal valid PDF; each page draws its lines with Helvetica (or nothing when empty)."""
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    kids = []
    for i, lines in enumerate(pages):
        page_id, content_id = 4 + 2 * i, 5 + 2 * i
        kids.append(f"{page_id} 0 R")
        if lines:
            ops = ["BT", "/F1 12 Tf", "72 720 Td"]
            for line in lines:
                ops += [f"({line}) Tj", "0 -16 Td"]
            ops.append("ET")
        else:
            ops = ["72 720 m", "300 720 l", "S"]  # A drawing with no text layer.
        stream = "\n".join(ops).encode()
        objects[content_id] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        objects[page_id] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
                            "/Resources << /Font << /F1 3 0 R >> >> >>").encode()
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()
    out, offsets = bytearray(b"%PDF-1.4\n"), {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += b"%d 0 obj\n" % num + objects[num] + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for num in sorted(objects):
        out += b"%010d 00000 n \n" % offsets[num]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def create_upload(pid, data, filename, mime="application/pdf"):
    status, _, up = post(f"/projects/{pid}/uploads", {"filename": filename, "mime_type": mime, "size_bytes": len(data),
                                                      "sha256": hashlib.sha256(data).hexdigest(), "kind": "document",
                                                      "origin": "reference"})
    assert status == 201, up
    status, _, body = raw("PUT", f"/projects/{pid}/uploads/{up['id']}/content", data, {"Content-Type": mime})
    assert status == 204, body
    return post(f"/projects/{pid}/uploads/{up['id']}/complete", {})


def wait_run(pid, rid, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, _, run = api("GET", f"/projects/{pid}/runs/{rid}")
        if run["status"] in ("succeeded", "failed", "cancelled"):
            return run
        time.sleep(1)
    raise AssertionError(f"run {rid} did not finish")


def sources(pid):
    return api("GET", f"/projects/{pid}/sources?limit=100")[2]["items"]


def artifact_json(pid, aid):
    status, _, data = raw("GET", f"/projects/{pid}/artifacts/{aid}/content")
    assert status == 200, status
    return json.loads(data)


CLAIM_SCRIPT = r"""
import json, os, sys
sys.path.insert(0, "/app")
from stellaris_api import db
from stellaris_api.errors import ApiError
from stellaris_api.research import publish_claim
conn = db.connect(os.environ["STELLARIS_DB_PATH"])
pid, sid, rid, excerpt, locator = sys.argv[1:6]
def attempt(excerpt, locator):
    try:
        with db.transaction(conn):
            publish_claim(conn, pid, run_id=rid, kind="inference", text="Probe claim from paper_ingest_test.",
                          citations=[{"source_id": sid, "locator": locator or None, "excerpt": excerpt}],
                          assumptions=["Test probe."])
        return "ok"
    except ApiError as exc:
        return exc.code + ":" + json.dumps(exc.details.get("field_errors", []))
print(json.dumps({
    "verbatim": attempt(excerpt, locator),
    "whitespace": attempt("  " + excerpt.replace(" ", "\n  "), None),
    "fabricated": attempt("The ball gained energy on every bounce.", None),
    "bad_locator": attempt(excerpt, "§99 ¶1"),
}))
"""


def probe_claims(pid, sid, rid, excerpt, locator):
    result = subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "-", pid, sid, rid, excerpt, locator],
                            input=CLAIM_SCRIPT.encode(), capture_output=True, cwd=BACKEND_DIR)
    assert result.returncode == 0, result.stderr.decode()[-2000:]
    return json.loads(result.stdout.decode().strip().splitlines()[-1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-arxiv", action="store_true")
    parser.add_argument("--arxiv-id", default="1706.03762")
    args = parser.parse_args()

    print("capabilities")
    _, _, caps = api("GET", "/capabilities")
    check(caps["features"].get("full_text_papers") is True, "full_text_papers capability enabled")
    check("application/pdf" in caps["uploads"]["accepted_mime_types"], "application/pdf accepted for upload")

    status, _, project = post("/projects", {"name": "Paper ingestion test", "research_question": "Full-text test"})
    assert status == 201, project
    pid = project["id"]

    print("uploads")
    status, _, err = create_upload(pid, b"just text, not a pdf at all", "fake.pdf")
    check(status == 422 and code(err) == "MEDIA_DECODE_FAILED", "non-PDF bytes rejected as application/pdf")
    pdf = make_pdf(PAGE_TEXT)
    status, _, pdf_art = create_upload(pid, pdf, "test-paper.pdf")
    check(status == 200 and pdf_art["mime_type"] == "application/pdf", "PDF upload completes")
    status, _, blank_art = create_upload(pid, make_pdf([[]]), "scanned.pdf")
    assert status == 200, blank_art
    status, headers, _ = raw("GET", f"/projects/{pid}/artifacts/{pdf_art['id']}/content?disposition=inline")
    check(status != 200 or "attachment" in (headers.get("Content-Disposition") or ""), "PDF never served inline")

    print("run validation")
    bad = [
        ({"kind": "paper_ingest", "document": {"arxiv_id": "not an id"}}, "invalid arXiv id"),
        ({"kind": "paper_ingest", "document": {"arxiv_id": "1706.03762"}, "metadata": {"title": "x"}},
         "metadata with arXiv"),
        ({"kind": "paper_ingest", "document": {"artifact_id": pdf_art["id"]}, "requested_by_run_id": None},
         "client requested_by_run_id"),
        ({"kind": "paper_ingest", "document": {"artifact_id": pdf_art["id"], "arxiv_id": "1706.03762"}},
         "two document references"),
    ]
    for body, label in bad:
        status, _, err = post(f"/projects/{pid}/runs", body)
        check(status == 422, f"rejects {label} ({code(err)})")
    status, _, err = post(f"/projects/{pid}/runs", {"kind": "paper_ingest", "document": {"artifact_id": "art_" + "0" * 32}})
    check(status == 422 and code(err) == "INVALID_REFERENCE", "rejects unknown artifact")

    print("uploaded PDF ingestion")
    status, _, run = post(f"/projects/{pid}/runs", {"kind": "paper_ingest", "document": {"artifact_id": pdf_art["id"]},
                                                    "metadata": {"title": "Restitution test document",
                                                                 "authors": ["Test Author"]}})
    check(status == 202 and run["input"]["requested_by_run_id"] is None, "paper_ingest accepted")
    run = wait_run(pid, run["id"])
    check(run["status"] == "succeeded", f"uploaded PDF ingestion succeeded ({run.get('error')})")
    check(run["provenance_artifact_id"] is not None, "provenance recorded")
    src = next(s for s in sources(pid) if (s.get("full_text") or {}).get("ingest_run_id") == run["id"])
    check(src["provider"] == "manual" and src["retrieval_status"] == "full_text_retrieved", "full-text manual source")
    check(src["document_artifact_id"] == pdf_art["id"], "source links the uploaded PDF")
    check(src["url"] == f"/api/v1/projects/{pid}/artifacts/{pdf_art['id']}/content", "internal content URL")
    check(src["full_text"]["format"] == "pdf_text" and src["full_text"]["page_count"] == 2, "pdf_text with 2 pages")
    paper = artifact_json(pid, src["full_text"]["text_artifact_id"])
    check(paper["schema"] == "stellaris.paper.v1" and [s["locator"] for s in paper["sections"]] == ["p. 1", "p. 2"],
          "paper.json has page sections")
    joined = " ".join(p["text"] for s in paper["sections"] for p in s["paragraphs"])
    check("apex heights" in joined and "Perspective error" in joined, "extracted text matches the fixture")
    outputs = {a["id"]: a for a in api("GET", f"/projects/{pid}/artifacts?run_id={run['id']}&limit=100")[2]["items"]}
    check(any(a["filename"] == "paper_extract_v1.py" and a["kind"] == "code" for a in outputs.values()),
          "executed extraction code published")
    check(outputs[src["full_text"]["text_artifact_id"]]["origin"] == "derived", "paper.json is derived")

    print("citation verification")
    para = paper["sections"][0]["paragraphs"][0]
    excerpt = "We track a ball and measure apex heights."
    result = probe_claims(pid, src["id"], run["id"], excerpt, para["locator"])
    check(result["verbatim"] == "ok", f"verbatim excerpt with exact locator accepted ({result['verbatim']})")
    check(result["whitespace"] == "ok", "whitespace-normalised excerpt accepted")
    check(result["fabricated"].startswith("VALIDATION_FAILED"), "fabricated excerpt rejected")
    check(result["bad_locator"].startswith("VALIDATION_FAILED"), "unknown locator rejected")

    print("no text layer")
    status, _, run2 = post(f"/projects/{pid}/runs", {"kind": "paper_ingest", "document": {"artifact_id": blank_art["id"]}})
    assert status == 202, run2
    run2 = wait_run(pid, run2["id"])
    check(run2["status"] == "failed" and run2["error"]["code"] == "NO_TEXT_LAYER", "PDF without text fails NO_TEXT_LAYER")
    check(not any((s.get("full_text") or {}).get("ingest_run_id") == run2["id"] for s in sources(pid)),
          "no source published for a failed ingestion")

    if not args.skip_arxiv:
        print(f"arXiv {args.arxiv_id} (live)")
        status, _, run3 = post(f"/projects/{pid}/runs", {"kind": "paper_ingest", "document": {"arxiv_id": args.arxiv_id}})
        assert status == 202, run3
        run3 = wait_run(pid, run3["id"], timeout=600)
        check(run3["status"] == "succeeded", f"arXiv ingestion succeeded ({run3.get('error')})")
        src3 = next(s for s in sources(pid) if (s.get("full_text") or {}).get("ingest_run_id") == run3["id"])
        check(src3["provider"] == "arxiv" and src3["external_id"].startswith(args.arxiv_id), "arXiv source snapshot")
        check(src3["full_text"]["format"] == "latex_source", "LaTeX source preferred")
        raw_doc = api("GET", f"/projects/{pid}/artifacts/{src3['document_artifact_id']}")[2]
        check(raw_doc["origin"] == "reference" and raw_doc["mime_type"] in ("application/gzip", "application/x-tar"),
              "raw e-print kept as a reference artifact")
        paper3 = artifact_json(pid, src3["full_text"]["text_artifact_id"])
        numbered = [s for s in paper3["sections"] if s["number"]]
        check(len(numbered) >= 3, f"numbered sections extracted ({len(numbered)})")
        print(f"      {src3['title']}: {run3['result_summary']}")
        first = next(p for s in numbered for p in s["paragraphs"] if len(p["text"]) > 80)
        result = probe_claims(pid, src3["id"], run3["id"], first["text"][:80], first["locator"])
        check(result["verbatim"] == "ok", f"excerpt from LaTeX full text accepted ({result['verbatim']})")

    print(f"\n{len(PASSED)} checks passed (project {pid}).")


if __name__ == "__main__":
    sys.exit(main())
