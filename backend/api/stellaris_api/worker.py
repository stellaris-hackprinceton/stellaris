"""Temporary isolated worker containers for scientific code (one per analysis run).

Per run (all labelled stellaris.run_id / stellaris.role; removed on every exit path):
  * volume   stellaris-run-<run>-input   declared inputs + manifest, root-owned 0444/0555
  * loader   stellaris-run-<run>-loader  created, never started; only used to copy the input
             archive into the volume through the Docker archive API, then removed
  * worker   stellaris-run-<run>-worker  the worker image, pinned by image ID:
               - input volume mounted read-only at /input
               - /output: tmpfs (size limit, uid 10002, 0700); /tmp: tmpfs (size limit)
               - read-only root filesystem, network_mode none, cap_drop ALL, no-new-privileges,
                 memory (= memory+swap), CPU, PID, open-file, file-size and core limits
               - no Docker socket, no bind mounts, no project volume, no credentials/env secrets
             Its main process (uid 10003) only sleeps. The analysis code runs through
             `docker exec` as uid 10002, so it cannot signal the keep-alive process; output is
             collected from the still-running container after every 10002 process is killed.
Output collection streams `tar -c /output` (run as uid 10002 by the image's trusted tar)
through a bounded reader that never calls extract()/extractall(): only regular files are
written, to fresh server-named files; directories are noted, everything else (symlinks,
hard links, devices, sparse files) is recorded as rejected, and absolute/traversing names,
duplicates, and size/count overruns reject the whole output.
"""

import json
import logging
import os
import tarfile
import tempfile
import threading
import time

from docker.errors import DockerException, ImageNotFound, NotFound
from docker.types import Ulimit

from .runtime import LABEL_MANAGED, LABEL_PROJECT, LABEL_ROLE, LABEL_RUN, _IterReader

log = logging.getLogger(__name__)

ANALYSIS_USER = "10002:10002"
KEEPER_USER = "10003:10003"
ROLE_WORKER, ROLE_LOADER, ROLE_INPUT = "run-worker", "run-loader", "run-input"
KILL_ANALYSIS = ["python", "-I", "-c", "import os, signal; os.kill(-1, signal.SIGKILL)"]
COLLECT = ["tar", "--format=posix", "-C", "/output", "-cf", "-", "."]
VERSIONS_PATH = "/opt/stellaris/versions.json"
MAX_OUTPUT_MEMBERS = 2000
MAX_PATH = 255
MAX_DEPTH = 8
KILL_GRACE_S = 15


class WorkerUnavailable(Exception):
    """Docker or the worker image is unavailable (message safe to log)."""


class OutputRejected(Exception):
    pass


def resource_names(run_id: str):
    return f"stellaris-run-{run_id}-input", f"stellaris-run-{run_id}-loader", f"stellaris-run-{run_id}-worker"


def _labels(project_id: str, run_id: str, role: str) -> dict:
    return {LABEL_MANAGED: "true", LABEL_PROJECT: project_id, LABEL_RUN: run_id, LABEL_ROLE: role}


def image_info(runtime, config):
    """{reference, image_id, repo_digests, created} for the configured worker image, or None."""
    try:
        image = runtime.client().images.get(config.worker_image)
    except (ImageNotFound, NotFound):
        return None
    except DockerException as exc:
        log.warning("Worker image lookup failed: %s", exc)
        return None
    return {"reference": config.worker_image, "image_id": image.id,
            "repo_digests": image.attrs.get("RepoDigests") or [], "created": image.attrs.get("Created")}


# -- bounded tar reading ----------------------------------------------------------------

def normalize_member(name: str) -> str:
    if not isinstance(name, str) or "\x00" in name or "\\" in name or name.startswith("/"):
        raise OutputRejected(f"output entry has an invalid or absolute name: {name!r}")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise OutputRejected(f"output entry escapes the output directory: {name!r}")
    normalized = "/".join(parts)
    if len(normalized) > MAX_PATH or len(parts) > MAX_DEPTH:
        raise OutputRejected("output entry path is too long or too deep")
    return normalized


