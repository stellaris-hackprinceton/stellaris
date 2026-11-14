"""Provider-free report checks. Run in the API image, with --docker for real storage/workers.

All evidence and model answers here are explicitly simulated test fixtures. No live
provider requests or credential environment are needed. Docker mode creates and retains
one labelled test project volume. Its container is stopped at the end.
"""

import copy
import json
import os
import sys
import tempfile
import uuid
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from stellaris_api import agent_runs, analysis, db, experiments, reports, runs
from stellaris_api.config import load_config
from stellaris_api.db import transaction
from stellaris_api.executor import RunContext, RunFailure, RunManager
from stellaris_api.http import dumps, new_id, now_ts
from stellaris_api.report_analysis import ReportSession, SECTIONS
from stellaris_api.runtime import ProjectRuntime


class Log:
    def __init__(self):
        self.lines = []

    def system(self, text):
        self.lines.append(text)

    def flush(self):
        pass


def fixture(project_id):
    eid, rid, mid = new_id("exp"), new_id("run"), "msr_" + uuid.uuid4().hex[:24]
    exp = {"id": eid, "project_id": project_id, "title": "SIMULATED comparison",
           "hypothesis": "Later bounce heights decrease.", "method": "computational",
           "protocol_markdown": "SIMULATED unit fixture. No physical observations.", "variables": [],
           "success_criteria": [], "input_artifact_ids": [], "calibration": {"mode": "none", "assumptions": []},
           "limitations": ["SIMULATED fixture only"], "implementation": None,
           "revision": 1, "created_at": now_ts(), "updated_at": now_ts()}
    snap = {"experiment": exp, "accepted_at": now_ts(), "inputs": [], "code": None, "sources": [],
            "pipeline": {"name": "script_analysis_v1", "version": "1", "source": None, "source_sha256": None},
            "parameters": {}, "calibration_conversion": None, "calibration_assumptions": [], "simulated": True}
    run = {"id": rid, "project_id": project_id, "status": "failed", "revision": 1,
           "input": {"kind": "analysis", "pipeline": "script_analysis_v1", "experiment_id": eid},
           "error": {"code": "INSUFFICIENT_EVIDENCE", "message": "SIMULATED fixture lacks enough bounces.", "retryable": False},
           "started_at": now_ts(), "finished_at": now_ts(), "result_summary": "SIMULATED partial evidence",
           "provenance_artifact_id": None}
    measurement = {"id": mid, "project_id": project_id, "run_id": rid, "experiment_id": eid,
        "series": "bounce", "quantity": "apex_height", "value": 10, "unit": "px", "time_s": None,
        "uncertainty": {"absolute": None, "method": None}, "status": "valid", "calibration_mode": "none",
        "data_origin": "simulated", "evidence": [], "assumptions": ["SIMULATED fixture"], "created_at": now_ts()}
    evidence = {"run": run, "snapshot": snap, "measurements": [measurement], "claims": [], "artifacts": [],
                "warnings": [], "simulated": True}
    return evidence


def report_snapshot(project_id, evidence):
    return {"title": "SIMULATED agent report test", "project": {"id": project_id, "research_question": "Do heights decrease?"},
        "experiment_current": evidence["snapshot"]["experiment"], "accepted_at": now_ts(), "sources": [],
        "evidence_runs": [{"id": evidence["run"]["id"], "status": evidence["run"]["status"], "revision": 1,
                           "provenance_artifact_id": None}], "format": "markdown"}


def read_all(session):
    for rid in session.by_run:
        for section in SECTIONS:
            session.read({"run_id": rid, "section": section, "offset": 0})


def answer(evidence):
    return {"assessment": "inconclusive",
        "interpretation_markdown": "The hypothesis remains inconclusive. The simulated run failed with insufficient evidence. "
            "A single recorded height cannot establish a decline across bounces. Tracking failure is an alternative "
            "explanation for missing results. No physical scale is available and uncertainty is unknown. "
            f"See [{evidence['run']['id']}](/api/v1/projects/{evidence['run']['project_id']}/runs/{evidence['run']['id']}).",
        "limitations": ["SIMULATED partial evidence, unknown uncertainty, and no physical calibration."],
        "references": [evidence["run"]["id"], evidence["measurements"][0]["id"]]}


def rejects(fn, code="INVALID_REPORT_ANALYSIS"):
    try:
        fn()
    except RunFailure as exc:
        assert exc.code == code, (exc.code, exc.message)
    else:
        raise AssertionError(f"expected {code}")


