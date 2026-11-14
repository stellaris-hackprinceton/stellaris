"""Provider-free terminal message and orphan-process regression (run in API image)."""
import json
import os
import sys
import tempfile
import time
import uuid
from types import SimpleNamespace
from flask import Flask
from stellaris_api import db, runs
from stellaris_api.chat import _message, _save_message
from stellaris_api.http import now_ts

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, 'state.sqlite')
    db.init_db(path)
    conn = db.connect(path)
    app = Flask(__name__)
    app.config['STELLARIS'] = SimpleNamespace(max_run_log_bytes=64, max_project_bytes=32*1024*1024)
    with db.transaction(conn):
        conn.execute("INSERT INTO projects VALUES ('p','test','',NULL,'active',1,?,?,'ready',NULL)", (now_ts(), now_ts()))
    def accepted():
        with app.app_context(), db.transaction(conn):
            user = _message('p','user','test')
            assistant = _message('p','assistant','partial response',status='streaming')
            run = runs.insert_run(conn,'p',{'kind':'agent','user_message_id':user['id'],
                                          'assistant_message_id':assistant['id'],'attachment_ids':[],
                                          'context_artifact_ids':[]},{})
            assistant['run_id'] = run['id']
            _save_message(conn,user)
            _save_message(conn,assistant)
        return run,assistant
    def check_message(run, assistant):
        doc = json.loads(conn.execute('SELECT doc FROM messages WHERE id=?',(assistant['id'],)).fetchone()[0])
        assert doc['status']=='interrupted' and doc['content_markdown']=='partial response'
        events = conn.execute("SELECT type FROM events WHERE run_id=? ORDER BY sequence",(run['id'],)).fetchall()
        names=[r[0] for r in events]
        assert names[-1]=='run.updated' and 'message.updated' in names
    run, assistant = accepted()
    with db.transaction(conn): runs.save_run(conn,run['id'],status='cancelled')
    check_message(run,assistant)
    run, assistant = accepted()
    with db.transaction(conn):
        runs.save_run(conn,run['id'],status='running')
        queued,lost = runs.recover_after_restart(conn)
    assert run['id'] in lost and not queued
    check_message(run,assistant)
    conn.close()
print('PASS: queued cancellation and restart finalize partial messages before terminal run events')

if len(sys.argv)>1:
    from stellaris_api.agent_runs import cleanup_lost_agents
    from stellaris_api.config import load_config
    from stellaris_api.runtime import ProjectRuntime
    runtime=ProjectRuntime(load_config())
    project=sys.argv[1]
    container=runtime.client().containers.get('stellaris-'+project)
    run_id='run_'+uuid.uuid4().hex
    request='/tmp/stellaris-agent-'+run_id+'.json'
    pidfile='/tmp/stellaris-agent-'+run_id+'.pid'
    # A harmless process with matching run-specific argv, deliberately ignoring TERM.
    code="import os,signal,sys,time; open(sys.argv[1],'w').write(str(os.getpid())); open(sys.argv[2],'w').write('{}'); signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)"
    container.exec_run(['python','-c',code,pidfile,request,'/opt/stellaris/agent_runner.py'],detach=True)
    pid=None
    try:
        for _ in range(30):
            result=container.exec_run(['cat',pidfile])
            if result.exit_code==0:
                pid=int(result.output.strip());break
            time.sleep(.1)
        assert pid is not None
        started=time.monotonic()
        cleanup_lost_agents(runtime,[(project,run_id)])
        assert time.monotonic()-started<10
        probe_code=("import os,sys; p='/proc/'+sys.argv[1]; "
                    "args=open(p+'/cmdline','rb').read().split(bytes([0])) if os.path.exists(p+'/cmdline') else []; "
                    "state=open(p+'/stat').read().split()[2] if os.path.exists(p+'/stat') else 'gone'; "
                    "sys.exit(0 if sys.argv[2].encode() in args and state!='Z' else 1)")
        for _ in range(25):
            probe=container.exec_run(['python','-c',probe_code,str(pid),request])
            if probe.exit_code!=0:break
            time.sleep(.1)
        assert probe.exit_code!=0,'a matching live orphan process survived cleanup'
        assert container.exec_run(['test','-e',pidfile]).exit_code!=0
        assert container.exec_run(['test','-e',request]).exit_code!=0
    finally:
        if pid:
            container.exec_run(['python','-c',
                "import os,signal,sys; p='/proc/'+sys.argv[1]+'/cmdline'; args=open(p,'rb').read().split(bytes([0])) if os.path.exists(p) else []; sys.argv[2].encode() in args and os.kill(int(sys.argv[1]),signal.SIGKILL)",str(pid),request])
    print('PASS: run-specific orphan ignores TERM, is killed within grace, and temporary files are removed')