def read_tar(chunks, dest_dir: str, *, max_bytes: int, max_members: int = MAX_OUTPUT_MEMBERS):
    """Copy regular files from a tar stream into dest_dir. Returns (files, rejected, dirs).

    files: {relative path: local file}; rejected: {relative path: entry type}. Never
    extracts by member name; never follows or creates links.
    """
    files, rejected, dirs = {}, {}, set()
    total = count = 0
    try:
        with tarfile.open(fileobj=_IterReader(chunks), mode="r|") as tar:
            for member in tar:
                count += 1
                if count > max_members:
                    raise OutputRejected(f"output has more than {max_members} entries")
                name = normalize_member(member.name)
                if not name:
                    continue
                if name in files or name in rejected or name in dirs:
                    raise OutputRejected(f"duplicate output entry {name!r}")
                if member.isdir():
                    dirs.add(name)
                    continue
                if not member.isreg() or member.issparse():
                    rejected[name] = ("symlink" if member.issym() else "hard link" if member.islnk()
                                      else "sparse file" if member.issparse() else "special file")
                    continue
                total += member.size
                if total > max_bytes:
                    raise OutputRejected(f"output exceeds the {max_bytes}-byte limit")
                path = os.path.join(dest_dir, f"out-{count:06d}")
                src = tar.extractfile(member)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as out:
                    remaining = member.size
                    while remaining:
                        chunk = src.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise OutputRejected("output archive is truncated")
                        out.write(chunk)
                        remaining -= len(chunk)
                files[name] = path
    except tarfile.TarError as exc:
        raise OutputRejected(f"output archive is unreadable: {exc}")
    return files, rejected, dirs


# -- one run --------------------------------------------------------------------------------

class Outcome:
    def __init__(self):
        self.status = None        # completed | cancelled | timeout | resource_limit | failed | output_rejected
        self.message = None
        self.exit_code = None
        self.files, self.rejected = {}, {}
        self.versions = None
        self.image = None
        self.started_at = self.finished_at = None
        self.wall_time_s = None


def run_worker(runtime, config, *, project_id: str, run_id: str, input_tar: str, argv, work_dir: str,
               on_output, cancel_requested) -> Outcome:
    """Execute argv in a fresh worker container. Raises WorkerUnavailable for Docker problems
    before execution starts; afterwards every outcome is reported in the returned Outcome."""
    outcome = Outcome()
    image = image_info(runtime, config)
    if image is None:
        raise WorkerUnavailable(f"Worker image {config.worker_image} is not available.")
    outcome.image = image
    client = runtime.client()
    vin, loader_name, worker_name = resource_names(run_id)
    try:
        try:
            client.volumes.create(name=vin, labels=_labels(project_id, run_id, ROLE_INPUT))
            loader = client.containers.create(
                image=image["image_id"], name=loader_name, command=["true"], user="0:0",
                labels=_labels(project_id, run_id, ROLE_LOADER), volumes={vin: {"bind": "/input", "mode": "rw"}},
                network_mode="none", read_only=True, cap_drop=["ALL"])
            try:
                with open(input_tar, "rb") as fh:
                    if not loader.put_archive("/input", fh):
                        raise WorkerUnavailable("Docker rejected the worker input archive.")
            finally:
                loader.remove(force=True)
            ctr = client.containers.create(
                image=image["image_id"], name=worker_name,
                command=["sleep", str(int(config.worker_wall_time_s) + 600)],
                labels=_labels(project_id, run_id, ROLE_WORKER), user=KEEPER_USER, working_dir="/tmp",
                environment={"HOME": "/tmp", "MPLCONFIGDIR": "/tmp/matplotlib", "STELLARIS_MANIFEST": "/input/manifest.json",
                             "STELLARIS_OUTPUT_DIR": "/output"},
                volumes={vin: {"bind": "/input", "mode": "ro"}},
                tmpfs={"/output": f"rw,nosuid,nodev,noexec,size={config.worker_output_mb}m,uid=10002,gid=10002,mode=0700",
                       "/tmp": f"rw,nosuid,nodev,noexec,size={config.worker_tmp_mb}m,mode=1777"},
                network_mode="none", read_only=True, cap_drop=["ALL"], security_opt=["no-new-privileges:true"],
                mem_limit=f"{config.worker_memory_mb}m", memswap_limit=f"{config.worker_memory_mb}m",
                nano_cpus=int(config.worker_cpus * 1_000_000_000), pids_limit=config.worker_pids_limit,
                ulimits=[Ulimit(name="nofile", soft=1024, hard=1024), Ulimit(name="core", soft=0, hard=0),
                         Ulimit(name="fsize", soft=config.worker_output_mb * 1024 * 1024,
                                hard=config.worker_output_mb * 1024 * 1024)],
                init=True, ipc_mode="private")
            ctr.start()
            outcome.versions = _read_versions(ctr, work_dir)
        except DockerException as exc:
            raise WorkerUnavailable(f"Could not prepare the worker container: {exc}") from exc

        _execute(runtime, config, ctr, argv, outcome, on_output, cancel_requested)
        if outcome.status == "completed":
            _collect(runtime, ctr, work_dir, config.worker_output_mb * 1024 * 1024, outcome, on_output)
        return outcome
    finally:
        remove_run_resources(runtime, run_id)