def local_checks():
    project_id = new_id("prj")
    evidence = fixture(project_id)
    ctx = SimpleNamespace(project_id=project_id, run_id=new_id("run"), snapshot=report_snapshot(project_id, evidence), log=Log())
    session = ReportSession(ctx, [evidence])
    session.metadata.update(provider="bedrock", model="offline-fixture")
    rejects(lambda: session.accept_analysis(answer(evidence)))
    denied = session.handle_tool("read_report_evidence", {"run_id": new_id("run"), "section": "overview", "offset": 0}, cancelled=lambda: False)
    assert denied["ok"] is False
    assert not session.handle_tool("organize_materials", {}, cancelled=lambda: False)["ok"]
    rejects(lambda: session.handle_tool("read_report_evidence", {}, cancelled=lambda: True), "CANCELLED")
    read_all(session)
    bad = answer(evidence)
    bad["references"].append(new_id("art"))
    rejects(lambda: session.accept_analysis(bad))
    bad = answer(evidence)
    bad["interpretation_markdown"] += f" See project {new_id('prj')}."
    rejects(lambda: session.accept_analysis(bad))
    session.accept_analysis(answer(evidence))
    rejects(lambda: session.accept_analysis(answer(evidence)))
    assert any("evidence_read" in line for line in ctx.log.lines)

    large = copy.deepcopy(evidence)
    large["measurements"] *= 45
    paged = ReportSession(ctx, [large])
    read_all(paged)
    paged.accept_analysis(answer(evidence))
    assert any("did not inspect 5 measurements" in text for text in paged.analysis["limitations"])

    empty = copy.deepcopy(evidence)
    empty["measurements"][0].update(status="missing", value=None)
    no_values = ReportSession(ctx, [empty])
    read_all(no_values)
    bad = answer(evidence)
    bad["assessment"] = "supported"
    rejects(lambda: no_values.accept_analysis(bad))
    text = reports.build_markdown(project_id, ctx.run_id, ctx.snapshot, [evidence], new_id("art"), now_ts(), analysis_session=session)
    assert "Scientific interpretation (AI)" in text and "SIMULATED DATA" in text
    assert "No reference-length calibration" in text and "unknown" in text and "This run did not succeed" in text
    assert "no language model was used" not in text
    legacy = reports.build_markdown(project_id, ctx.run_id, ctx.snapshot, [evidence], new_id("art"), now_ts())
    assert "no language model was used" in legacy
    # Exercise the real Docker stream parser with a provider-free transport.
    def streamed(events):
        api = SimpleNamespace(exec_create=lambda *a, **k: {"Id": "fixture-exec"}, exec_inspect=lambda *a: {"ExitCode": 0})
        container = SimpleNamespace(labels={"stellaris.project_id": project_id, "stellaris.role": "project-runtime"},
            attrs={"Image": "fixture-image"}, id="fixture-container", reload=lambda: None)
        api.containers = SimpleNamespace(get=lambda *a: container)
        stream_api = SimpleNamespace(exec_start=lambda *a, **k: iter([(dumps(v).encode() + b"\n", None) for v in events]))
        ctx.runtime = SimpleNamespace(ensure=lambda *a, **k: None, client=lambda: SimpleNamespace(api=api, containers=api.containers),
                                     stream_client=lambda: SimpleNamespace(api=stream_api))
        ctx.cancel_requested = lambda: False
        result = ReportSession(ctx, [evidence])
        with patch.object(agent_runs, "_put_request", return_value="/tmp/fixture.json"), \
             patch.object(agent_runs, "_deliver_agent_tool_reply"), patch.object(agent_runs, "_cleanup_agent_files"), \
             patch.object(agent_runs, "_terminate_agent"):
            agent_runs._run_agent(ctx, result.request(), {}, [], result.metadata, "bedrock", "fixture", report_session=result)
        return result

    events = [{"type": "provenance", "python_version": "test", "packages": {"deepagents": "fixture"},
               "tool_version": "fixture", "provider": "bedrock", "model": "fixture"}]
    events += [{"type": "tool_request", "request_id": f"{ctx.run_id}-{i + 1}", "name": "read_report_evidence",
                "payload": {"run_id": evidence["run"]["id"], "section": section, "offset": 0}}
               for i, section in enumerate(SECTIONS)]
    events += [{"type": "report_analysis", "analysis": answer(evidence)}, {"type": "complete"}]
    assert streamed(events).analysis["assessment"] == "inconclusive"
    rejects(lambda: streamed([{"type": "delta", "text": "unvalidated report"}]), "INVALID_AGENT_STREAM")
    rejects(lambda: streamed([{"type": "error", "code": "ThrottlingException"}]), "AGENT_PROVIDER_ERROR")
    rejects(lambda: streamed(events + [{"type": "complete"}]), "INVALID_AGENT_STREAM")
    print("PASS: evidence reads/scoping, cancellation, reference validation, incomplete evidence, failure/simulation/calibration, historical rendering")
    print("PASS: report stream/tool bridge, final validation, provider errors, rejection of unvalidated output and post-completion events")


