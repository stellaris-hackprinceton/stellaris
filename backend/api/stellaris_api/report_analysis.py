"""Bounded evidence tools and validation for the project-contained report Deep Agent."""

import hashlib
import json
import re

from . import agent_runs, papers
from .errors import ApiError
from .executor import RunFailure
from .http import dumps
from .runtime import ArtifactMissing, RuntimeUnavailable

PAGE_ITEMS = 40
MAX_PAGE_BYTES = 80_000
MAX_CONTEXT_BYTES = 1_500_000
MAX_PAPER_CHARS = 16_000
MAX_CALCULATIONS = 4
SECTIONS = ("overview", "experiment", "measurements", "claims", "sources")
RESOURCE_ID = re.compile(r"\b(?:run|src|msr|art|clm|exp)_[0-9a-f]{16,32}\b")


def _ids(value):
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "parameters":
                continue  # User-defined parameter objects do not establish resource identities.
            # Untrusted prose may mention invented IDs. Only structured ID fields
            # establish a reference that the backend can validate.
            if key == "id" or key.endswith("_id"):
                if isinstance(item, str) and RESOURCE_ID.fullmatch(item):
                    found.add(item)
            elif key.endswith("_ids") and isinstance(item, list):
                found.update(item for item in item if isinstance(item, str) and RESOURCE_ID.fullmatch(item))
            if isinstance(item, (dict, list)):
                found.update(_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_ids(item))
    return found


