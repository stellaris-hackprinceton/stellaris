"""Bounded in-process run executor (single API process) and the per-run context handlers use.

RunManager owns a FIFO queue and `max_concurrent_runs` daemon threads. Handlers are plain
functions registered per Run input kind:

    manager.register_handler("agent", handle_agent_run)   # next slice (chat / Deep Agents)

A handler receives a RunContext after the run has moved queued -> running. It must end by
calling ctx.finish(...); raising RunFailure (or any exception) fails the run, keeping logs
and already committed outputs. Cancellation: the cancel route commits `cancelling` (or
`cancelled` for queued runs) and calls request_cancel(); handlers poll ctx.cancel_requested().
finish() re-reads the status inside its transaction, so a run whose `cancelling` committed
first can never become `succeeded` (section 7 serialization).
"""

import codecs
import json
import logging
import os
import queue
import re
import threading
import time

from . import artifacts, db, runs
from .db import transaction
from .errors import ApiError
from .events import record_event
from .http import dumps, new_id, now_ts
from .runtime import RuntimeUnavailable

log = logging.getLogger(__name__)

PROGRESS_INTERVAL_S = 1.0
LOG_FLUSH_INTERVAL_S = 0.5
LOG_FLUSH_BYTES = 16 * 1024
_SECRET_NAME = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)", re.I)
_SECRET_PATTERNS = [re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}")]


def _secret_values():
    # Values only (never logged); used to redact accidental echoes in persisted logs.
    return sorted({v for k, v in os.environ.items() if _SECRET_NAME.search(k) and len(v) >= 8}, key=len, reverse=True)


_SECRETS = _secret_values()


