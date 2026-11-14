"""Provider-free Flask integration check; run in an isolated API image without secrets."""

import json
import os
import tempfile
import time
import uuid

from stellaris_api import db
from stellaris_api.app import create_app
from stellaris_api.config import load_config
from stellaris_api.http import now_ts


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"ok: {message}")


def main():
    root = tempfile.mkdtemp(prefix="stellaris-missing-model-", dir="/tmp")
    os.environ["STELLARIS_DB_PATH"] = os.path.join(root, "db.sqlite3")
    os.environ["STELLARIS_UPLOAD_TMP_DIR"] = os.path.join(root, "uploads")
    os.environ["STELLARIS_RUN_TMP_DIR"] = os.path.join(root, "runs")
    config = load_config()
    app = create_app(config)
    project_id = "prj_" + uuid.uuid4().hex
    timestamp = now_ts()
    conn = db.connect(config.db_path)
    try:
        with db.transaction(conn):
            conn.execute(
                "INSERT INTO projects (id,name,description,research_question,status,revision,created_at,updated_at,runtime_state) "
                "VALUES (?,?,?,?,'active',1,?,?,'ready')",
                (project_id, "Missing provider test", "", None, timestamp, timestamp),
            )
    finally:
        conn.close()

    with app.test_client() as client:
        caps = client.get("/api/v1/capabilities").get_json()
        check(caps["model_provider"] == "bedrock" and not caps["model_configured"]
              and not caps["features"]["research_chat"],
              "test uses the default Bedrock provider with no configured credentials")
        body = {"content_markdown": "Exercise the missing provider failure."}
        route = f"/api/v1/projects/{project_id}/messages"
        missing = client.post(route, json=body)
        check(missing.status_code == 428, "message submission requires an idempotency key")

        workspace = client.get(f"/api/v1/projects/{project_id}/workspace").get_json()
        key = "missing-model-" + uuid.uuid4().hex
        headers = {"Idempotency-Key": key}
        accepted = client.post(route, json=body, headers=headers)
        check(accepted.status_code == 202, "missing model configuration is accepted asynchronously")
        created = accepted.get_json()
        replay = client.post(route, json=body, headers=headers)
        check(replay.status_code == 202 and replay.get_json() == created
              and replay.headers.get("Idempotent-Replayed") == "true", "same idempotency key replays the accepted chat command")
        conflict = client.post(route, json={"content_markdown": "different"}, headers=headers)
        check(conflict.status_code == 409 and conflict.get_json()["error"]["code"] == "IDEMPOTENCY_CONFLICT",
              "same key with a different body is rejected")

        run_id = created["run"]["id"]
        assistant_id = created["assistant_message"]["id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            run = client.get(f"/api/v1/projects/{project_id}/runs/{run_id}").get_json()
            if run["status"] in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(0.05)
        check(run["status"] == "failed" and run["error"]["code"] == "MODEL_CONFIGURATION_MISSING"
              and "AWS_ACCESS_KEY_ID" in run["error"]["message"],
              "default Bedrock provider fails honestly when credentials are absent")
        message = client.get(f"/api/v1/projects/{project_id}/messages/{assistant_id}").get_json()
        check(message["status"] == "interrupted", "assistant placeholder is finalized as interrupted")

        stream = client.get(f"/api/v1/projects/{project_id}/events?after={workspace['event_cursor']}",
                            buffered=False, headers={"Accept": "text/event-stream"})
        buffer, event_order = "", []
        for chunk in stream.response:
            buffer += chunk.decode() if isinstance(chunk, bytes) else chunk
            while "\n\n" in buffer:
                frame, buffer = buffer.split("\n\n", 1)
                data = next((line[5:] for line in frame.splitlines() if line.startswith("data:")), None)
                if not data:
                    continue
                event = json.loads(data)
                payload = event["payload"]
                if event["type"] == "message.updated" and payload["message"]["id"] == assistant_id:
                    event_order.append("message.updated")
                if (event["type"] == "run.updated" and payload["run"]["id"] == run_id
                        and payload["run"]["status"] in ("succeeded", "failed", "cancelled")):
                    event_order.append("run.updated")
                    break
            if event_order and event_order[-1] == "run.updated":
                break
        stream.close()
        check(event_order == ["message.updated", "run.updated"],
              "SSE finalizes the assistant message before the terminal run event")
    print("Missing-provider chat integration passed.")


if __name__ == "__main__":
    main()
