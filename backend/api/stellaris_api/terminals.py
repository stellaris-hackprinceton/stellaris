"""Project-scoped interactive PTY sessions, isolated from research and execution workers."""
import base64
import hashlib
import json
import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, request

from .db import connect, transaction
from .errors import ApiError
from .events import record_event
from .http import (canonical_sha256, dumps, idempotency_key, json_body, json_response,
                   new_id, now_ts, page_limit, encode_cursor, decode_cursor)
from .projects import load_visible, load_writable

OUTPUT_LIMIT = 2 * 1024 * 1024
CHUNK = 4096
INPUT_LIMIT = 16 * 1024
MANAGED = "stellaris.managed"
ROLE = "stellaris.role"


def _idempotency_cutoff():
    return (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS terminals (
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), status TEXT NOT NULL,
      rows INTEGER NOT NULL, cols INTEGER NOT NULL, created_at TEXT NOT NULL, finished_at TEXT,
      error TEXT, output_bytes INTEGER NOT NULL DEFAULT 0, last_output_sequence INTEGER NOT NULL DEFAULT 0,
      last_input_sequence INTEGER NOT NULL DEFAULT 0, container_id TEXT, volume_name TEXT NOT NULL,
      UNIQUE(project_id, id));
    CREATE INDEX IF NOT EXISTS terminals_project ON terminals(project_id, created_at, id);
    CREATE UNIQUE INDEX IF NOT EXISTS terminals_one_active_per_project ON terminals(project_id)
      WHERE status IN ('starting','running','closing');
    CREATE TABLE IF NOT EXISTS terminal_output (
      terminal_id TEXT NOT NULL REFERENCES terminals(id), sequence INTEGER NOT NULL,
      occurred_at TEXT NOT NULL, data BLOB NOT NULL, PRIMARY KEY(terminal_id, sequence));
    CREATE TABLE IF NOT EXISTS terminal_inputs (
      terminal_id TEXT NOT NULL REFERENCES terminals(id), sequence INTEGER NOT NULL,
      body_sha256 TEXT NOT NULL, PRIMARY KEY(terminal_id, sequence));
    CREATE TABLE IF NOT EXISTS terminal_idempotency (
      project_id TEXT NOT NULL, scope TEXT NOT NULL, key TEXT NOT NULL, body_sha256 TEXT NOT NULL,
      terminal_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT '', PRIMARY KEY(project_id, scope, key));
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(terminal_idempotency)")}
    if "created_at" not in columns:
        conn.execute("ALTER TABLE terminal_idempotency ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")


def _public(row):
    return {"id": row["id"], "project_id": row["project_id"], "status": row["status"],
            "rows": row["rows"], "cols": row["cols"], "created_at": row["created_at"],
            "finished_at": row["finished_at"],
            "error": json.loads(row["error"]) if row["error"] else None,
            "output_bytes": row["output_bytes"],
            "last_output_sequence": row["last_output_sequence"],
            "last_input_sequence": row["last_input_sequence"], "transcript_artifact_id": None}


class TerminalSettings:
    """Read terminal settings only; never forward a broad host environment."""
    def __init__(self):
        def value(name, default):
            return os.environ.get(name, "").strip() or default
        self.image = value("STELLARIS_TERMINAL_IMAGE", "stellaris-terminal:dev")
        self.duration_s = min(3600, max(60, int(value("STELLARIS_TERMINAL_DURATION_S", "3600"))))
        self.cpus = min(1.0, max(.1, float(value("STELLARIS_TERMINAL_CPUS", ".5"))))
        self.memory_mb = min(512, max(64, int(value("STELLARIS_TERMINAL_MEMORY_MB", "256"))))
        self.pids = min(128, max(16, int(value("STELLARIS_TERMINAL_PIDS", "64"))))