def docker_checks():
    root = tempfile.mkdtemp(prefix="stellaris-report-check-", dir="/tmp")
    config = replace(load_config(), db_path=root + "/db.sqlite", upload_tmp_dir=root + "/uploads",
                     run_tmp_dir=root + "/runs", catalog_dir=root + "/catalogs", slurm_host="")
    db.init_db(config.db_path)
    conn = db.connect(config.db_path)
    runtime = ProjectRuntime(config)
    manager = RunManager(config, runtime)
    manager.register_handler("analysis", analysis.handle_analysis)
    manager.register_handler("report", reports.handle_report)
    project_id = new_id("prj")
    with transaction(conn):
        conn.execute("INSERT INTO projects VALUES (?, 'SIMULATED report integration', '', ?, 'active', 1, ?, ?, 'ready', NULL)",
                     (project_id, "Do heights decrease?", now_ts(), now_ts()))
    runtime.ensure(project_id, create_volume=True, wait_healthy=True)
    e = fixture(project_id)
    exp = e["snapshot"]["experiment"]
    # Seed explicit simulated terminal evidence. This tests persistence and report
    # orchestration, not the scientific accuracy of a measurement pipeline.
    with transaction(conn):
        conn.execute("INSERT INTO experiments (id,project_id,revision,created_at,doc) VALUES (?,?,?,?,?)",
            (exp["id"], project_id, 1, exp["created_at"], dumps(exp)))
        evidence_run = runs.insert_run(conn, project_id, e["run"]["input"], e["snapshot"], experiment_id=exp["id"], config=config)
        e["run"]["id"] = evidence_run["id"]
        e["measurements"][0]["run_id"] = evidence_run["id"]
        runs.save_run(conn, evidence_run["id"], status="running")
        runs.save_run(conn, evidence_run["id"], status="failed", error=e["run"]["error"], finished_at=now_ts())
        m = e["measurements"][0]
        conn.execute("INSERT INTO measurements (id,project_id,run_id,series,created_at,doc) VALUES (?,?,?,?,?,?)",
                     (m["id"], project_id, evidence_run["id"], m["series"], m["created_at"], dumps(m)))
    snap = report_snapshot(project_id, e)
    report_input = {"kind": "report", "experiment_id": exp["id"], "evidence_run_ids": [evidence_run["id"]],
                    "source_ids": [], "title": snap["title"], "format": "markdown"}

    def start():
        with transaction(conn):
            return runs.insert_run(conn, project_id, report_input, snap, experiment_id=exp["id"], config=config)

    def content(aid):
        _, reader, close = runtime.open_artifact(project_id, aid)
        try:
            return reader.read(2_000_000).decode("utf-8")
        finally:
            close()

    def fake_agent(ctx, request, env, claim_ids, metadata, provider, model_id, *, report_session):
        assert request["mode"] == "report"
        read_all(report_session)
        metadata["packages"] = {"deepagents": "offline-fixture"}
        report_session.accept_analysis(answer(e))

    safe_config = ("bedrock", "offline-fixture", {}, None, None)
    try:
        with patch.object(agent_runs, "selected_model_config", return_value=safe_config), patch.object(agent_runs, "_run_agent", side_effect=fake_agent):
            run = start()
            manager.execute_now(run["id"])
        saved = json.loads(runs.load_run_row(conn, project_id, run["id"])["doc"])
        assert saved["status"] == "succeeded", saved
        output = runs.results(conn, project_id, run["id"])
        assert "Scientific interpretation (AI)" in content(output["report_artifact_id"])
        prov = json.loads(content(saved["provenance_artifact_id"]))
        assert prov["model"] == "offline-fixture" and len(prov["agent_analysis"]["evidence_reads"]) == 5

        def provider_failure(ctx, *args, report_session, **kwargs):
            read_all(report_session)
            raise RunFailure("AGENT_PROVIDER_ERROR", "Simulated provider failure.")

        with patch.object(agent_runs, "selected_model_config", return_value=safe_config), patch.object(agent_runs, "_run_agent", side_effect=provider_failure):
            failed = start()
            manager.execute_now(failed["id"])
        failed_doc = json.loads(runs.load_run_row(conn, project_id, failed["id"])["doc"])
        assert failed_doc["status"] == "failed" and failed_doc["error"]["code"] == "AGENT_PROVIDER_ERROR"
        assert runs.results(conn, project_id, failed["id"])["report_artifact_id"] is None
        assert len(json.loads(content(failed_doc["provenance_artifact_id"]))["agent_analysis"]["evidence_reads"]) == 5

        def cancelled_agent(ctx, *args, report_session, **kwargs):
            read_all(report_session)
            with transaction(ctx.conn):
                runs.save_run(ctx.conn, ctx.run_id, status="cancelling")
            manager.request_cancel(ctx.run_id)
            raise RunFailure("CANCELLED", "Simulated cancellation.")

        with patch.object(agent_runs, "selected_model_config", return_value=safe_config), patch.object(agent_runs, "_run_agent", side_effect=cancelled_agent):
            cancelled = start()
            manager.execute_now(cancelled["id"])
        assert json.loads(runs.load_run_row(conn, project_id, cancelled["id"])["doc"])["status"] == "cancelled"
        assert runs.results(conn, project_id, cancelled["id"])["report_artifact_id"] is None

        missing_config = ("bedrock", "offline-fixture", {}, "MODEL_CONFIGURATION_MISSING", "Report model is not configured.")
        with patch.object(agent_runs, "selected_model_config", return_value=missing_config):
            missing = start()
            manager.execute_now(missing["id"])
        missing_doc = json.loads(runs.load_run_row(conn, project_id, missing["id"])["doc"])
        assert missing_doc["status"] == "failed" and missing_doc["error"]["code"] == "MODEL_CONFIGURATION_MISSING"
        assert runs.results(conn, project_id, missing["id"])["report_artifact_id"] is None

        from stellaris_api.report_calculations import execute_calculation
        calc_parent = start()
        with transaction(conn):
            runs.save_run(conn, calc_parent["id"], status="running")
        ctx = RunContext(manager, calc_parent["id"])
        source = '''import json, pathlib
manifest=json.load(open('/input/manifest.json'))
data=next(a for a in manifest['inputs'] if a['filename']=='report-evidence.json')
evidence=json.load(open(data['path']))['evidence']
values=[m['value'] for e in evidence for m in e['measurements'] if m['status']=='valid']
pathlib.Path('/output/calculation.json').write_text(json.dumps({'mean_px':sum(values)/len(values)}))
json.dump({'measurements':[],'claims':[],'artifacts':[{'local_key':'calculation','path':'calculation.json',
'kind':'dataset','origin':'generated','mime_type':'application/json','parents':[{'input_artifact_id':data['artifact_id']}]}],
'warnings':[]},open('/output/result.json','w'))
'''
        try:
            before = conn.execute("SELECT doc FROM experiments WHERE id=?", (exp["id"],)).fetchone()["doc"]
            result = execute_calculation(ctx, source, [], [e])
            assert result["status"] == "succeeded", result
            assert '"mean_px": 10.0' in result["output_text"][0]["text"], result
            assert result["code_artifact_id"] and result["evidence_artifact_id"] and result["provenance_artifact_id"]
            child_prov = json.loads(content(result["provenance_artifact_id"]))
            assert child_prov["execution"]["network"] == "none", child_prov["execution"]
            assert before == conn.execute("SELECT doc FROM experiments WHERE id=?", (exp["id"],)).fetchone()["doc"]
            ctx.finish("cancelled", summary="Provider-free calculation check finished.")
        finally:
            ctx.close()
        print(f"PASS: real Docker report publication, provider-failure audit/no fallback, isolated calculation/provenance, unchanged experiment. Project {project_id}")
    finally:
        runtime.client().containers.get("stellaris-" + project_id).stop(timeout=5)
        conn.close()


if __name__ == "__main__":
    local_checks()
    if "--docker" in sys.argv:
        docker_checks()
