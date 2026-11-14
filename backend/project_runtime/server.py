"""Stellaris per-project runtime (placeholder for the Deep Agents runtime of the next slice).

Prepares the project's persistent workspace volume and serves GET /health on :8080.
The workspace marker binds the volume to one project so a mis-mounted volume fails
health instead of silently mixing project data.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WORKSPACE = os.environ.get("STELLARIS_WORKSPACE", "/workspace")
PROJECT_ID = os.environ.get("STELLARIS_PROJECT_ID", "")
MARKER = os.path.join(WORKSPACE, ".stellaris-project.json")
SUBDIRS = ("data", "scratch")
LAYOUT_VERSION = 1


def prepare_workspace() -> None:
    if not PROJECT_ID:
        sys.exit("STELLARIS_PROJECT_ID is required")
    for name in SUBDIRS:
        os.makedirs(os.path.join(WORKSPACE, name), exist_ok=True)
    if os.path.exists(MARKER):
        with open(MARKER, encoding="utf-8") as fh:
            owner = json.load(fh).get("project_id")
        if owner != PROJECT_ID:
            sys.exit("Workspace volume belongs to a different project; refusing to start.")
        return
    tmp = MARKER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"project_id": PROJECT_ID, "layout_version": LAYOUT_VERSION}, fh)
    os.replace(tmp, MARKER)


def health():
    checks = {name: os.access(os.path.join(WORKSPACE, name), os.W_OK) for name in SUBDIRS}
    try:
        with open(MARKER, encoding="utf-8") as fh:
            marker_ok = json.load(fh).get("project_id") == PROJECT_ID
    except (OSError, ValueError):
        marker_ok = False
    ok = marker_ok and all(checks.values())
    return ok, {
        "status": "ok" if ok else "degraded",
        "project_id": PROJECT_ID,
        "workspace": {"marker": marker_ok, **checks},
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib naming
        if self.path != "/health":
            self._send(404, {"error": "not found"})
            return
        ok, body = health()
        self._send(200 if ok else 503, body)

    def _send(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        pass


def main() -> None:
    prepare_workspace()
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    print(f"Stellaris project runtime ready for {PROJECT_ID}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
