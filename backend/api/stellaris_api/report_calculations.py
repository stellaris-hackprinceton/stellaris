"""Run report-requested reproducible calculations in the isolated analysis worker."""

import json
import threading

from . import runs, worker
from .artifacts import commit_artifact
from .db import transaction
from .errors import ApiError
from .executor import RunFailure
from .http import dumps, now_ts
from .projects import load_writable

MAX_IMPLEMENTATION_BYTES = 256 * 1024
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_READ_BYTES = 64 * 1024
MAX_TOTAL_OUTPUT_TEXT_BYTES = 120 * 1024
ALLOWED_INPUT_KINDS = {"dataset", "image", "video", "chart"}


def _snapshot_artifact(doc):
    return {k: doc[k] for k in ("id", "kind", "origin", "filename", "mime_type", "size_bytes", "sha256",
                                 "parent_artifact_ids", "metadata", "created_at")}


def _bounded_text(ctx, artifact_id, max_bytes):
    try:
        size, reader, close = ctx.runtime.open_artifact(ctx.project_id, artifact_id)
    except Exception:
        return "", False, True
    try:
        try:
            data = reader.read(min(MAX_READ_BYTES, max_bytes) + 1)
        except Exception:
            return "", False, True
    finally:
        try:
            close()
        except Exception:
            pass
    cap = min(MAX_READ_BYTES, max_bytes)
    truncated = size > cap or len(data) > cap
    text = data[:cap].decode("utf-8", "replace")
    encoded = text.encode("utf-8")
    if len(encoded) > cap:
        text = encoded[:cap].decode("utf-8", "ignore")
        truncated = True
    return text, truncated, False


