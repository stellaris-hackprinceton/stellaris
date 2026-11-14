"""Slurm + Apptainer execution over SSH (Contracts.md 1.1, ADR-0001).

Only the primary backend talks to the cluster. The SSH private key and the pinned host key
live in the API data volume; project containers, agents, and workers never see them.

Per run (inside the analysis handler, after an approved `remote_compute` approval):
  1. ensure_sif(): the pinned worker Docker image is exported once per image ID, converted to a
     SIF with `apptainer build`, and cached on the cluster with its SHA-256 and version inventory.
  2. The input tar and a generated job script are uploaded to <scratch>/runs/<run_id>/.
  3. `sbatch` submits it as `stellaris-<run_id>`. The name makes submission idempotent: a run
     resumed after a backend restart finds its job with squeue instead of submitting twice.
  4. The job state is polled with `scontrol show job`; stdout/stderr are tailed over SFTP.
  5. On COMPLETED, /output is streamed back as a tar through worker.read_tar(), and the normal
     result validation applies. The remote run directory is then removed.
"""

import json
import logging
import math
import os
import posixpath
import re
import shlex
import threading
import time
from datetime import datetime, timezone

from . import runs, worker
from .db import transaction
from .executor import RunFailure
from .http import now_ts

log = logging.getLogger(__name__)

JOB_PREFIX = "stellaris-"
POLL_INTERVAL_S = 2.0
CANCEL_GRACE_S = 60
ACTIVE_STATES = {"PENDING", "CONFIGURING", "RUNNING", "COMPLETING", "SUSPENDED", "REQUEUED", "RESIZING",
                 "SIGNALING", "STAGE_OUT", "REQUEUE_HOLD", "REQUEUE_FED", "RESV_DEL_HOLD", "SPECIAL_EXIT"}
LOST_STATES = {"NODE_FAIL", "BOOT_FAIL", "PREEMPTED", "DEADLINE", "REVOKED", "LOST"}
_RUN_ID = re.compile(r"^run_[0-9a-f]{32}$")
_ARTIFACT_ID = re.compile(r"^art_[0-9a-f]{32}$")
_PARTITION = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class ClusterUnavailable(Exception):
    pass


def parse_duration(value: str):
    """Slurm time ("D-HH:MM:SS", "HH:MM:SS", "MM:SS", "MM") -> seconds; None for unlimited."""
    value = (value or "").strip()
    if not value or value.upper() in ("INFINITE", "UNLIMITED", "NONE", "N/A"):
        return None
    days = 0
    if "-" in value:
        d, value = value.split("-", 1)
        days = int(d)
    parts = [int(p) for p in value.split(":")]
    if len(parts) == 1:
        h, m, s = 0, parts[0], 0
    elif len(parts) == 2:
        h, (m, s) = 0, parts
    else:
        h, m, s = parts[-3:]
    return days * 86400 + h * 3600 + m * 60 + s