class ReportSession:
    def __init__(self, ctx, evidence):
        self.ctx = ctx
        self.evidence = evidence
        self.by_run = {e["run"]["id"]: e for e in evidence}
        self.reads = []
        self.calculations = []
        self.paper_cache = {}
        self.known_ids = set(self.by_run)
        self.supplied_bytes = 0
        self.analysis = None
        self.metadata = {}

    def audit(self, event, record):
        # Run logs are committed incrementally. Recovery can retain the exact
        # supplied-record hashes and calculation IDs even if the API is restarted
        # before a final provenance artifact can be published.
        self.ctx.log.system(f"Report analysis {event}: {dumps(record)}")
        self.ctx.log.flush()

    def request(self):
        snap = self.ctx.snapshot
        return {
            "mode": "report", "project_id": self.ctx.project_id, "run_id": self.ctx.run_id,
            "report": {"title": snap["title"], "research_question": snap["project"].get("research_question"),
                       "evidence_run_ids": list(self.by_run),
                       "source_ids": [s["id"] for s in snap.get("sources", [])]},
            "evidence_manifest": {
                "runs": [{"run_id": e["run"]["id"], "status": e["run"]["status"],
                          "measurement_count": len(e["measurements"]), "claim_count": len(e["claims"]),
                          "source_count": len(e["snapshot"].get("sources", [])),
                          "simulated": bool(e["simulated"])} for e in self.evidence],
                "sections": list(SECTIONS), "page_items": PAGE_ITEMS,
                "context_budget_bytes": MAX_CONTEXT_BYTES,
                "calculation_limit": MAX_CALCULATIONS,
                "note": "Use read_report_evidence for actual records. Unread pages are not inspected evidence.",
            },
        }

    def _source_record(self, source):
        sid = source["id"]
        if sid in self.paper_cache:
            return self.paper_cache[sid]
        record = {"source": source}
        full = source.get("full_text") or {}
        if source.get("retrieval_status") == "full_text_retrieved" and full.get("text_artifact_id"):
            try:
                paper, art = papers.load_paper(self.ctx.runtime, self.ctx.conn, self.ctx.project_id,
                                               full["text_artifact_id"])
                if paper is not None:
                    text = dumps(paper)
                    record.update(retrieved_text=text[:MAX_PAPER_CHARS],
                                  text_truncated=len(text) > MAX_PAPER_CHARS or bool(full.get("truncated")),
                                  text_artifact_id=art["id"], sha256=art["sha256"])
                else:
                    record["text_unavailable"] = True
            except (RuntimeUnavailable, ArtifactMissing, ValueError, ApiError):
                record["text_unavailable"] = True
        self.paper_cache[sid] = record
        return record

    def _records(self, run_id, section):
        if run_id == "" and section == "sources":
            return [self._source_record(s) for s in self.ctx.snapshot.get("sources", [])]
        e = self.by_run.get(run_id)
        if e is None:
            raise ValueError("Run is not selected evidence for this report.")
        if section == "overview":
            return [{"run": e["run"], "warnings": e["warnings"], "simulated": bool(e["simulated"]),
                     "artifacts": e["artifacts"], "accepted_at": e["snapshot"]["accepted_at"]}]
        if section == "experiment":
            return [{key: e["snapshot"].get(key) for key in
                     ("experiment", "inputs", "pipeline", "parameters", "calibration_conversion",
                      "calibration_assumptions", "code")}]
        if section == "sources":
            return [self._source_record(s) for s in e["snapshot"].get("sources", [])]
        return e[section]

    def read(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {"run_id", "section", "offset"}
                or not isinstance(payload["run_id"], str) or payload["section"] not in SECTIONS
                or type(payload["offset"]) is not int or payload["offset"] < 0):
            raise ValueError("Expected run_id, a supported section, and a nonnegative integer offset.")
        run_id, section, offset = payload["run_id"], payload["section"], payload["offset"]
        records = self._records(run_id, section)
        if offset > len(records):
            raise ValueError("Offset exceeds the selected section.")
        items = []
        for item in records[offset:offset + PAGE_ITEMS]:
            raw = dumps(item).encode("utf-8")
            if len(raw) > MAX_PAGE_BYTES:
                raise ValueError("An evidence record exceeds the page limit. Report analysis cannot inspect it safely.")
            if len(dumps(items + [item]).encode("utf-8")) > MAX_PAGE_BYTES:
                break
            items.append(item)
        end = offset + len(items)
        result = {"run_id": run_id, "section": section, "items": items, "total_count": len(records),
                  "next_offset": end if end < len(records) else None}
        raw = dumps(result).encode("utf-8")
        if self.supplied_bytes + len(raw) > MAX_CONTEXT_BYTES:
            raise ValueError("Report context budget reached. Explain unread evidence as a limitation.")
        self.supplied_bytes += len(raw)
        self.known_ids.update(_ids(items))
        read = {"run_id": run_id, "section": section, "offset": offset,
                           "count": len(items), "total_count": len(records),
                           "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw),
                           "record_ids": sorted(_ids(items)),
                           "text_truncated": any(item.get("text_truncated", False) for item in items),
                           "text_unavailable": any(item.get("text_unavailable", False) for item in items)}
        self.reads.append(read)
        self.audit("evidence_read", read)
        return result

    def handle_tool(self, name, payload, *, cancelled):
        if cancelled():
            raise RunFailure("CANCELLED", "The report analysis was cancelled.")
        try:
            if name == "read_report_evidence":
                result = self.read(payload)
            elif name == "calculate_report":
                if not isinstance(payload, dict) or set(payload) != {"source", "input_artifact_ids"}:
                    raise ValueError("Expected Python source and input_artifact_ids.")
                if len(self.calculations) >= MAX_CALCULATIONS:
                    raise ValueError("Report calculation limit reached. Explain remaining analysis as a limitation.")
                from .report_calculations import execute_calculation
                result = execute_calculation(self.ctx, payload["source"], payload["input_artifact_ids"],
                                             self.evidence, cancelled=cancelled)
                self.calculations.append(result)
                self.known_ids.update(_ids(result))
                self.audit("calculation", {k: v for k, v in result.items() if k not in {"output_text", "log"}})
            else:
                raise ValueError("Report agents may only read selected evidence and execute isolated calculations.")
            return {"ok": True, "result": result}
        except (ValueError, ApiError) as exc:
            return {"ok": False, "error": getattr(exc, "message", str(exc))[:1000]}

    def limitations(self):
        limitations = []
        for run_id, section in [(rid, s) for rid in self.by_run for s in SECTIONS] + [("", "sources")]:
            pages = [r for r in self.reads if r["run_id"] == run_id and r["section"] == section]
            if not pages:
                continue
            supplied = {i for p in pages for i in range(p["offset"], p["offset"] + p["count"])}
            missing = pages[0]["total_count"] - len(supplied)
            if missing:
                limitations.append(f"Agent did not inspect {missing} {section} records for {run_id or 'selected sources'}.")
        if any(r["text_truncated"] for r in self.reads):
            limitations.append("Retrieved paper text supplied to the agent was partial or truncated.")
        if any(r["text_unavailable"] for r in self.reads):
            limitations.append("Some saved full-text source content was unavailable to the agent.")
        if any(c["status"] != "succeeded" for c in self.calculations):
            limitations.append("Some report calculations did not succeed. Their outputs are partial evidence only.")
        if any(c.get("output_text_notice") for c in self.calculations):
            limitations.append("Some calculation output text supplied to the agent was truncated, unavailable, or omitted.")
        return limitations

    def accept_analysis(self, analysis):
        def invalid(message):
            raise RunFailure("INVALID_REPORT_ANALYSIS", message)

        if self.analysis is not None:
            invalid("The report agent returned more than one final analysis.")
        if not isinstance(analysis, dict) or set(analysis) != {"assessment", "interpretation_markdown", "limitations", "references"}:
            invalid("The report agent returned an invalid analysis structure.")
        if analysis["assessment"] not in ("supported", "contradicted", "inconclusive", "mixed"):
            invalid("The report agent returned an invalid hypothesis assessment.")
        text = analysis["interpretation_markdown"]
        if not isinstance(text, str) or not 80 <= len(text.strip()) <= 100_000:
            invalid("The report agent returned no substantive interpretation or exceeded the output limit.")
        limits, refs = analysis["limitations"], analysis["references"]
        if (not isinstance(limits, list) or not 1 <= len(limits) <= 50
                or any(not isinstance(s, str) or not 1 <= len(s.strip()) <= 2000 for s in limits)):
            invalid("The report analysis must state its limitations.")
        if (not isinstance(refs, list) or not 1 <= len(refs) <= 200
                or any(not isinstance(s, str) or s not in self.known_ids for s in refs)):
            invalid("The report analysis cites records outside its supplied evidence.")
        if not set(self.by_run).issubset(refs):
            invalid("The report analysis must reference every selected evidence run.")
        if set(RESOURCE_ID.findall(text)) - self.known_ids:
            invalid("The interpretation mentions records outside its supplied evidence.")
        if set(re.findall(r"\bprj_[0-9a-f]{32}\b", text)) - {self.ctx.project_id}:
            invalid("The interpretation links to another project.")
        required = {(rid, s) for rid in self.by_run for s in SECTIONS}
        if self.ctx.snapshot.get("sources"):
            required.add(("", "sources"))
        read = {(r["run_id"], r["section"]) for r in self.reads if r["offset"] == 0}
        if required - read:
            invalid("The report agent did not inspect the required evidence sections for every selected run.")
        if (not any(m.get("status") == "valid" and m.get("value") is not None
                    for e in self.evidence for m in e["measurements"]) and not any(
                c["status"] == "succeeded" for c in self.calculations) and analysis["assessment"] != "inconclusive"):
            invalid("Evidence without measurements or successful calculations requires an inconclusive assessment.")
        self.analysis = {**analysis, "limitations": list(dict.fromkeys(limits + self.limitations()))}