def execute_calculation(ctx, source: str, input_artifact_ids: list[str], evidence: list[dict], cancelled=None) -> dict:
    """Execute generated report-analysis calculations in a synchronous normal analysis run."""
    is_cancelled = cancelled or ctx.cancel_requested
    if not isinstance(source, str) or not source.strip():
        raise ApiError(422, "VALIDATION_FAILED", "Calculation source must be 1 to 262144 UTF-8 bytes.")
    try:
        source_bytes = source.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise ApiError(422, "VALIDATION_FAILED", "Calculation source must be valid UTF-8.") from exc
    if len(source_bytes) > MAX_IMPLEMENTATION_BYTES:
        raise ApiError(422, "VALIDATION_FAILED", "Calculation source must be 1 to 262144 UTF-8 bytes.")
    if not isinstance(input_artifact_ids, list) or len(input_artifact_ids) > 100 or any(
            not isinstance(aid, str) for aid in input_artifact_ids):
        raise ApiError(422, "VALIDATION_FAILED", "Calculation input artifact IDs must be a list of at most 100 IDs.")
    if len(set(input_artifact_ids)) != len(input_artifact_ids):
        raise ApiError(422, "VALIDATION_FAILED", "Calculation input artifact IDs must be unique.")
    if not isinstance(evidence, list) or not evidence:
        raise ApiError(422, "VALIDATION_FAILED", "Calculation requires selected report evidence.")
    if is_cancelled():
        raise RunFailure("CANCELLED", "The report analysis was cancelled before calculation preparation.")
    allowed_run_ids = {item["id"] for item in ctx.snapshot.get("evidence_runs", [])}
    if any(not isinstance(e, dict) or e.get("run", {}).get("id") not in allowed_run_ids for e in evidence):
        raise ApiError(422, "VALIDATION_FAILED", "Calculation evidence must be selected by this report run.")

    selected_by_id = {}
    evidence_run_ids = []
    for entry in evidence:
        run_id = entry["run"]["id"]
        if run_id in evidence_run_ids:
            raise ApiError(422, "VALIDATION_FAILED", "Calculation evidence runs must be unique.")
        evidence_run_ids.append(run_id)
        for art in entry.get("snapshot", {}).get("inputs", []):
            if art.get("kind") in ALLOWED_INPUT_KINDS:
                selected_by_id[art["id"]] = art
        for art in entry.get("artifacts", []):
            if art.get("kind") in ALLOWED_INPUT_KINDS:
                selected_by_id[art["id"]] = art
    if any(aid not in selected_by_id for aid in input_artifact_ids):
        raise ApiError(422, "VALIDATION_FAILED", "Calculation inputs must be data or media artifacts from selected evidence.")

    # Resolve all selected IDs inside this project and reject mutable/unsafe kinds.
    actual = {}
    for aid in input_artifact_ids:
        row = ctx.conn.execute("SELECT doc FROM artifacts WHERE id = ? AND project_id = ?", (aid, ctx.project_id)).fetchone()
        if row is None:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
        doc = json.loads(row["doc"])
        if doc.get("kind") not in ALLOWED_INPUT_KINDS:
            raise ApiError(422, "VALIDATION_FAILED", "Calculation inputs must be dataset, image, video, or chart artifacts.")
        actual[aid] = _snapshot_artifact(doc)

    supported = worker.available_runtimes(ctx.runtime, ctx.config)
    if "python" not in supported:
        raise ApiError(409, "FEATURE_UNAVAILABLE", "The configured worker image does not advertise Python runtime.")

    base = evidence[0]["snapshot"]
    experiment = json.loads(json.dumps(base["experiment"]))
    experiment["input_artifact_ids"] = list(input_artifact_ids)
    experiment_id, revision = experiment["id"], experiment["revision"]
    serialized_evidence = []
    for entry in evidence:
        serialized_evidence.append({k: entry.get(k) for k in
                                    ("run", "snapshot", "measurements", "claims", "artifacts", "warnings", "simulated")})
    evidence_bytes = dumps({"schema": "stellaris.report_calculation_evidence.v1", "evidence": serialized_evidence}).encode("utf-8")
    if len(evidence_bytes) > MAX_EVIDENCE_BYTES:
        raise ApiError(422, "VALIDATION_FAILED", "Selected evidence exceeds the calculation dataset limit.")

    # Stage exact code/evidence, then commit them atomically with child acceptance.
    evidence_parents = list(dict.fromkeys(
        [a["id"] for entry in evidence for a in entry.get("artifacts", [])
         if a.get("kind") in ALLOWED_INPUT_KINDS] +
        [a["id"] for entry in evidence for a in entry.get("snapshot", {}).get("inputs", [])
         if a.get("kind") in ALLOWED_INPUT_KINDS]
    ))[:50]
    code = ctx.stage_text(source, filename="report-calculation.py", mime_type="text/x-python", kind="code",
                          origin="generated", experiment_id=experiment_id, parent_artifact_ids=evidence_parents)
    data = ctx.stage_text(evidence_bytes.decode("utf-8"), filename="report-evidence.json", mime_type="application/json",
                          kind="dataset", origin="simulated" if any(e.get("simulated") for e in evidence) else "generated",
                          experiment_id=experiment_id, parent_artifact_ids=evidence_parents)
    code_doc, evidence_doc = code, data

    inputs = [actual[aid] for aid in input_artifact_ids]
    inputs.append(_snapshot_artifact(evidence_doc))
    experiment["input_artifact_ids"] = [a["id"] for a in inputs]
    # A report calculation consumes recorded units. It does not inherit a camera
    # conversion from the first of potentially differently calibrated evidence runs.
    experiment["calibration"] = {"mode": "none", "assumptions": [
        "Use each saved measurement's recorded units. Original per-run calibrations are retained in report-evidence.json."]}
    simulated = any(e.get("simulated") for e in evidence) or any(a.get("origin") == "simulated" for a in inputs)
    child_snapshot = json.loads(json.dumps(base))
    child_snapshot.update({
        "version": 1, "kind": "analysis", "runtime": "python", "experiment": experiment,
        "inputs": inputs, "code": _snapshot_artifact(code_doc),
        "pipeline": {"name": "script_analysis_v1", "version": runs.PIPELINES["script_analysis_v1"]["version"],
                     "source": None, "source_sha256": None},
        "parameters": {}, "sources": [], "simulated": simulated,
        "calibration_conversion": None, "calibration_assumptions": [],
        "execution": runs.resolve_execution({"backend": "isolated_python"}, ctx.config, ctx.manager.cluster),
        "limits": runs._limits(ctx.config), "accepted_at": now_ts(),
        "report_calculation": {"requested_by_report_run_id": ctx.run_id, "evidence_run_ids": evidence_run_ids,
                               "code_artifact_id": code_doc["id"], "evidence_artifact_id": evidence_doc["id"]},
    })
    run_input = {"kind": "analysis", "experiment_id": experiment_id, "experiment_revision": revision,
                 "input_artifact_ids": [a["id"] for a in inputs], "pipeline": "script_analysis_v1",
                 "code_artifact_id": code_doc["id"], "runtime": "python", "parameters": {},
                 "execution": {"backend": "isolated_python"}}
    if is_cancelled():
        raise RunFailure("CANCELLED", "The report analysis was cancelled before calculation acceptance.")
    with transaction(ctx.conn):
        load_writable(ctx.conn, ctx.project_id)
        if is_cancelled():
            raise RunFailure("CANCELLED", "The report analysis was cancelled before calculation acceptance.")
        code_doc = commit_artifact(ctx.conn, code)
        evidence_doc = commit_artifact(ctx.conn, data)
        child_snapshot["code"] = _snapshot_artifact(code_doc)
        child_snapshot["inputs"] = [actual[aid] for aid in input_artifact_ids] + [_snapshot_artifact(evidence_doc)]
        run = runs.insert_run(ctx.conn, ctx.project_id, run_input, child_snapshot,
                              experiment_id=experiment_id, config=ctx.config)
        runs.save_run(ctx.conn, ctx.run_id)
    committed_ids = {code_doc["id"], evidence_doc["id"]}
    ctx.staged = [item for item in ctx.staged if item["id"] not in committed_ids]
    ctx.log.system(f"Report calculation accepted: {dumps({'run_id': run['id'], 'code_artifact_id': code_doc['id'], 'evidence_artifact_id': evidence_doc['id']})}")
    ctx.log.flush()

    finished = threading.Event()

    def watch_cancel():
        while not finished.wait(0.1):
            if is_cancelled():
                ctx.manager.request_cancel(run["id"])
                return

    watcher = threading.Thread(target=watch_cancel, name=f"cancel-report-calc-{run['id'][-8:]}", daemon=True)
    watcher.start()
    try:
        if is_cancelled():
            ctx.manager.request_cancel(run["id"])
        ctx.manager.execute_now(run["id"])
    finally:
        finished.set()
        watcher.join(timeout=1)
        with ctx.manager._lock:
            ctx.manager._cancel_events.pop(run["id"], None)

    child = runs.load_run_row(ctx.conn, ctx.project_id, run["id"])
    public = json.loads(child["doc"])
    output_ids = public.get("output_artifact_ids", [])
    output_text = []
    output_text_bytes = 0
    output_text_omitted_count = 0
    output_text_truncated_count = 0
    output_text_unavailable_count = 0
    for aid in output_ids:
        row = ctx.conn.execute("SELECT doc FROM artifacts WHERE id = ? AND project_id = ?", (aid, ctx.project_id)).fetchone()
        if row is None:
            continue
        art = json.loads(row["doc"])
        if art.get("kind") == "dataset" and art.get("mime_type") in ("application/json", "text/plain", "text/csv"):
            remaining = MAX_TOTAL_OUTPUT_TEXT_BYTES - output_text_bytes
            if remaining <= 0:
                output_text_omitted_count += 1
                continue
            text, truncated, unavailable = _bounded_text(ctx, aid, remaining)
            text_size = len(text.encode("utf-8"))
            output_text_bytes += text_size
            output_text_truncated_count += int(truncated)
            output_text_unavailable_count += int(unavailable)
            output_text.append({"artifact_id": aid, "filename": art.get("filename"), "text": text,
                                "truncated": truncated, "unavailable": unavailable})
            if truncated:
                output_text_omitted_count += 1
    logs = "".join(json.loads(item["doc"])["text"] for item in ctx.conn.execute(
        "SELECT doc FROM run_logs WHERE run_id = ? ORDER BY sequence", (run["id"],)).fetchall())[-12_000:]
    return {"run_id": run["id"], "status": public["status"], "error": public.get("error"),
            "output_artifact_ids": output_ids, "provenance_artifact_id": public.get("provenance_artifact_id"),
            "code_artifact_id": code_doc["id"], "evidence_artifact_id": evidence_doc["id"],
            "output_text": output_text, "output_text_omitted_count": output_text_omitted_count,
            "output_text_truncated_count": output_text_truncated_count,
            "output_text_unavailable_count": output_text_unavailable_count,
            "output_text_notice": ("Some dataset output text was truncated, unavailable, or omitted to enforce the 120 KiB response limit."
                                   if output_text_omitted_count or output_text_unavailable_count else None),
            "log": logs}