class TerminalManager:
    def __init__(self, config, runtime, settings=None):
        self.config, self.runtime = config, runtime
        self.settings = settings or TerminalSettings()
        self._threads, self._sockets = {}, {}
        self._lock = threading.RLock()
        self._session_locks = {}
        self._timers = {}
        self._available = False

    def available(self):
        try:
            client = self.runtime.client()
            client.ping()
            client.images.get(self.settings.image)
            return True
        except Exception:
            return False

    def start(self):
        try:
            client = self.runtime.client()
            for c in client.containers.list(all=True, filters={"label": [f"{MANAGED}=true", f"{ROLE}=terminal"]}):
                c.remove(force=True)
            self._available = True
        except Exception:
            self._available = False
        conn = connect(self.config.db_path)
        try:
            with transaction(conn):
                rows = conn.execute("SELECT id, project_id FROM terminals WHERE status IN ('starting','running','closing')").fetchall()
                for row in rows:
                    self._finish(conn, row["id"], row["project_id"], "lost", "Session ended when the backend restarted.")
        finally:
            conn.close()

    def recover(self):
        return None

    def close_all(self):
        for sid in list(self._sockets):
            self.close(sid)

    def _session_lock(self, sid):
        with self._lock:
            return self._session_locks.setdefault(sid, threading.RLock())

    def _launch(self, sid, project_id, volume, rows, cols):
        conn = connect(self.config.db_path)
        try:
            client = self.runtime.client()
            try:
                vol = client.volumes.get(volume)
            except Exception:
                # A volume that disappeared after any prior session is data loss, not a
                # first-use provision. Never make an empty replacement look like recovery.
                prior = conn.execute("SELECT 1 FROM terminals WHERE project_id=? AND id<>? LIMIT 1", (project_id, sid)).fetchone()
                if prior:
                    raise RuntimeError("persistent terminal volume is missing")
                vol = client.volumes.create(name=volume, labels={MANAGED: "true", ROLE: "terminal", "stellaris.project": project_id})
            labels = {MANAGED: "true", ROLE: "terminal", "stellaris.project": project_id, "stellaris.session": sid}
            ctr = client.containers.create(self.settings.image, command=["--noprofile", "--norc"],
                name=f"stellaris-terminal-{sid}", labels=labels, stdin_open=True, tty=True,
                working_dir="/workspace", user="10004:10004", network_mode="none", network_disabled=True,
                read_only=True, tmpfs={"/tmp": "rw,noexec,nosuid,size=32m,uid=10004,gid=10004",
                                      "/home/terminal": "rw,nosuid,size=16m,uid=10004,gid=10004,mode=0700"},
                volumes={volume: {"bind": "/workspace", "mode": "rw"}},
                cap_drop=["ALL"], security_opt=["no-new-privileges:true"], pids_limit=self.settings.pids,
                mem_limit=f"{self.settings.memory_mb}m", nano_cpus=int(self.settings.cpus * 1_000_000_000),
                environment={"HOME": "/home/terminal", "TERM": "xterm-256color"})
            ctr.start()
            ctr.resize(height=rows, width=cols)
            sock = ctr.attach_socket(params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1})
            raw = getattr(sock, "_sock", sock)
            raw.settimeout(None)  # An idle interactive session is bounded by our session timer.
            with self._lock:
                with transaction(conn):
                    row = conn.execute("SELECT * FROM terminals WHERE id=?", (sid,)).fetchone()
                    if not row or row["status"] != "starting":
                        try: raw.close()
                        except Exception: pass
                        ctr.remove(force=True)
                        return
                    self._sockets[sid] = (ctr, raw)
                    conn.execute("UPDATE terminals SET status='running',container_id=? WHERE id=?", (ctr.id, sid))
                    rec = conn.execute("SELECT * FROM terminals WHERE id=?", (sid,)).fetchone()
                    record_event(conn, project_id, "terminal.updated", {"terminal": _public(rec)})
            timer = threading.Timer(self.settings.duration_s, lambda: self.close(sid, reason="time_limit"))
            timer.daemon = True
            self._timers[sid] = timer
            timer.start()
            t = threading.Thread(target=self._read, args=(sid, project_id, raw), daemon=True)
            self._threads[sid] = t
            t.start()
        except Exception:
            if "ctr" in locals():
                try: ctr.remove(force=True)
                except Exception: pass
            self._stop_container(sid)
            with transaction(conn):
                self._finish(conn, sid, project_id, "failed", "Terminal could not be started.", code="start_failed")
        finally:
            conn.close()

    def _read(self, sid, project_id, raw):
        try:
            while True:
                data = raw.recv(CHUNK)
                if not data: break
                conn = connect(self.config.db_path)
                try:
                    with transaction(conn):
                        row = conn.execute("SELECT * FROM terminals WHERE id=?", (sid,)).fetchone()
                        if not row or row["status"] != "running": break
                        remain = OUTPUT_LIMIT - row["output_bytes"]
                        if remain <= 0:
                            self._finish(conn, sid, project_id, "closed", "Terminal output limit reached.", code="output_limit")
                            break
                        data = data[:min(CHUNK, remain)]
                        seq = row["last_output_sequence"] + 1
                        conn.execute("INSERT INTO terminal_output VALUES(?,?,?,?)", (sid, seq, now_ts(), data))
                        conn.execute("UPDATE terminals SET output_bytes=output_bytes+?,last_output_sequence=? WHERE id=?", (len(data), seq, sid))
                        record_event(conn, project_id, "terminal.output", {"terminal_id": sid, "sequence": seq, "data_base64": base64.b64encode(data).decode()})
                        rec = conn.execute("SELECT * FROM terminals WHERE id=?", (sid,)).fetchone()
                        record_event(conn, project_id, "terminal.updated", {"terminal": _public(rec)})
                        if len(data) == remain:
                            self._finish(conn, sid, project_id, "closed", "Terminal output limit reached.", code="output_limit")
                            should_stop = True
                        else:
                            should_stop = False
                finally: conn.close()
                if should_stop:
                    break
        except (OSError, socket.error):
            pass
        finally:
            conn = connect(self.config.db_path)
            try:
                with transaction(conn):
                    row = conn.execute("SELECT status FROM terminals WHERE id=?", (sid,)).fetchone()
                    if row and row["status"] == "running": self._finish(conn, sid, project_id, "closed", "Terminal process exited.", code="process_exited")
            finally: conn.close()
            self._stop_container(sid)

    def _finish(self, conn, sid, project_id, status, message, code="closed"):
        final_status = status if status in ("closed", "failed") else "closed"
        changed = conn.execute("UPDATE terminals SET status=?,finished_at=?,error=? WHERE id=? AND status IN ('starting','running','closing')",
                     (final_status, now_ts(), dumps({"code": code, "message": message}), sid)).rowcount
        row = conn.execute("SELECT * FROM terminals WHERE id=?", (sid,)).fetchone()
        if row and changed: record_event(conn, project_id, "terminal.updated", {"terminal": _public(row)})

    def _stop_container(self, sid):
        with self._lock:
            pair = self._sockets.pop(sid, None)
            timer = self._timers.pop(sid, None)
        if timer: timer.cancel()
        if pair:
            try: pair[1].close()
            except Exception: pass
            try: pair[0].remove(force=True)
            except Exception: pass

    def close(self, sid, reason="closed"):
        with self._session_lock(sid):
            conn = connect(self.config.db_path)
            try:
                row = conn.execute("SELECT * FROM terminals WHERE id=?", (sid,)).fetchone()
                if not row: return
                with transaction(conn):
                    self._finish(conn, sid, row["project_id"], "closed", "Terminal closed." if reason == "closed" else "Terminal time limit reached.", code=reason)
                self._stop_container(sid)
            finally: conn.close()


