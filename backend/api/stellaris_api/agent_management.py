"""Project agent organization permissions, request review, and bounded catalog tools."""

import json
import logging
import re
import sqlite3

from flask import Blueprint, current_app, g, request

from . import catalog, idempotency
from .db import transaction
from .errors import ApiError
from .events import record_event
from .http import decode_cursor, dumps, encode_cursor, etag, idempotency_key, json_body, json_response, new_id, now_ts, page_limit, parse_if_match
from .projects import load_visible, load_writable
from .validation import Validator

log = logging.getLogger(__name__)
bp = Blueprint("agent_management", __name__, url_prefix="/api/v1/projects")
MODES = ("off", "ask", "allow")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")


def init_schema(conn):
    """Idempotently install additive agent control and chat generation tables/columns."""
    conn.execute("CREATE TABLE IF NOT EXISTS agent_settings (project_id TEXT PRIMARY KEY REFERENCES projects(id), "
                 "organization_permission TEXT NOT NULL CHECK(organization_permission IN ('off','ask','allow')), "
                 "revision INTEGER NOT NULL, updated_at TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS organization_requests (id TEXT PRIMARY KEY, project_id TEXT NOT NULL "
                 "REFERENCES projects(id), status TEXT NOT NULL CHECK(status IN ('pending','applied','rejected','failed')), "
                 "operation TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                 "error TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS organization_requests_page ON organization_requests(project_id,status,created_at,id)")
    conn.execute("CREATE TABLE IF NOT EXISTS chat_state (project_id TEXT PRIMARY KEY REFERENCES projects(id), "
                 "generation INTEGER NOT NULL, cleared_at TEXT NOT NULL)")
    columns = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
    if "chat_generation" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN chat_generation INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE TABLE IF NOT EXISTS organization_decisions (request_id TEXT PRIMARY KEY REFERENCES organization_requests(id), "
                 "decision TEXT NOT NULL, response TEXT NOT NULL, created_at TEXT NOT NULL)")


def _settings(conn, project_id):
    row = conn.execute("SELECT * FROM agent_settings WHERE project_id=?", (project_id,)).fetchone()
    if row is None:
        project = conn.execute("SELECT created_at FROM projects WHERE id=?", (project_id,)).fetchone()
        return {"project_id": project_id, "organization_permission": "ask", "revision": 1,
                "updated_at": project["created_at"] if project else None}
    return {"project_id": project_id, "organization_permission": row["organization_permission"],
            "revision": row["revision"], "updated_at": row["updated_at"]}


@bp.get("/<project_id>/agent-settings")
def get_agent_settings(project_id):
    load_visible(g.db, project_id)
    value = _settings(g.db, project_id)
    return json_response(value, headers={"ETag": etag(value["revision"])})


@bp.patch("/<project_id>/agent-settings")
def patch_agent_settings(project_id):
    body = json_body()
    v = Validator()
    v.unknown(body, {"organization_permission"})
    mode = v.enum(body, "organization_permission", MODES)
    v.check()
    expected = parse_if_match()
    if expected is None:
        raise ApiError(428, "PRECONDITION_REQUIRED", "If-Match with the settings' current ETag is required.")
    with transaction(g.db):
        load_writable(g.db, project_id)
        current = _settings(g.db, project_id)
        if expected != current["revision"]:
            raise ApiError(412, "REVISION_CONFLICT", "Agent settings changed since they were loaded.",
                           details={"current_revision": current["revision"]})
        if mode == current["organization_permission"]:
            value = current
        else:
            ts = now_ts(); revision = current["revision"] + 1
            g.db.execute("INSERT INTO agent_settings(project_id,organization_permission,revision,updated_at) VALUES(?,?,?,?) "
                         "ON CONFLICT(project_id) DO UPDATE SET organization_permission=excluded.organization_permission, "
                         "revision=excluded.revision,updated_at=excluded.updated_at", (project_id, mode, revision, ts))
            value = {"project_id": project_id, "organization_permission": mode, "revision": revision, "updated_at": ts}
            record_event(g.db, project_id, "agent.settings.updated", {"settings": value})
    return json_response(value, headers={"ETag": etag(value["revision"])})


def _request_obj(row):
    error = row["error"]
    if error:
        try:
            error = json.loads(error)
        except (TypeError, ValueError):
            error = {"code": "ORGANIZATION_FAILED", "message": str(error)}
    return {"id": row["id"], "project_id": row["project_id"], "status": row["status"],
            "operation": json.loads(row["operation"]), "revision": row["revision"], "created_at": row["created_at"],
            "updated_at": row["updated_at"], "error": error}


@bp.get("/<project_id>/organization-requests")
def list_organization_requests(project_id):
    load_visible(g.db, project_id)
    status = request.args.get("status", "pending")
    if status not in ("pending", "applied", "rejected", "failed", "all"):
        raise ApiError(400, "INVALID_QUERY", "status has an unsupported value.")
    limit = page_limit()
    after = None
    raw_cursor = request.args.get("cursor")
    if raw_cursor:
        state = decode_cursor(raw_cursor)
        if state.get("v") != 1 or state.get("p") != project_id or state.get("s") != status \
                or not isinstance(state.get("c"), str) or not isinstance(state.get("i"), str):
            raise ApiError(400, "INVALID_CURSOR", "cursor is invalid.")
        after = (state["c"], state["i"])
    sql = "SELECT * FROM organization_requests WHERE project_id=?"
    args = [project_id]
    if status != "all":
        sql += " AND status=?"; args.append(status)
    if after:
        sql += " AND (created_at > ? OR (created_at = ? AND id > ?))"; args.extend((after[0], after[0], after[1]))
    rows = g.db.execute(sql + " ORDER BY created_at,id LIMIT ?", (*args, limit + 1)).fetchall()
    items = [_request_obj(row) for row in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor({"v": 1, "p": project_id, "s": status, "c": last["created_at"], "i": last["id"]})
    return json_response({"items": items, "next_cursor": next_cursor})


def _open_catalog(conn, config, project_id):
    try:
        cat = catalog.open_catalog(config, project_id)
        catalog.sync(conn, cat, project_id)
        return cat
    except (catalog.CatalogUnavailable, catalog.SyncFailed) as exc:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "The project's file catalog is unavailable.", retryable=True) from exc


def _apply(cat, project_id, operation, request_id):
    """Atomically apply one bounded user organization request in the per-project catalog."""
    cat.execute("CREATE TABLE IF NOT EXISTS organization_applied_requests(request_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    with transaction(cat):
        if cat.execute("SELECT 1 FROM organization_applied_requests WHERE request_id=?", (request_id,)).fetchone():
            return {"replayed": True}
        changes = []
        kind = operation["operation"]
        if kind in ("assign_tags", "remove_tags"):
            fid = operation["file_id"]
            file = cat.execute("SELECT id,status,revision FROM files WHERE id=?", (fid,)).fetchone()
            if file is None or file["status"] != "active":
                raise ValueError("The referenced file is missing or inactive.")
            for slug in operation["tags"]:
                if not SLUG.fullmatch(slug): raise ValueError("A tag slug is invalid.")
            if kind == "assign_tags":
                existing_user = cat.execute("SELECT COUNT(*) FROM file_tags WHERE file_id=? AND assigned_by='user'", (fid,)).fetchone()[0]
                addable = [slug for slug in operation["tags"]
                           if cat.execute("SELECT 1 FROM file_tags WHERE file_id=? AND slug=?", (fid, slug)).fetchone() is None]
                if existing_user + len(addable) > 32:
                    raise ValueError("A file may carry at most 32 user tags.")
                for slug in operation["tags"]:
                    row = cat.execute("SELECT system FROM tags WHERE slug=?", (slug,)).fetchone()
                    if row is not None and row["system"]: continue
                    if row is None:
                        ts = now_ts(); cat.execute("INSERT INTO tags(slug,label,color,system,revision,created_at,updated_at) VALUES(?,?,NULL,0,1,?,?)", (slug,slug,ts,ts))
                        changes.append({"entity":"tag","id":slug,"revision":1,"deleted":False})
                    cat.execute("INSERT OR IGNORE INTO file_tags(file_id,slug,assigned_by,created_at) VALUES(?,?,'user',?)", (fid,slug,now_ts()))
            else:
                for slug in operation["tags"]:
                    cat.execute("DELETE FROM file_tags WHERE file_id=? AND slug=? AND assigned_by='user'", (fid,slug))
            cat.execute("UPDATE files SET revision=revision+1,updated_at=? WHERE id=?", (now_ts(),fid))
            rev = cat.execute("SELECT revision FROM files WHERE id=?", (fid,)).fetchone()[0]
            changes.append({"entity":"file","id":fid,"revision":rev,"deleted":False})
        elif kind == "create_collection":
            cid = new_id("col"); ts = now_ts()
            cat.execute("INSERT INTO collections(id,name,description,filter,revision,created_at,updated_at) VALUES(?,?,?,'{}',1,?,?)",
                        (cid,operation["name"],operation.get("description",""),ts,ts))
            changes.append({"entity":"collection","id":cid,"revision":1,"deleted":False})
        else:
            cid = operation["collection_id"]
            coll = cat.execute("SELECT id FROM collections WHERE id=?", (cid,)).fetchone()
            if coll is None: raise ValueError("The referenced collection does not exist.")
            for fid in operation["file_ids"]:
                f = cat.execute("SELECT id,status FROM files WHERE id=?", (fid,)).fetchone()
                if f is None or f["status"] != "active": raise ValueError("A referenced file is missing or inactive.")
            for fid in operation["file_ids"]:
                if kind == "add_collection_members":
                    cat.execute("INSERT OR IGNORE INTO collection_files(collection_id,file_id,added_at) VALUES(?,?,?)",(cid,fid,now_ts()))
                else:
                    cat.execute("DELETE FROM collection_files WHERE collection_id=? AND file_id=?",(cid,fid))
            cat.execute("UPDATE collections SET revision=revision+1,updated_at=? WHERE id=?",(now_ts(),cid))
            rev=cat.execute("SELECT revision FROM collections WHERE id=?",(cid,)).fetchone()[0]
            changes.append({"entity":"collection","id":cid,"revision":rev,"deleted":False})
            for fid in operation["file_ids"]:
                cat.execute("UPDATE files SET revision=revision+1,updated_at=? WHERE id=?",(now_ts(),fid))
                fr=cat.execute("SELECT revision FROM files WHERE id=?",(fid,)).fetchone()[0]
                changes.append({"entity":"file","id":fid,"revision":fr,"deleted":False})
        if changes: catalog.enqueue_event(cat, changes)
        cat.execute("INSERT INTO organization_applied_requests(request_id,applied_at) VALUES(?,?)",(request_id,now_ts()))
    return {"replayed": False}


def _record_request(conn, project_id, operation):
    ts, rid = now_ts(), new_id("org")
    row = conn.execute("SELECT revision FROM agent_settings WHERE project_id=?", (project_id,)).fetchone()
    revision = row[0] if row else 1
    conn.execute("INSERT INTO organization_requests(id,project_id,status,operation,revision,created_at,updated_at,error) "
                 "VALUES(?,?,'pending',?,?,?,?,NULL)", (rid, project_id, dumps(operation), revision, ts, ts))
    return conn.execute("SELECT * FROM organization_requests WHERE id=?", (rid,)).fetchone()


def _permission(conn, project_id):
    return _settings(conn, project_id)["organization_permission"]


def _perform_operation(conn, config, project_id, operation):
    mode = _permission(conn, project_id)
    if mode == "off": raise ApiError(403, "ORGANIZATION_DISABLED", "Project organization is disabled.")
    with transaction(conn):
        load_writable(conn, project_id)
        mode = _permission(conn, project_id)
        if mode == "off": raise ApiError(403, "ORGANIZATION_DISABLED", "Project organization is disabled.")
        row = _record_request(conn, project_id, operation)
        record_event(conn, project_id, "organization.request.updated", {"request": _request_obj(row)})
    if mode == "ask": return {"status":"pending","request":_request_obj(row),"result":None}
    return _apply_request(conn, config, row, require_allow=True)


def _apply_request(conn, config, row, *, require_allow=False):
    project_id, rid = row["project_id"], row["id"]
    cat = _open_catalog(conn, config, project_id)
    try:
        # Current mode is rechecked immediately before catalog transaction; off blocks even old approvals.
        load_writable(conn, project_id)
        current_permission = _permission(conn, project_id)
        if current_permission == "off": raise ApiError(403,"ORGANIZATION_DISABLED","Project organization is disabled.")
        if require_allow and current_permission != "allow":
            return {"status":"pending","request":_request_obj(row),"result":None}
        # Serialize the final permission/archive check with the catalog commit. The catalog
        # outbox is relayed only after this primary transaction has committed.
        with transaction(conn):
            load_writable(conn, project_id)
            current_permission = _permission(conn, project_id)
            if current_permission == "off": raise ApiError(403,"ORGANIZATION_DISABLED","Project organization is disabled.")
            if require_allow and current_permission != "allow":
                return {"status":"pending","request":_request_obj(row),"result":None}
            result = _apply(cat, project_id, json.loads(row["operation"]), rid)
        catalog.relay_pending(conn, cat, project_id)
    except (ValueError, sqlite3.IntegrityError) as exc:
        with transaction(conn):
            ts=now_ts(); error=dumps({"code":"ORGANIZATION_CONFLICT","message":str(exc)[:500]})
            conn.execute("UPDATE organization_requests SET status='failed',error=?,updated_at=? WHERE id=? AND status='pending'",(error,ts,rid))
            fresh=conn.execute("SELECT * FROM organization_requests WHERE id=?",(rid,)).fetchone()
            record_event(conn,project_id,"organization.request.updated",{"request":_request_obj(fresh)})
        return {"status":"failed","request":_request_obj(fresh),"result":None}
    except ApiError as exc:
        if exc.code != "PROJECT_ARCHIVED":
            raise
        with transaction(conn):
            ts=now_ts(); error=dumps({"code":"PROJECT_ARCHIVED","message":"The project was archived before this request could be applied."})
            conn.execute("UPDATE organization_requests SET status='failed',error=?,updated_at=? WHERE id=? AND status='pending'",(error,ts,rid))
            fresh=conn.execute("SELECT * FROM organization_requests WHERE id=?",(rid,)).fetchone()
            record_event(conn,project_id,"organization.request.updated",{"request":_request_obj(fresh)})
        return {"status":"failed","request":_request_obj(fresh),"result":None}
    finally:
        cat.close()
    with transaction(conn):
        ts=now_ts(); conn.execute("UPDATE organization_requests SET status='applied',error=NULL,updated_at=? WHERE id=? AND status='pending'",(ts,rid))
        fresh=conn.execute("SELECT * FROM organization_requests WHERE id=?",(rid,)).fetchone()
        record_event(conn,project_id,"organization.request.updated",{"request":_request_obj(fresh)})
    return {"status":"applied","request":_request_obj(fresh),"result":result}


@bp.post("/<project_id>/organization-requests/<request_id>/decision")
def decide_organization_request(project_id, request_id):
    body=json_body(); v=Validator(); v.unknown(body,{"decision"}); decision=v.enum(body,"decision",("approve","reject")); v.check()
    key=idempotency_key()
    def build(conn):
        load_writable(conn,project_id)
        row=conn.execute("SELECT * FROM organization_requests WHERE id=? AND project_id=?",(request_id,project_id)).fetchone()
        if row is None: raise ApiError(404,"RESOURCE_NOT_FOUND","Resource not found.")
        if decision == "approve" and _permission(conn,project_id)=="off": raise ApiError(403,"ORGANIZATION_DISABLED","Project organization is disabled.")
        if row["status"]!="pending": raise ApiError(409,"REQUEST_ALREADY_DECIDED","This organization request is no longer pending.")
        ts=now_ts()
        prior = conn.execute("SELECT decision FROM organization_decisions WHERE request_id=?", (request_id,)).fetchone()
        if prior and (prior["decision"] != "approve" or decision != "approve"):
            raise ApiError(409,"REQUEST_ALREADY_DECIDED","This organization request already has a decision.")
        if decision=="reject":
            conn.execute("INSERT INTO organization_decisions(request_id,decision,response,created_at) VALUES(?,?,?,?)",
                         (request_id,"reject","{}",ts))
            conn.execute("UPDATE organization_requests SET status='rejected',updated_at=? WHERE id=?",(ts,request_id))
            updated=conn.execute("SELECT * FROM organization_requests WHERE id=?",(request_id,)).fetchone()
            record_event(conn,project_id,"organization.request.updated",{"request":_request_obj(updated)})
            payload=_request_obj(updated)
        elif not prior:
            # Persist decision intent. Applying occurs after this transaction; a replay finds its durable decision.
            conn.execute("INSERT INTO organization_decisions(request_id,decision,response,created_at) VALUES(?,?,?,?)",
                         (request_id,"approve","{}",ts))
        if decision == "approve":
            payload=_request_obj(row)
        return 200,payload,{},request_id
    response=idempotency.run_command(g.db,key,body,build)
    if decision=="approve":
        fresh=g.db.execute("SELECT * FROM organization_requests WHERE id=? AND project_id=?",(request_id,project_id)).fetchone()
        if fresh and fresh["status"]=="pending":
            result=_apply_request(g.db, current_app.config["STELLARIS"], fresh)
            request_value=result["request"]
            # Cache the contract response row, not the internal tool wrapper.
            keyscope=f"POST {request.path}"
            with transaction(g.db):
                g.db.execute("UPDATE idempotency_keys SET response_body=? WHERE scope=? AND key=?",(dumps(request_value),keyscope,key))
            return json_response(request_value)
        if fresh and fresh["status"] in ("applied", "failed"):
            request_value=_request_obj(fresh)
            keyscope=f"POST {request.path}"
            with transaction(g.db):
                g.db.execute("UPDATE idempotency_keys SET response_body=? WHERE scope=? AND key=?",(dumps(request_value),keyscope,key))
            return json_response(request_value)
    return response


def handle_tool(ctx, name, payload):
    """Backend implementation for project-scoped agent catalog tools."""
    conn, config, project_id = ctx.conn, ctx.config, ctx.project_id
    if name=="list_materials":
        if payload is None: payload = {}
        if not isinstance(payload,dict) or set(payload)-{"cursor","limit"}: raise ValueError("list_materials accepts only cursor and limit")
        limit=payload.get("limit",100)
        if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=100: raise ValueError("list_materials limit must be from 1 to 100")
        after=None
        if payload.get("cursor"):
            if not isinstance(payload["cursor"],str): raise ValueError("list_materials cursor must be a string")
            state=decode_cursor(payload["cursor"])
            if state.get("v")!=1 or state.get("p")!=project_id or not isinstance(state.get("c"),str) or not isinstance(state.get("i"),str):
                raise ValueError("list_materials cursor is invalid")
            after=(state["c"],state["i"])
        cat=_open_catalog(conn,config,project_id)
        try:
            sql="SELECT * FROM files WHERE status='active'"; args=[]
            if after: sql+=" AND (created_at>? OR (created_at=? AND id>?))"; args.extend((after[0],after[0],after[1]))
            rows=cat.execute(sql+" ORDER BY created_at,id LIMIT ?",(*args,limit+1)).fetchall()
            items=[]
            for row in rows[:limit]:
                tags=[{"slug":r[0],"assigned_by":r[1]} for r in cat.execute("SELECT slug,assigned_by FROM file_tags WHERE file_id=? ORDER BY slug",(row["id"],))]
                cols=[r[0] for r in cat.execute("SELECT collection_id FROM collection_files WHERE file_id=? ORDER BY collection_id",(row["id"],))]
                items.append({"id":row["id"],"name":row["name"],"file_kind":row["file_kind"],"status":row["status"],"tags":tags,"collection_ids":cols,"revision":row["revision"],"mime_type":row["mime_type"],"size_bytes":row["size_bytes"]})
            next_cursor=None
            if len(rows)>limit:
                last=rows[limit-1]
                next_cursor=encode_cursor({"v":1,"p":project_id,"c":last["created_at"],"i":last["id"]})
            return {"items":items,"next_cursor":next_cursor}
        finally: cat.close()
    if name!="organize_materials": raise ValueError("Unsupported agent management tool")
    if not isinstance(payload,dict): raise ValueError("organize_materials payload must be an object")
    op=payload.get("operation")
    if op in ("assign_tags","remove_tags"):
        fid,tags=payload.get("file_id"),payload.get("tags")
        if not isinstance(fid,str) or not isinstance(tags,list) or not 1<=len(tags)<=32 or any(not isinstance(s,str) or not SLUG.fullmatch(s) for s in tags): raise ValueError("Expected file_id and 1-32 valid tag slugs")
        operation={"operation":op,"file_id":fid,"tags":list(dict.fromkeys(tags))}
    elif op=="create_collection":
        name_value,description=payload.get("name"),payload.get("description","")
        if not isinstance(name_value,str) or not 1<=len(name_value.strip())<=120 or not isinstance(description,str) or len(description)>2000: raise ValueError("Expected collection name (1-120 characters) and optional description")
        operation={"operation":op,"name":name_value.strip(),"description":description}
    elif op in ("add_collection_members","remove_collection_members"):
        cid,ids=payload.get("collection_id"),payload.get("file_ids")
        if not isinstance(cid,str) or not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(x,str) for x in ids): raise ValueError("Expected collection_id and 1-100 file_ids")
        operation={"operation":op,"collection_id":cid,"file_ids":list(dict.fromkeys(ids))}
    else: raise ValueError("Unsupported organization operation")
    return _perform_operation(conn,config,project_id,operation)