def analyze_report(ctx, evidence):
    session = ReportSession(ctx, evidence)
    provider, model_id, env, code, message = agent_runs.selected_model_config()
    if code:
        raise RunFailure(code, message.replace("Research chat", "Report analysis"))
    session.metadata.update(provider=provider, model=model_id)
    session.audit("model", session.metadata)
    lock = agent_runs._project_lock(ctx.project_id)
    while not lock.acquire(timeout=0.25):
        if ctx.cancel_requested():
            raise RunFailure("CANCELLED", "The report analysis was cancelled while waiting for the project agent.")
    try:
        if ctx.cancel_requested():
            raise RunFailure("CANCELLED", "The report analysis was cancelled.")
        ctx.progress("analyzing evidence", None, "Agent is evaluating saved evidence and the hypothesis.", force=True)
        try:
            agent_runs._run_agent(ctx, session.request(), env, [], session.metadata, provider, model_id,
                                  report_session=session)
        except RunFailure:
            raise
        except Exception as exc:
            raise RunFailure("AGENT_RUNTIME_LOST", "The project report agent connection failed.", True) from exc
        if session.analysis is None or not session.metadata.get("packages"):
            raise RunFailure("INVALID_REPORT_ANALYSIS", "The report agent did not complete a validated analysis with model provenance.")
        return session
    except RunFailure as exc:
        # Retain what the model was actually supplied, even when it fails. No
        # interpretation/report artifact is published on this path.
        provenance = ctx.stage_text(dumps({"schema": "stellaris.provenance.v1", "run_id": ctx.run_id,
            "project_id": ctx.project_id, "accepted_snapshot": ctx.snapshot, "outputs": [],
            "execution": {"outcome": "cancelled" if exc.code == "CANCELLED" else "failed"},
            "agent_analysis": {**session.metadata, "evidence_reads": session.reads,
                               "calculations": session.calculations, "limitations": session.limitations()}}),
            filename="provenance.json", mime_type="application/json", kind="environment", origin="generated")
        retained = ctx.stage_text(ctx.log.text(), filename="run-log.txt", mime_type="text/plain", kind="log", origin="generated")
        ctx.finish("cancelled" if exc.code == "CANCELLED" else "failed",
                   error=None if exc.code == "CANCELLED" else {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
                   summary="Report analysis cancelled." if exc.code == "CANCELLED" else "Report analysis failed.",
                   retained=[retained], provenance=provenance)
        return None
    finally:
        lock.release()