def create_blueprint(manager):
    bp = Blueprint("terminals", __name__, url_prefix="/api/v1/projects")
    def get_session(conn, project, sid):
        row = conn.execute("SELECT * FROM terminals WHERE id=? AND project_id=?", (sid, project)).fetchone()
        if row is None: raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
        return row
    def dimensions(body):
        if set(body)-{"rows","cols"}: raise ApiError(422,"VALIDATION_FAILED","Unknown field.")
        r,c=body.get("rows",24),body.get("cols",80)
        if type(r) is not int or type(c) is not int or not 2<=r<=200 or not 2<=c<=500: raise ApiError(422,"VALIDATION_FAILED","rows and cols are out of range.")
        return r,c
    @bp.post("/<project_id>/terminals")
    def create(project_id):
        load_writable(g.db, project_id); body=json_body(); key=idempotency_key(); rows,cols=dimensions(body)
        if not manager.available(): raise ApiError(503,"TERMINAL_UNAVAILABLE","Terminal runtime or image is unavailable.",retryable=True)
        digest=canonical_sha256(body); scope="POST /terminals"
        with transaction(g.db):
            g.db.execute("DELETE FROM terminal_idempotency WHERE created_at < ?", (_idempotency_cutoff(),))
            old=g.db.execute("SELECT * FROM terminal_idempotency WHERE project_id=? AND scope=? AND key=?",(project_id,scope,key)).fetchone()
            if old:
                if old["body_sha256"]!=digest: raise ApiError(409,"IDEMPOTENCY_CONFLICT","Idempotency-Key was used with another request.")
                row=get_session(g.db,project_id,old["terminal_id"])
                return json_response(_public(row),202,{"Idempotent-Replayed":"true"})
            if g.db.execute("SELECT 1 FROM terminals WHERE project_id=? AND status IN ('starting','running','closing')", (project_id,)).fetchone():
                raise ApiError(409,"TERMINAL_ACTIVE","This project already has an active terminal.")
            sid=new_id("trm")
            g.db.execute("INSERT INTO terminal_idempotency(project_id,scope,key,body_sha256,terminal_id,created_at) VALUES(?,?,?,?,?,?)",(project_id,scope,key,digest,sid,now_ts()))
            volume=f"stellaris-terminal-{project_id}"
            g.db.execute("INSERT INTO terminals(id,project_id,status,rows,cols,created_at,volume_name) VALUES(?,?,?,?,?,?,?)",(sid,project_id,"starting",rows,cols,now_ts(),volume))
            row=get_session(g.db,project_id,sid); record_event(g.db,project_id,"terminal.updated",{"terminal":_public(row)})
        threading.Thread(target=manager._launch,args=(sid,project_id,volume,rows,cols),daemon=True).start()
        return json_response(_public(row),202)
    @bp.get("/<project_id>/terminals")
    def listing(project_id):
        load_visible(g.db,project_id); limit=page_limit(); cursor=request.args.get("cursor"); after=None
        if cursor:
            state=decode_cursor(cursor)
            if state.get("v")!=1 or state.get("t")!="terminals" or state.get("p")!=project_id or not isinstance(state.get("c"),str) or not isinstance(state.get("i"),str):
                raise ApiError(400,"INVALID_CURSOR","cursor is invalid.")
            after=(state["c"],state["i"])
        if after:
            rows=g.db.execute("SELECT * FROM terminals WHERE project_id=? AND (created_at,id)>(?,?) ORDER BY created_at,id LIMIT ?",(project_id,*after,limit+1)).fetchall()
        else:
            rows=g.db.execute("SELECT * FROM terminals WHERE project_id=? ORDER BY created_at,id LIMIT ?",(project_id,limit+1)).fetchall()
        next_cursor=encode_cursor({"v":1,"t":"terminals","p":project_id,"c":rows[limit-1]["created_at"],"i":rows[limit-1]["id"]}) if len(rows)>limit else None
        return json_response({"items":[_public(r) for r in rows[:limit]],"next_cursor":next_cursor})
    @bp.get("/<project_id>/terminals/<sid>")
    def detail(project_id,sid): load_visible(g.db,project_id); return json_response(_public(get_session(g.db,project_id,sid)))
    @bp.put("/<project_id>/terminals/<sid>/input/<int:sequence>")
    def input_bytes(project_id,sid,sequence):
        load_writable(g.db,project_id); body=json_body()
        if set(body)!={"data_base64"} or not isinstance(body["data_base64"],str): raise ApiError(422,"VALIDATION_FAILED","data_base64 is required.")
        try: data=base64.b64decode(body["data_base64"],validate=True)
        except Exception: raise ApiError(422,"VALIDATION_FAILED","data_base64 must be valid base64.")
        if len(data)>INPUT_LIMIT: raise ApiError(413,"REQUEST_TOO_LARGE","Terminal input exceeds 16 KiB.")
        digest=hashlib.sha256(data).hexdigest()
        with manager._session_lock(sid):
            with transaction(g.db):
                row=get_session(g.db,project_id,sid); receipt=g.db.execute("SELECT body_sha256 FROM terminal_inputs WHERE terminal_id=? AND sequence=?",(sid,sequence)).fetchone()
                if receipt:
                    if receipt[0]!=digest: raise ApiError(409,"INPUT_CONFLICT","Sequence was already used with different bytes.")
                    return json_response(_public(row),202,{"Idempotent-Replayed":"true"})
                expected=row["last_input_sequence"]+1
                if sequence!=expected: raise ApiError(409,"INPUT_SEQUENCE_GAP","Input sequence is not next.",details={"expected_sequence":expected})
                if row["status"]!="running": raise ApiError(409,"TERMINAL_NOT_RUNNING","Terminal is not running.")
                if expected > 10_000: raise ApiError(409,"INPUT_LIMIT","Terminal input receipt limit reached.")
                g.db.execute("INSERT INTO terminal_inputs VALUES(?,?,?)",(sid,sequence,digest)); g.db.execute("UPDATE terminals SET last_input_sequence=? WHERE id=?",(sequence,sid))
                row=get_session(g.db,project_id,sid); record_event(g.db,project_id,"terminal.updated",{"terminal":_public(row)})
            pair=manager._sockets.get(sid)
            if not pair: raise ApiError(409,"TERMINAL_INPUT_UNKNOWN","Input was recorded but delivery is unknown; it will not be resent.")
            try: pair[1].sendall(data)
            except OSError: raise ApiError(409,"TERMINAL_INPUT_UNKNOWN","Input was recorded but delivery is unknown; it will not be resent.")
        return json_response(_public(row),202)
    @bp.put("/<project_id>/terminals/<sid>/size")
    def resize(project_id,sid):
        load_writable(g.db,project_id); rows,cols=dimensions(json_body())
        with manager._session_lock(sid):
            rec=get_session(g.db,project_id,sid)
            if rec["status"]!="running": raise ApiError(409,"TERMINAL_NOT_RUNNING","Terminal is not running.")
            pair=manager._sockets.get(sid)
            if not pair: raise ApiError(503,"TERMINAL_UNAVAILABLE","Terminal connection is unavailable.",retryable=True)
            try: pair[0].resize(height=rows,width=cols)
            except Exception: raise ApiError(503,"TERMINAL_UNAVAILABLE","Terminal could not be resized.",retryable=True)
            with transaction(g.db):
                g.db.execute("UPDATE terminals SET rows=?,cols=? WHERE id=?",(rows,cols,sid)); rec=get_session(g.db,project_id,sid); record_event(g.db,project_id,"terminal.updated",{"terminal":_public(rec)})
            return json_response(_public(rec))
    @bp.post("/<project_id>/terminals/<sid>/close")
    def close(project_id,sid):
        load_visible(g.db,project_id); body=json_body()
        if body: raise ApiError(422,"VALIDATION_FAILED","Close body must be an empty object.")
        key=idempotency_key(); scope=f"POST /terminals/{sid}/close"; digest=canonical_sha256(body)
        with transaction(g.db):
            g.db.execute("DELETE FROM terminal_idempotency WHERE created_at < ?", (_idempotency_cutoff(),))
            rec=get_session(g.db,project_id,sid)
            old=g.db.execute("SELECT * FROM terminal_idempotency WHERE project_id=? AND scope=? AND key=?",(project_id,scope,key)).fetchone()
            if old:
                if old["body_sha256"]!=digest: raise ApiError(409,"IDEMPOTENCY_CONFLICT","Idempotency-Key was used with another request.")
                return json_response(_public(rec),200,{"Idempotent-Replayed":"true"})
            g.db.execute("INSERT INTO terminal_idempotency(project_id,scope,key,body_sha256,terminal_id,created_at) VALUES(?,?,?,?,?,?)",(project_id,scope,key,digest,sid,now_ts()))
        manager.close(sid)
        return json_response(_public(get_session(g.db,project_id,sid)))
    @bp.get("/<project_id>/terminals/<sid>/output")
    def output(project_id,sid):
        load_visible(g.db,project_id); get_session(g.db,project_id,sid)
        try: after=int(request.args.get("after_sequence","0")); limit=int(request.args.get("limit","50"))
        except ValueError: raise ApiError(400,"INVALID_QUERY","after_sequence and limit must be integers.")
        if after<0 or not 1<=limit<=100: raise ApiError(400,"INVALID_QUERY","Invalid output page bounds.")
        cursor=request.args.get("cursor")
        initial_after=after
        if cursor:
            state=decode_cursor(cursor)
            saved=state.get("x")
            if (state.get("v")!=1 or state.get("t")!="terminal_output" or state.get("p")!=project_id
                    or not isinstance(saved,dict) or set(saved)!={"terminal_id","after_sequence"}
                    or saved.get("terminal_id")!=sid or type(saved.get("after_sequence")) is not int
                    or saved["after_sequence"]<0 or type(state.get("c")) is not int
                    or state["c"]<saved["after_sequence"]):
                raise ApiError(400,"INVALID_CURSOR","cursor is invalid.")
            if request.args.get("after_sequence") is not None and after!=saved["after_sequence"]:
                raise ApiError(400,"INVALID_QUERY","after_sequence must match the cursor's filter.")
            initial_after=saved["after_sequence"]
            after=state["c"]
        rows=g.db.execute("SELECT * FROM terminal_output WHERE terminal_id=? AND sequence>? ORDER BY sequence LIMIT ?",(sid,after,limit+1)).fetchall()
        next_cursor=encode_cursor({"v":1,"t":"terminal_output","p":project_id,"x":{"terminal_id":sid,"after_sequence":initial_after},"c":rows[limit-1]["sequence"]}) if len(rows)>limit else None
        return json_response({"items":[{"sequence":r["sequence"],"occurred_at":r["occurred_at"],"data_base64":base64.b64encode(r["data"]).decode()} for r in rows[:limit]],"next_cursor":next_cursor})
    @bp.get("/<project_id>/terminals/<sid>/transcript")
    def transcript(project_id,sid):
        load_visible(g.db,project_id); get_session(g.db,project_id,sid)
        from flask import Response
        chunks=g.db.execute("SELECT data FROM terminal_output WHERE terminal_id=? ORDER BY sequence",(sid,)).fetchall()
        return Response((r[0] for r in chunks),mimetype="application/octet-stream",headers={"Content-Disposition":f'attachment; filename="{sid}.bin"'})
    return bp