def _read_versions(ctr, work_dir):
    try:
        bits, _ = ctr.get_archive(VERSIONS_PATH)
        dest = tempfile.mkdtemp(prefix="versions-", dir=work_dir)
        files, _, _ = read_tar(bits, dest, max_bytes=256 * 1024, max_members=4)
        path = next(iter(files.values()), None)
        if path:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    except (DockerException, OutputRejected, ValueError, OSError) as exc:
        log.warning("Could not read worker versions: %s", exc)
    return None


def _exec_kill_analysis(runtime, ctr_id):
    try:
        api = runtime.client().api
        exec_id = api.exec_create(ctr_id, KILL_ANALYSIS, user=ANALYSIS_USER)["Id"]
        api.exec_start(exec_id)
    except DockerException as exc:
        log.warning("Could not stop analysis processes in %s: %s", ctr_id[:12], exc)


def _execute(runtime, config, ctr, argv, outcome, on_output, cancel_requested):
    api = runtime.stream_client().api
    done = threading.Event()
    reason = {}
    deadline = time.monotonic() + config.worker_wall_time_s

    def watchdog():
        while not done.wait(0.5):
            if cancel_requested():
                reason["value"] = "cancelled"
            elif time.monotonic() > deadline:
                reason["value"] = "timeout"
            else:
                continue
            _exec_kill_analysis(runtime, ctr.id)
            if not done.wait(KILL_GRACE_S):
                try:
                    ctr.kill()
                except DockerException:
                    pass
            return

    exec_id = api.exec_create(ctr.id, argv, user=ANALYSIS_USER, workdir="/tmp", stdout=True, stderr=True)["Id"]
    outcome.started_at = time.time()
    started = time.monotonic()
    guard = threading.Thread(target=watchdog, name=f"watchdog-{ctr.id[:12]}", daemon=True)
    guard.start()
    try:
        for out, err in api.exec_start(exec_id, stream=True, demux=True):
            if out:
                on_output("stdout", out)
            if err:
                on_output("stderr", err)
    except DockerException as exc:
        log.warning("Worker output stream ended with an error: %s", exc)
    finally:
        done.set()
        guard.join(timeout=KILL_GRACE_S + 5)
    outcome.finished_at = time.time()
    outcome.wall_time_s = round(time.monotonic() - started, 3)
    try:
        outcome.exit_code = api.exec_inspect(exec_id).get("ExitCode")
        ctr.reload()
        state = ctr.attrs.get("State") or {}
    except DockerException:
        state = {}
    if reason.get("value") == "cancelled":
        outcome.status, outcome.message = "cancelled", "Execution was stopped because the run was cancelled."
    elif reason.get("value") == "timeout":
        outcome.status, outcome.message = "timeout", f"Execution exceeded the {config.worker_wall_time_s} s wall-time limit."
    elif state.get("OOMKilled") or outcome.exit_code in (137, -9) or (state and not state.get("Running", True)):
        outcome.status = "resource_limit"
        outcome.message = ("The analysis process was killed (exit code %s), most likely by the %d MiB memory limit."
                           % (outcome.exit_code, config.worker_memory_mb))
    elif outcome.exit_code != 0:
        outcome.status, outcome.message = "failed", f"The analysis process exited with code {outcome.exit_code}."
    else:
        outcome.status = "completed"