def _parse_time(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


class SlurmCluster:
    def __init__(self, config, runtime):
        self.config = config
        self.runtime = runtime
        self._lock = threading.RLock()
        self._sif_lock = threading.Lock()
        self._client = None
        self._caps = (0.0, None)

    @property
    def enabled(self) -> bool:
        return bool(self.config.slurm_host)

    @property
    def run_root(self) -> str:
        return posixpath.join(self.config.slurm_scratch, "runs")

    # -- credentials --------------------------------------------------------------------
    def _key_path(self):
        return os.path.join(self.config.slurm_key_dir, "id_ed25519")

    def ensure_key(self) -> None:
        """Create the backend's SSH key once and publish its public half for the local cluster."""
        if not self.enabled:
            return
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        os.makedirs(self.config.slurm_key_dir, mode=0o700, exist_ok=True)
        path = self._key_path()
        if not os.path.exists(path):
            key = Ed25519PrivateKey.generate()
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                                    serialization.NoEncryption())
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(pem)
            pub = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
            with open(path + ".pub", "wb") as fh:
                fh.write(pub + b" stellaris-backend\n")
        if self.config.slurm_authorized_keys_dir:
            with open(path + ".pub", "rb") as src:
                pub = src.read()
            target = os.path.join(self.config.slurm_authorized_keys_dir, "authorized_keys")
            current = open(target, "rb").read() if os.path.exists(target) else b""
            if current != pub:
                tmp = target + ".tmp"
                with open(tmp, "wb") as fh:
                    fh.write(pub)
                os.chmod(tmp, 0o644)
                os.replace(tmp, target)

    # -- SSH ------------------------------------------------------------------------------
    def _connect(self):
        import paramiko

        client = paramiko.SSHClient()
        known = os.path.join(self.config.slurm_key_dir, "known_hosts")
        pinned = os.path.exists(known) and os.path.getsize(known) > 0
        if pinned:
            client.load_host_keys(known)
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        elif self.config.slurm_cluster_kind == "local_simulated":
            # The local simulated cluster has a disposable, private Docker network. Pin its first
            # key on first use; external clusters must be pre-pinned by the operator.
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            client.close()
            raise ClusterUnavailable("The external Slurm host key is not configured.")
        try:
            client.connect(self.config.slurm_host, port=self.config.slurm_port, username=self.config.slurm_user,
                           pkey=paramiko.Ed25519Key.from_private_key_file(self._key_path()), timeout=5,
                           banner_timeout=5, auth_timeout=5, allow_agent=False, look_for_keys=False)
        except (paramiko.SSHException, OSError) as exc:
            client.close()
            raise ClusterUnavailable(f"Cannot reach the Slurm cluster ({type(exc).__name__}).") from exc
        if not pinned:
            client.save_host_keys(known)
            os.chmod(known, 0o600)
            log.warning("Pinned the Slurm cluster host key for %s (trust on first use).", self.config.slurm_host)
        transport = client.get_transport()
        transport.set_keepalive(15)
        return client

    def _ssh(self):
        with self._lock:
            transport = self._client.get_transport() if self._client else None
            if transport is None or not transport.is_active():
                if self._client:
                    self._client.close()
                self._client = self._connect()
            return self._client

    def _drop(self):
        with self._lock:
            if self._client:
                self._client.close()
            self._client = None

    def run(self, argv, timeout=60, check=True):
        """Run a fixed argv (shell-quoted) on the cluster. Returns (rc, stdout, stderr)."""
        import paramiko

        chan = None
        try:
            chan = self._ssh().get_transport().open_session(timeout=10)
            chan.exec_command(shlex.join(argv))
            out, err = bytearray(), bytearray()
            deadline = time.monotonic() + timeout
            while True:
                if time.monotonic() >= deadline:
                    raise ClusterUnavailable("A Slurm command exceeded its time limit.")
                if chan.recv_ready():
                    out += chan.recv(65536)
                elif chan.recv_stderr_ready():
                    err += chan.recv_stderr(65536)
                elif chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
                    break
                else:
                    time.sleep(min(0.02, max(0, deadline - time.monotonic())))
                if len(out) + len(err) > 32 * 1024 * 1024:
                    raise ClusterUnavailable("Cluster command output exceeded its limit.")
            rc = chan.recv_exit_status()
        except ClusterUnavailable:
            self._drop()
            raise
        except (paramiko.SSHException, OSError, EOFError) as exc:
            self._drop()
            raise ClusterUnavailable(f"Lost contact with the Slurm cluster ({type(exc).__name__}).") from exc
        finally:
            if chan is not None:
                chan.close()
        if check and rc != 0:
            log.error("Slurm command %s failed with exit code %s: %s", argv[0], rc,
                      err.decode(errors="replace")[-500:])
            raise ClusterUnavailable("A Slurm command failed.")
        return rc, out.decode(errors="replace"), err.decode(errors="replace")

    def _sftp(self):
        import paramiko

        try:
            return self._ssh().open_sftp()
        except (paramiko.SSHException, OSError, EOFError) as exc:
            self._drop()
            raise ClusterUnavailable(f"SFTP to the Slurm cluster failed ({type(exc).__name__}).") from exc

    # -- discovery --------------------------------------------------------------------------
    def capabilities(self):
        """Capabilities.remote_compute, or None when disabled/unreachable (cached 30 s)."""
        if not self.enabled:
            return None
        checked, value = self._caps
        if time.monotonic() - checked < 30:
            return value
        try:
            value = {"scheduler": "slurm", "container_runtime": "apptainer",
                     "cluster_kind": self.config.slurm_cluster_kind, "cluster_label": self.config.slurm_cluster_label,
                     "approval_required": True, "max_queue_wait_s": self.config.slurm_max_queue_wait_s,
                     "partitions": self.partitions()}
            if not value["partitions"]:
                value = None
        except ClusterUnavailable as exc:
            log.info("Slurm cluster unavailable: %s", exc)
            value = None
        self._caps = (time.monotonic(), value)
        return value

    def partitions(self):
        _, out, _ = self.run(["sinfo", "-h", "-o", "%P|%l|%c|%m|%G|%a"], timeout=15)
        found = {}
        for line in out.splitlines():
            parts = line.strip().split("|")
            if len(parts) != 6 or parts[5] != "up":
                continue
            name = parts[0].rstrip("*")
            if not _PARTITION.fullmatch(name):
                continue
            gpus = sum(int(m) for m in re.findall(r"gpu(?::[A-Za-z0-9_-]+)?:(\d+)", parts[4]))
            wall = parse_duration(parts[1])
            entry = {"name": name, "max_wall_time_s": wall if wall is not None else 7 * 86400,
                     "max_memory_mb": int(re.sub(r"\D", "", parts[3]) or 0), "max_cpus": int(parts[2] or 0),
                     "max_gpus": gpus}
            prev = found.get(name)
            if prev is None or entry["max_cpus"] > prev["max_cpus"]:
                found[name] = entry
        return list(found.values())

    # -- images ---------------------------------------------------------------------------------
    def ensure_sif(self, image: dict) -> dict:
        """Build (once per worker image ID) and return {path, sha256, versions}."""
        digest = image["image_id"].split(":")[-1][:24]
        base = posixpath.join(self.config.slurm_scratch, "images", f"worker-{digest}")
        sif = base + ".sif"
        with self._sif_lock:
            rc, out, _ = self.run(["cat", base + ".sha256"], check=False)
            if rc != 0 or not re.fullmatch(r"[0-9a-f]{64}", out.split()[0] if out.split() else ""):
                self._build_sif(image, base)
                _, out, _ = self.run(["cat", base + ".sha256"])
            sha = out.split()[0]
            _, versions, _ = self.run(["cat", base + ".versions.json"], check=False)
        try:
            versions = json.loads(versions) if versions.strip() else None
        except ValueError:
            versions = None
        return {"path": sif, "sha256": sha, "versions": versions}

    def _build_sif(self, image, base):
        log.info("Building Apptainer image %s.sif from %s", base, image["image_id"])
        self.run(["mkdir", "-p", posixpath.dirname(base)])
        archive = base + ".docker.tar"
        sftp = self._sftp()
        try:
            with sftp.open(archive, "wb") as remote:
                remote.set_pipelined(True)
                for chunk in self.runtime.client().images.get(image["image_id"]).save(named=False):
                    remote.write(chunk)
        finally:
            sftp.close()
        unsquash = ["--unsquash"] if self.config.slurm_unsquash else []
        try:
            self.run(["apptainer", "-q", "build", "--force", base + ".tmp.sif", f"docker-archive://{archive}"],
                     timeout=1800)
            self.run(["mv", "-f", base + ".tmp.sif", base + ".sif"])
            _, versions, _ = self.run(["apptainer", "-q", "exec", "--containall", "--cleanenv", *unsquash,
                                       base + ".sif", "cat", worker.VERSIONS_PATH], timeout=300, check=False)
            sftp = self._sftp()
            try:
                with sftp.open(base + ".versions.json", "wb") as fh:
                    fh.write(versions.encode())
            finally:
                sftp.close()
            _, out, _ = self.run(["sha256sum", base + ".sif"], timeout=300)
            sftp = self._sftp()
            try:
                with sftp.open(base + ".sha256", "wb") as fh:
                    fh.write(out.split()[0].encode() + b"\n")
            finally:
                sftp.close()
        finally:
            self.run(["rm", "-f", archive], check=False)

    # -- jobs -------------------------------------------------------------------------------------
    def run_dir(self, run_id: str) -> str:
        if not _RUN_ID.fullmatch(run_id):
            raise ValueError(run_id)
        return posixpath.join(self.run_root, run_id)

    def job_script(self, run_id, code_id, resources, sif_path) -> str:
        if not _ARTIFACT_ID.fullmatch(code_id) or not _PARTITION.fullmatch(resources["partition"]):
            raise ValueError("invalid job parameters")
        d = self.run_dir(run_id)
        minutes = max(1, math.ceil(resources["wall_time_s"] / 60))
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={JOB_PREFIX}{run_id}",
            f"#SBATCH --chdir={d}",
            f"#SBATCH --output={d}/stdout.log",
            f"#SBATCH --error={d}/stderr.log",
            f"#SBATCH --partition={resources['partition']}",
            f"#SBATCH --time={minutes}",
            f"#SBATCH --mem={int(resources['memory_mb'])}M",
            f"#SBATCH --cpus-per-task={int(resources['cpus'])}",
            "#SBATCH --no-requeue",
        ]
        if resources.get("gpus"):
            lines.append(f"#SBATCH --gres=gpu:{int(resources['gpus'])}")
        flags = ["--containall", "--cleanenv", "--no-home", "--net", "--network", "none", "--pwd", "/tmp"]
        if self.config.slurm_unsquash:
            flags.append("--unsquash")
        if resources.get("gpus"):
            flags.append("--nv")
        env = ",".join(["MPLCONFIGDIR=/tmp/matplotlib", "STELLARIS_MANIFEST=/input/manifest.json",
                        "STELLARIS_OUTPUT_DIR=/output", f"OMP_NUM_THREADS={int(resources['cpus'])}",
                        f"OPENBLAS_NUM_THREADS={int(resources['cpus'])}"])
        cmd = ["apptainer", "-q", "exec", *flags,
               "--bind", f"{d}/input:/input:ro", "--bind", f"{d}/output:/output", "--bind", f"{d}/tmp:/tmp",
               "--env", env, sif_path, "python", "-I", "-B", f"/input/artifacts/{code_id}"]
        lines += ["set -eu", "umask 077", "tar -xf input.tar -C input", "rm -f input.tar", "exec " + shlex.join(cmd), ""]
        return "\n".join(lines)

    def stage(self, run_id, input_tar, script) -> None:
        d = self.run_dir(run_id)
        self.run(["mkdir", "-p", "-m", "0700", d, f"{d}/input", f"{d}/output", f"{d}/tmp"])
        sftp = self._sftp()
        try:
            sftp.put(input_tar, f"{d}/input.tar")
            with sftp.open(f"{d}/job.sh", "w") as fh:
                fh.write(script)
            sftp.chmod(f"{d}/job.sh", 0o700)
        finally:
            sftp.close()

    def find_job(self, run_id):
        _, out, _ = self.run(["squeue", "-h", "-a", "--states=all", "-n", JOB_PREFIX + run_id, "-o", "%i"], timeout=20)
        ids = [line.strip() for line in out.splitlines() if re.fullmatch(r"[0-9]+", line.strip())]
        return ids[-1] if ids else None

    def submit(self, run_id) -> str:
        rc, out, err = self.run(["sbatch", "--parsable", f"{self.run_dir(run_id)}/job.sh"], check=False, timeout=30)
        job_id = out.strip().split(";")[0]
        if rc != 0 or not re.fullmatch(r"[0-9]+", job_id):
            log.error("Slurm rejected job submission (exit %s): %s", rc,
                      err.decode(errors="replace")[-400:] if isinstance(err, bytes) else str(err)[-400:])
            raise RunFailure("REMOTE_SUBMISSION_FAILED", "Slurm rejected the job submission.")
        return job_id

    def job_info(self, job_id) -> dict:
        if not re.fullmatch(r"[0-9]+", str(job_id)):
            raise ValueError("invalid Slurm job ID")
        rc, out, err = self.run(["scontrol", "show", "job", "-o", str(job_id)], check=False, timeout=20)
        if rc != 0:
            if "Invalid job id" in err:
                return {"JobState": "LOST"}
            log.error("scontrol failed (exit %s): %s", rc, err[-300:])
            raise ClusterUnavailable("Slurm job status could not be read.")
        return dict(re.findall(r"(\w+)=(\S*)", out))

    def cancel(self, job_id) -> None:
        if not re.fullmatch(r"[0-9]+", str(job_id)):
            raise ValueError("invalid Slurm job ID")
        self.run(["scancel", str(job_id)], check=False)

    def read_from(self, run_id, name, offset, limit=256 * 1024):
        sftp = self._sftp()
        try:
            try:
                with sftp.open(f"{self.run_dir(run_id)}/{name}", "rb") as fh:
                    fh.seek(offset)
                    return fh.read(limit)
            except FileNotFoundError:
                return b""
        finally:
            sftp.close()

    def collect(self, run_id, dest, max_bytes):
        """Stream the job's /output back through the bounded, link-rejecting tar reader."""
        import paramiko

        chan = self._ssh().get_transport().open_session(timeout=10)
        chan.settimeout(120)
        chan.exec_command(shlex.join(["tar", "--format=posix", "-C", f"{self.run_dir(run_id)}/output", "-cf", "-", "."]))

        def chunks():
            while True:
                data = chan.recv(65536)
                if not data:
                    return
                yield data

        try:
            files, rejected, _ = worker.read_tar(chunks(), dest, max_bytes=max_bytes)
            for _ in chunks():
                pass
            rc = chan.recv_exit_status()
        except (paramiko.SSHException, OSError) as exc:
            self._drop()
            raise ClusterUnavailable(f"Output collection failed ({type(exc).__name__}).") from exc
        finally:
            chan.close()
        if rc != 0:
            raise worker.OutputRejected(f"Output collection failed (tar exit code {rc}).")
        return files, rejected

    def cleanup(self, run_id) -> None:
        try:
            # Extracted inputs are read-only (0555 dirs); make them removable first.
            self.run(["chmod", "-R", "u+w", self.run_dir(run_id)], check=False)
            self.run(["rm", "-rf", self.run_dir(run_id)], check=False)
        except ClusterUnavailable as exc:
            log.warning("Could not remove remote run directory for %s: %s", run_id, exc)


