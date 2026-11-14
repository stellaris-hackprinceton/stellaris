"""Focused regression: quota reservations and cancelled-result cleanup. Run in API image."""
import io
import json
import os
import tempfile
from types import SimpleNamespace
from flask import Flask
from stellaris_api import db, runs
from stellaris_api.artifacts import commit_artifact
from stellaris_api.errors import ApiError
from stellaris_api.executor import RunContext, RunManager
from stellaris_api.http import now_ts

class Storage:
    def __init__(self): self.files = {}
    def store_artifact(self, project, artifact, path, _tmp):
        with open(path, 'rb') as source: self.files[(project, artifact)] = source.read()
    def open_artifact(self, project, artifact):
        data = self.files[(project, artifact)]
        reader = io.BytesIO(data)
        return len(data), reader, reader.close
    def discard_artifact(self, project, artifact): self.files.pop((project, artifact), None)

with tempfile.TemporaryDirectory() as tmp:
    cfg = SimpleNamespace(db_path=os.path.join(tmp, 'test.sqlite'), upload_tmp_dir=tmp,
                          max_file_bytes=1024*1024, max_project_bytes=16*1024*1024+64+4096,
                          max_run_log_bytes=64, max_log_chunk_bytes=256)
    db.init_db(cfg.db_path)
    conn = db.connect(cfg.db_path)
    app = Flask(__name__)
    app.config['STELLARIS'] = cfg
    runtime = Storage()
    manager = RunManager(cfg, runtime)
    def context(project):
        with app.app_context(), db.transaction(conn):
            conn.execute("INSERT INTO projects VALUES (?,?,?,NULL,'active',1,?,?,'ready',NULL)",
                         (project, project, '', now_ts(), now_ts()))
            run = runs.insert_run(conn, project, {'kind':'analysis'}, {'input':{}})
            runs.save_run(conn, run['id'], status='running', started_at=now_ts())
        return RunContext(manager, run['id'])
    ctx = context('quota')
    output = ctx.stage_text('x'*4000, filename='data.csv', mime_type='text/csv', kind='dataset', origin='generated')
    ctx.commit_now([output])
    try:
        ctx.stage_text('y'*200, filename='extra.csv', mime_type='text/csv', kind='dataset', origin='generated')
        raise AssertionError('outputs consumed the reserved audit budget')
    except ApiError as error: assert error.code == 'PROJECT_QUOTA_EXCEEDED'
    result = ctx.finish('failed', error={'code':'INVALID_OUTPUT','message':'test failure','retryable':False})
    assert result['provenance_artifact_id'] and result['status'] == 'failed'
    assert ('quota', output['id']) in runtime.files, 'cleanup removed a published artifact'
    assert ('quota', result['provenance_artifact_id']) in runtime.files, 'audit reservation failed'
    ctx.close()
    ctx = context('cancel')
    report = ctx.stage_text('pending report', filename='report.md', mime_type='text/markdown', kind='report', origin='generated')
    prov = ctx.stage_text(json.dumps({'outputs':[{'artifact_id':report['id']}], 'execution':{}}),
                          filename='provenance.json', mime_type='application/json', kind='environment', origin='generated')
    with db.transaction(ctx.conn): runs.save_run(ctx.conn, ctx.run_id, status='cancelling')
    result = ctx.finish('succeeded', summary='report succeeded', publish=lambda c: commit_artifact(c, report), provenance=prov)
    assert result['status'] == 'cancelled'
    assert ('cancel', report['id']) not in runtime.files
    manifest = json.loads(runtime.files[('cancel',result['provenance_artifact_id'])])
    assert manifest['outputs'] == [] and manifest['execution']['published_run_status'] == 'cancelled'
    assert ctx.conn.execute('SELECT 1 FROM artifacts WHERE id=?',(report['id'],)).fetchone() is None
    ctx.close()
    conn.close()
print('PASS: audit quota, published-file preservation, cancellation provenance and staged cleanup')