def _collect(runtime, ctr, work_dir, max_bytes, outcome, on_output):
    _exec_kill_analysis(runtime, ctr.id)  # Background processes must not change /output while it is read.
    api = runtime.stream_client().api
    exec_id = api.exec_create(ctr.id, COLLECT, user=ANALYSIS_USER, workdir="/tmp", stdout=True, stderr=True)["Id"]
    stream = api.exec_start(exec_id, stream=True, demux=True)
    errors = []

    def stdout_chunks():
        for out, err in stream:
            if err and sum(map(len, errors)) < 4096:
                errors.append(err)
            if out:
                yield out

    dest = tempfile.mkdtemp(prefix="output-", dir=work_dir)
    try:
        outcome.files, outcome.rejected, _ = read_tar(stdout_chunks(), dest, max_bytes=max_bytes)
        for _ in stdout_chunks():  # Drain trailing padding so the exit code is final.
            pass
    except OutputRejected as exc:
        outcome.status, outcome.message = "output_rejected", str(exc)
        return
    code = api.exec_inspect(exec_id).get("ExitCode")
    if errors:
        on_output("system", b"output collection: " + b"".join(errors)[:4096])
    if code != 0:
        outcome.status, outcome.message = "output_rejected", f"Output collection failed (tar exit code {code})."


def remove_run_resources(runtime, run_id: str) -> None:
    """Remove this run's worker/loader containers and input volume (idempotent)."""
    vin, loader_name, worker_name = resource_names(run_id)
    try:
        client = runtime.client()
    except DockerException as exc:
        log.error("Cannot reach Docker to clean up run %s: %s", run_id, exc)
        return
    for name in (worker_name, loader_name):
        try:
            ctr = client.containers.get(name)
            if ctr.labels.get(LABEL_RUN) == run_id:
                ctr.remove(force=True)
        except NotFound:
            pass
        except DockerException as exc:
            log.error("Could not remove %s: %s", name, exc)
    for attempt in range(5):
        try:
            vol = client.volumes.get(vin)
            if (vol.attrs.get("Labels") or {}).get(LABEL_RUN) == run_id:
                vol.remove(force=True)
            return
        except NotFound:
            return
        except DockerException as exc:  # Volume may still be in use for a moment after removal.
            if attempt == 4:
                log.error("Could not remove volume %s: %s", vin, exc)
            time.sleep(0.5)


def cleanup_orphans(runtime, conn_factory) -> None:
    """Startup: remove labelled worker resources whose run is terminal (e.g. WORKER_LOST).

    Resources for active runs and for run IDs unknown to this database are left alone.
    """
    try:
        client = runtime.client()
        labelled = [(c.labels.get(LABEL_RUN), c.labels.get(LABEL_ROLE)) for c in
                    client.containers.list(all=True, filters={"label": [f"{LABEL_MANAGED}=true", LABEL_RUN]})]
        labelled += [((v.attrs.get("Labels") or {}).get(LABEL_RUN), (v.attrs.get("Labels") or {}).get(LABEL_ROLE))
                     for v in client.volumes.list(filters={"label": [f"{LABEL_MANAGED}=true", LABEL_RUN]})]
    except DockerException as exc:
        log.error("Worker orphan scan failed: %s", exc)
        return
    run_ids = {rid for rid, role in labelled if rid and role in (ROLE_WORKER, ROLE_LOADER, ROLE_INPUT)}
    if not run_ids:
        return
    conn = conn_factory()
    try:
        terminal = {r["id"] for r in conn.execute(
            f"SELECT id FROM runs WHERE status IN ('succeeded', 'failed', 'cancelled') AND id IN "
            f"({','.join('?' * len(run_ids))})", sorted(run_ids))}
    finally:
        conn.close()
    for rid in sorted(terminal):
        remove_run_resources(runtime, rid)
        log.warning("Removed leftover worker resources of terminal run %s", rid)
    unknown = run_ids - terminal
    if unknown:
        log.info("Left worker resources of %d non-terminal or unknown runs untouched", len(unknown))