def redact(text: str) -> str:
    for value in _SECRETS:
        text = text.replace(value, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class RunFailure(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


class RunLog:
    """Bounded, redacted, chunked run log persisted as run_logs rows + run.log events."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.chunk = max(256, ctx.config.max_log_chunk_bytes)
        self.limit = ctx.config.max_run_log_bytes
        self.pending = []
        self.pending_bytes = 0
        self.retained = []  # (stream, text) for the log artifact
        self.retained_bytes = 0
        self.dropped_bytes = 0
        self.truncated = False
        self.last_flush = time.monotonic()
        self.decoders = {}
        self.lock = threading.Lock()
        row = ctx.conn.execute("SELECT COALESCE(MAX(sequence), 0) FROM run_logs WHERE run_id = ?", (ctx.run_id,)).fetchone()
        self.sequence = row[0]

    def write(self, stream: str, data) -> None:
        if isinstance(data, bytes):
            decoder = self.decoders.setdefault(stream, codecs.getincrementaldecoder("utf-8")("replace"))
            data = decoder.decode(data)
        if not data:
            return
        text = redact(data)
        with self.lock:
            size = len(text.encode("utf-8"))
            if self.retained_bytes + size > self.limit:
                if not self.truncated:
                    self.truncated = True
                    note = (f"Log output truncated: retained log limit of {self.limit} bytes reached; "
                            "further output was discarded.")
                    self._add("system", note)
                    self.ctx.warn("LOG_TRUNCATED", note)
                self.dropped_bytes += size
                return
            self.retained_bytes += size
            self._add(stream, text)
        if self.pending_bytes >= LOG_FLUSH_BYTES or time.monotonic() - self.last_flush >= LOG_FLUSH_INTERVAL_S:
            self.flush()

    def system(self, text: str) -> None:
        self.write("system", text if text.endswith("\n") else text + "\n")

    def _add(self, stream, text):
        self.retained.append((stream, text))
        encoded = text.encode("utf-8")
        start = 0
        while start < len(encoded):  # Split on UTF-8 boundaries into <= chunk bytes.
            end = min(len(encoded), start + self.chunk)
            while end < len(encoded) and (encoded[end] & 0xC0) == 0x80:
                end -= 1
            self.pending.append((stream, encoded[start:end].decode("utf-8")))
            self.pending_bytes += end - start
            start = end

    def flush(self) -> None:
        with self.lock:
            pending, self.pending, self.pending_bytes = self.pending, [], 0
            self.last_flush = time.monotonic()
        if not pending:
            return
        conn = self.ctx.conn
        with transaction(conn):
            for stream, text in pending:
                self.sequence += 1
                entry = {"id": new_id("log"), "run_id": self.ctx.run_id, "sequence": self.sequence, "stream": stream,
                         "text": text, "created_at": now_ts()}
                conn.execute("INSERT INTO run_logs (id, project_id, run_id, sequence, created_at, doc) "
                             "VALUES (?, ?, ?, ?, ?, ?)",
                             (entry["id"], self.ctx.project_id, self.ctx.run_id, self.sequence, entry["created_at"],
                              dumps(entry)))
                record_event(conn, self.ctx.project_id, "run.log", {"entry": entry}, run_id=self.ctx.run_id)

    def text(self) -> str:
        return "".join(f"[{stream}] {line}\n" for stream, chunk in self.retained for line in chunk.splitlines())


class RunContext:
    def __init__(self, manager, run_id: str):
        self.manager = manager
        self.config = manager.config
        self.runtime = manager.runtime
        self.run_id = run_id
        self.conn = db.connect(self.config.db_path)
        row = self.conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        self.project_id = row["project_id"]
        self.run = json.loads(row["doc"])
        self.snapshot = json.loads(row["snapshot"])
        self.input = self.run["input"]
        self.experiment_id = row["experiment_id"]
        self._cancel = manager._cancel_event(run_id)
        if row["status"] == "cancelling":  # Resumed after a restart with cancellation already requested.
            self._cancel.set()
        self.suspended = False  # Set by a handler that is waiting for an approval decision.
        self.cluster = getattr(manager, "cluster", None)
        self._last_progress = 0.0
        self.warnings = []
        self.staged = []
        self.finished = False
        self.log = RunLog(self)

    # -- state -----------------------------------------------------------------
    def cancel_requested(self) -> bool:
        """Thread-safe (the worker watchdog calls it). The cancel route commits `cancelling`
        and then sets this in-process event; the API is a single process."""
        return self._cancel.is_set()

    def progress(self, phase: str, fraction=None, message=None, force=False) -> None:
        if not force and time.monotonic() - self._last_progress < PROGRESS_INTERVAL_S:
            return
        self._last_progress = time.monotonic()
        with transaction(self.conn):
            status = self.conn.execute("SELECT status FROM runs WHERE id = ?", (self.run_id,)).fetchone()["status"]
            if status != "running":
                return  # Never overwrite cancelling/terminal display state.
            runs.save_run(self.conn, self.run_id, phase=phase,
                          progress={"fraction": None if fraction is None else max(0.0, min(1.0, float(fraction))),
                                    "message": message})

    def warn(self, code: str, message: str) -> None:
        warning = {"code": code, "message": message}
        if warning not in self.warnings:
            self.warnings.append(warning)

    # -- artifacts ---------------------------------------------------------------
    def stage(self, **kwargs) -> dict:
        """artifacts.stage_artifact() bound to this run; tracked for discard on failure."""
        kwargs.setdefault("experiment_id", self.experiment_id)
        staged = artifacts.stage_artifact(self.conn, self.runtime, self.config, self.project_id, run_id=self.run_id,
                                          **kwargs)
        self.staged.append(staged)
        return staged

    def stage_text(self, text: str, **kwargs) -> dict:
        kwargs.setdefault("audit", kwargs.get("kind") in ("log", "environment"))
        tmp_dir = artifacts.ensure_tmp_dir(self.config)
        path = os.path.join(tmp_dir, f"run-text-{new_id('t')}.tmp")
        try:
            with open(path, "wb") as fh:
                fh.write(text.encode("utf-8"))
            return self.stage(local_path=path, **kwargs)
        finally:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def commit_now(self, staged_list) -> list:
        """Commit staged artifacts immediately (partial outputs) and refresh the run."""
        with transaction(self.conn):
            committed = [artifacts.commit_artifact(self.conn, s) for s in staged_list]
            runs.save_run(self.conn, self.run_id)
        ids = {s["id"] for s in staged_list}
        self.staged = [s for s in self.staged if s["id"] not in ids]
        return committed

    def discard_staged(self) -> None:
        for staged in self.staged:
            # A final publication callback may have committed these artifacts. Only
            # uncommitted bytes are staging garbage; published evidence must survive.
            committed = self.conn.execute("SELECT 1 FROM artifacts WHERE id = ?", (staged["id"],)).fetchone()
            if committed is None:
                artifacts.discard_staged(self.runtime, staged)
        self.staged = []

    # -- completion --------------------------------------------------------------
    def finish(self, status: str, *, error=None, summary=None, publish=None, retained=(), provenance=None) -> dict:
        """Commit the final state in one transaction.

        publish(conn) commits results (measurements, claims, result artifacts) and is skipped
        when cancellation committed first. `retained` (logs, code) and `provenance` staged
        artifacts are always committed. If publishing raises (e.g. quota or claim
        validation), the run fails with that error and only retained outputs are kept.
        """
        self.log.flush()
        if provenance is None:
            try:
                provenance = self.stage_text(dumps({
                    "schema": "stellaris.provenance.v1", "run_id": self.run_id,
                    "project_id": self.project_id, "generated_at": now_ts(),
                    "accepted_snapshot": self.snapshot, "outputs": [], "warnings": self.warnings,
                    "execution": {"outcome": status, "note": summary},
                    "reproducibility_limits": ["No complete execution manifest was available; accepted inputs are retained."],
                }), filename="provenance.json", mime_type="application/json", kind="environment", origin="generated")
            except Exception:
                self.warn("PROVENANCE_UNAVAILABLE", "Audit storage is unavailable; accepted inputs remain in backend metadata.")
        try:
            run = self._finish_tx(status, error, summary, publish, list(retained), provenance)
        except (ApiError, RunFailure, RuntimeUnavailable, OSError) as exc:
            code = getattr(exc, "code", "STORAGE_UNAVAILABLE")
            message = getattr(exc, "message", "Artifact storage is unavailable.")
            log.warning("Run %s could not publish results (%s): %s", self.run_id, code, message)
            failure = {"code": code if code != "VALIDATION_FAILED" else "INVALID_OUTPUT",
                       "message": f"Results could not be published: {message}", "retryable": False}
            try:
                run = self._finish_tx("failed", failure, summary, None, list(retained), provenance)
            except (ApiError, RunFailure, RuntimeUnavailable, OSError):
                self.warn("PROVENANCE_UNAVAILABLE", "Storage failed while publishing audit artifacts; "
                          "the accepted input snapshot and run logs remain in backend metadata.")
                run = self._finish_tx("failed", failure, summary, None, [], None)
        self.discard_staged()
        self.finished = True
        return run

    def _finish_tx(self, status, error, summary, publish, retained, provenance):
        with transaction(self.conn):
            current = self.conn.execute("SELECT status FROM runs WHERE id = ?", (self.run_id,)).fetchone()["status"]
            if current in runs.TERMINAL:
                return json.loads(self.conn.execute("SELECT doc FROM runs WHERE id = ?", (self.run_id,)).fetchone()["doc"])
            final = status
            if current == "running" and final == "cancelled":
                runs.save_run(self.conn, self.run_id, status="cancelling")  # Section 7 path to cancelled.
                current = "cancelling"
            if current == "cancelling":
                final = "cancelled"
                publish = None
                error = None
                if status == "succeeded":
                    self.warn("CANCELLED_AFTER_COMPLETION", "Cancellation was requested before the results were "
                                                            "committed; results of this run were not published.")
                summary = "Cancelled before result publication."
            if publish is not None:
                publish(self.conn)
            if final != "succeeded" and provenance is not None:
                _, reader, close = self.runtime.open_artifact(self.project_id, provenance["id"])
                try:
                    manifest = json.loads(reader.read(16 * 1024 * 1024 + 1))
                finally:
                    close()
                kept = {s["id"] for s in retained}
                for key in ("outputs", "partial_outputs"):
                    manifest[key] = [item for item in manifest.get(key, []) if item.get("artifact_id") in kept
                                     or self.conn.execute("SELECT 1 FROM artifacts WHERE id = ?", (item.get("artifact_id"),)).fetchone()]
                manifest.setdefault("execution", {}).update({"published_run_status": final, "note": summary})
                manifest["warnings"] = list(self.warnings)
                provenance = self.stage_text(dumps(manifest), filename="provenance.json", mime_type="application/json",
                                             kind="environment", origin="generated", artifact_id=provenance["id"])
            for staged in retained + ([provenance] if provenance else []):
                artifacts.commit_artifact(self.conn, staged)
            runs.add_warnings(self.conn, self.run_id, self.warnings)
            results = runs.results(self.conn, self.project_id, self.run_id)
            if results["measurement_count"]:
                record_event(self.conn, self.project_id, "measurements.available",
                             {"run_id": self.run_id, "total_count": results["measurement_count"]}, run_id=self.run_id)
            record_event(self.conn, self.project_id, "results.updated", {"results": results}, run_id=self.run_id)
            run = runs.save_run(
                self.conn, self.run_id, status=final, finished_at=now_ts(), phase=final,
                progress={"fraction": 1.0 if final == "succeeded" else None, "message": summary},
                result_summary=summary, error=error,
                provenance_artifact_id=provenance["id"] if provenance else None)
        committed = {s["id"] for s in retained} | ({provenance["id"]} if provenance else set())
        self.staged = [s for s in self.staged if s["id"] not in committed]
        return run

    def close(self):
        self.conn.close()


class RunManager:
    def __init__(self, config, runtime):
        self.config = config
        self.runtime = runtime
        self.handlers = {}
        self.cluster = None  # hpc.SlurmCluster, set by the app when configured.
        self._queue = queue.Queue()
        self._remote_queue = queue.Queue()  # Slurm runs hold a slot while polling; keep them separate.
        self._cancel_events = {}
        self._lock = threading.Lock()
        self._threads = []
        self._worker_check = (0.0, False)

    def register_handler(self, kind: str, handler) -> None:
        self.handlers[kind] = handler

    def start(self) -> None:
        for i in range(max(1, self.config.max_concurrent_runs)):
            thread = threading.Thread(target=self._loop, args=(self._queue,), name=f"stellaris-run-{i}", daemon=True)
            thread.start()
            self._threads.append(thread)
        for i in range(max(1, self.config.slurm_max_concurrent_runs)):
            thread = threading.Thread(target=self._loop, args=(self._remote_queue,), name=f"stellaris-remote-{i}",
                                      daemon=True)
            thread.start()
            self._threads.append(thread)
        threading.Thread(target=self._sweep_approvals, name="stellaris-approvals", daemon=True).start()

    def enqueue(self, run_id: str, remote: bool = False) -> None:
        (self._remote_queue if remote else self._queue).put((run_id, False))

    def resume(self, run_id: str) -> None:
        """Continue a run that is already `running`/`cancelling` (approved, or reattaching after
        a restart). Only remote runs are resumable."""
        self._remote_queue.put((run_id, True))

    def _sweep_approvals(self) -> None:
        from . import approvals
        while True:
            time.sleep(30)
            try:
                conn = db.connect(self.config.db_path)
                try:
                    approvals.sweep_expired(conn)
                finally:
                    conn.close()
            except Exception:
                log.exception("Approval expiry sweep failed")

    def execute_now(self, run_id: str) -> None:
        """Execute a queued run synchronously on the calling thread (agent-requested paper
        ingestion). Bypasses the queue so a run holding an executor slot cannot deadlock
        waiting for another slot."""
        try:
            self._execute(run_id)
        finally:
            with self._lock:
                self._cancel_events.pop(run_id, None)

    def request_cancel(self, run_id: str) -> None:
        self._cancel_event(run_id).set()

    def _cancel_event(self, run_id: str) -> threading.Event:
        with self._lock:
            return self._cancel_events.setdefault(run_id, threading.Event())

    def worker_available(self) -> bool:
        """Whether the worker image exists (cached for 30 s)."""
        checked_at, value = self._worker_check
        if time.monotonic() - checked_at < 30:
            return value
        from . import worker
        value = worker.image_info(self.runtime, self.config) is not None
        self._worker_check = (time.monotonic(), value)
        return value

    def _loop(self, source) -> None:
        while True:
            run_id, resume = source.get()
            try:
                self._execute(run_id, resume=resume)
            except Exception:
                log.exception("Run %s crashed the executor loop", run_id)
            finally:
                with self._lock:
                    self._cancel_events.pop(run_id, None)

    def _execute(self, run_id: str, resume: bool = False) -> None:
        conn = db.connect(self.config.db_path)
        try:
            with transaction(conn):
                row = conn.execute("SELECT status, kind FROM runs WHERE id = ?", (run_id,)).fetchone()
                if row is None or row["status"] != ("queued" if not resume else row["status"]):
                    return  # Cancelled while queued, or already handled.
                if resume and row["status"] not in ("running", "cancelling"):
                    return
                kind = row["kind"]
                handler = self.handlers.get(kind)
                if handler is None:
                    runs.save_run(conn, run_id, status="failed", finished_at=now_ts(), phase="failed",
                                  error={"code": "FEATURE_UNAVAILABLE",
                                         "message": f"No executor is registered for {kind} runs.", "retryable": False})
                    return
                if not resume:
                    runs.save_run(conn, run_id, status="running", started_at=now_ts(), phase="starting",
                                  progress={"fraction": 0.0, "message": "Starting."})
        finally:
            conn.close()

        ctx = RunContext(self, run_id)
        try:
            handler(ctx)
            if ctx.suspended:
                return  # Awaiting approval; a decision re-enqueues the run.
            if not ctx.finished:
                raise RunFailure("INTERNAL_ERROR", "The run handler returned without finishing the run.")
        except RunFailure as exc:
            self._fail(ctx, exc.code, exc.message, exc.retryable)
        except Exception as exc:
            log.exception("Run %s failed unexpectedly", run_id)
            self._fail(ctx, "INTERNAL_ERROR", f"Unexpected backend error ({type(exc).__name__}).", True)
        finally:
            ctx.close()

    def _fail(self, ctx, code, message, retryable):
        if ctx.finished:
            return
        try:
            ctx.log.system(f"Run failed: {code}: {message}")
            retained = []
            try:
                retained.append(ctx.stage_text(ctx.log.text(), filename="run-log.txt", mime_type="text/plain",
                                               kind="log", origin="generated"))
            except Exception as exc:  # Logs stay available through the logs route.
                log.warning("Could not stage log artifact for %s: %s", ctx.run_id, exc)
            ctx.finish("failed", error={"code": code, "message": message, "retryable": retryable},
                       summary=f"Failed: {code}", retained=retained)
        except Exception:
            log.exception("Could not record failure for run %s", ctx.run_id)
            ctx.discard_staged()