# -- run execution ------------------------------------------------------------------------------

def _save_remote(ctx, remote_job):
    with transaction(ctx.conn):
        runs.save_run(ctx.conn, ctx.run_id, remote_job=remote_job)


def run_slurm(ctx, *, approved, tar_path, code_doc, work_dir, on_output):
    """Execute the staged worker input as a Slurm job, exactly as `approved` (the approval's
    action snapshot) describes. Returns a worker.Outcome extended with `remote` (job details).
    Raises RunFailure for remote-specific failures."""
    cluster = ctx.manager.cluster
    execution = ctx.snapshot["execution"]
    resources = execution["resources"]
    outcome = worker.Outcome()
    image = worker.image_info(ctx.runtime, ctx.config)
    if image is None:
        raise RunFailure("WORKER_UNAVAILABLE", "The worker image is not available to convert for the cluster.", True)
    if image["image_id"] != approved["worker_image_id"]:
        raise RunFailure("WORKER_UNAVAILABLE", "The worker image changed after this run was approved; resubmit it.")
    try:
        sif = cluster.ensure_sif(image)
        if sif["sha256"] != approved["sif_sha256"]:
            raise RunFailure("WORKER_UNAVAILABLE", "The cluster image differs from the approved one; resubmit the run.")
        outcome.image = {**image, "sif_path": sif["path"], "sif_sha256": sif["sha256"]}
        outcome.versions = sif["versions"]
        row = ctx.conn.execute("SELECT doc FROM runs WHERE id = ?", (ctx.run_id,)).fetchone()
        remote_job = json.loads(row["doc"]).get("remote_job")
        job_id = (remote_job or {}).get("job_id") or cluster.find_job(ctx.run_id)
        if job_id is None:
            ctx.progress("staging", 0.1, "Uploading inputs to the cluster.", force=True)
            cluster.stage(ctx.run_id, tar_path, cluster.job_script(ctx.run_id, code_doc["id"], resources, sif["path"]))
            job_id = cluster.submit(ctx.run_id)
            ctx.log.system(f"Submitted Slurm job {job_id} to {execution['cluster']['label']} "
                           f"(partition {resources['partition']}).")
        else:
            ctx.log.system(f"Reattached to Slurm job {job_id}.")
        if not remote_job or remote_job.get("job_id") != job_id:
            remote_job = {"scheduler": "slurm", "job_id": job_id, "state": "PENDING",
                          "cluster_label": execution["cluster"]["label"], "submitted_at": now_ts(),
                          "started_at": None, "ended_at": None}
            _save_remote(ctx, remote_job)

        offsets = {"stdout.log": 0, "stderr.log": 0}

        def pump():
            for name, stream in (("stdout.log", "stdout"), ("stderr.log", "stderr")):
                data = cluster.read_from(ctx.run_id, name, offsets[name])
                if data:
                    offsets[name] += len(data)
                    on_output(stream, data)

        submitted = time.monotonic()
        cancel_sent = None
        info = {}
        while True:
            info = cluster.job_info(job_id)
            state = (info.get("JobState") or "UNKNOWN").upper()
            if state != remote_job["state"]:
                remote_job = {**remote_job, "state": state}
                if state != "PENDING" and remote_job["started_at"] is None:
                    remote_job["started_at"] = now_ts()
                if state not in ACTIVE_STATES:
                    remote_job["ended_at"] = now_ts()
                _save_remote(ctx, remote_job)
                ctx.progress("executing" if state == "RUNNING" else "queued_on_cluster", None,
                             f"Slurm job {job_id}: {state}.", force=True)
            pump()
            if state not in ACTIVE_STATES:
                break
            if ctx.cancel_requested() and cancel_sent is None:
                ctx.log.system(f"Cancelling Slurm job {job_id}.")
                cluster.cancel(job_id)
                cancel_sent = time.monotonic()
            if cancel_sent is not None and time.monotonic() - cancel_sent > CANCEL_GRACE_S:
                break
            if (state == "PENDING" and cancel_sent is None
                    and time.monotonic() - submitted > ctx.config.slurm_max_queue_wait_s):
                cluster.cancel(job_id)
                cluster.cleanup(ctx.run_id)
                raise RunFailure("REMOTE_QUEUE_TIMEOUT",
                                 f"The job waited longer than {ctx.config.slurm_max_queue_wait_s} s in the queue "
                                 "and was cancelled.")
            time.sleep(POLL_INTERVAL_S)

        state = (info.get("JobState") or "UNKNOWN").upper()
        code = (info.get("ExitCode") or "0:0").split(":")
        outcome.exit_code = int(code[0]) if code[0].isdigit() else None
        outcome.started_at = _parse_time(info.get("StartTime"))
        outcome.finished_at = _parse_time(info.get("EndTime"))
        run_time = parse_duration(info.get("RunTime", ""))
        outcome.wall_time_s = float(run_time) if run_time is not None else None
        outcome.remote = {"job_id": job_id, "state": state, "node": info.get("NodeList"),
                          "reason": info.get("Reason"), "exit_code": info.get("ExitCode")}
        if ctx.cancel_requested():
            outcome.status, outcome.message = "cancelled", "Execution was stopped because the run was cancelled."
        elif state == "COMPLETED" and outcome.exit_code == 0:
            outcome.status = "completed"
            ctx.progress("collecting", 0.8, "Collecting outputs from the cluster.", force=True)
            try:
                outcome.files, outcome.rejected = cluster.collect(
                    ctx.run_id, work_dir, ctx.config.worker_output_mb * 1024 * 1024)
            except worker.OutputRejected as exc:
                outcome.status, outcome.message = "output_rejected", str(exc)
        elif state == "TIMEOUT":
            outcome.status = "timeout"
            outcome.message = f"The Slurm job exceeded its {resources['wall_time_s']} s time limit."
        elif state == "OUT_OF_MEMORY":
            outcome.status = "resource_limit"
            outcome.message = f"The Slurm job exceeded its {resources['memory_mb']} MiB memory request."
        elif state == "CANCELLED":
            cluster.cleanup(ctx.run_id)
            raise RunFailure("REMOTE_JOB_CANCELLED", f"Slurm job {job_id} was cancelled outside Stellaris.")
        elif state in LOST_STATES:
            cluster.cleanup(ctx.run_id)
            raise RunFailure("WORKER_LOST", f"Slurm job {job_id} ended with {state}.", True)
        else:
            outcome.status = "failed"
            outcome.message = f"The Slurm job ended with {state} (exit code {info.get('ExitCode')})."
        cluster.cleanup(ctx.run_id)
        return outcome
    except ClusterUnavailable as exc:
        raise RunFailure("REMOTE_UNAVAILABLE", str(exc), True) from exc
