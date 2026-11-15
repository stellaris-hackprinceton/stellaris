"""Dynamic per-project Docker containers, owned by the trusted primary backend.

Each project gets:
  * a named volume  stellaris-<project_id>-workspace  mounted at /workspace
      /workspace/data     project files and (later) artifacts
      /workspace/scratch  LangChain Deep Agents scratch space
  * a container     stellaris-<project_id>  running the project runtime image

Project containers never receive the Docker socket, bind mounts, or published ports.
They share one bridge network created with inter-container communication disabled,
so they keep outbound access (needed later for the model provider) but cannot reach
each other. The backend talks to them through the Docker API (inspect/exec/archive),
which also gives the later worker slice a path to copy files in and out.

All operations are idempotent: names are derived from the project ID, so retries
reuse an existing volume/container instead of creating duplicates.
"""

import logging
import os
import re
import tarfile
import tempfile
import threading
import time

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound

log = logging.getLogger(__name__)

LABEL_MANAGED = "stellaris.managed"
LABEL_PROJECT = "stellaris.project_id"
LABEL_ROLE = "stellaris.role"
LABEL_RUN = "stellaris.run_id"
WORKSPACE_MOUNT = "/workspace"
RUNTIME_USER = "10001:10001"
LAYOUT_SCRIPT = "/opt/stellaris/secure_layout.py"
LAYOUT_TIMEOUT_S = 60

# Fixed internal storage layout. Artifact files are named only by server-generated IDs;
# client filenames are labels and never become paths.
DATA_DIR = f"{WORKSPACE_MOUNT}/data"
ARTIFACT_SUBDIR = "artifacts"
ARTIFACT_DIR = f"{DATA_DIR}/{ARTIFACT_SUBDIR}"
ARTIFACT_ID = re.compile(r"^art_[0-9a-f]{32}$")
STREAM_CHUNK = 256 * 1024


class RuntimeUnavailable(Exception):
    """Docker could not provide a healthy project runtime. Message is safe to log, not to return."""


class ArtifactMissing(Exception):
    """A recorded artifact's bytes are absent or not a regular file in the project volume."""


class _IterReader:
    """Minimal file-like reader over an iterator of byte chunks (for tarfile stream mode)."""

    def __init__(self, chunks):
        self._chunks = iter(chunks)
        self._buffer = b""
        self._pos = 0

    def read(self, size=-1):
        parts = []
        while size != 0:
            available = len(self._buffer) - self._pos
            if available <= 0:
                try:
                    self._buffer, self._pos = next(self._chunks), 0
                except StopIteration:
                    break
                continue
            take = available if size < 0 else min(size, available)
            parts.append(self._buffer[self._pos:self._pos + take])
            self._pos += take
            if size > 0:
                size -= take
        return b"".join(parts)


def container_name(project_id: str) -> str:
    return f"stellaris-{project_id}"


def volume_name(project_id: str) -> str:
    return f"stellaris-{project_id}-workspace"


def _labels(project_id: str, role: str) -> dict:
    return {LABEL_MANAGED: "true", LABEL_PROJECT: project_id, LABEL_ROLE: role}


class ProjectRuntime:
    def __init__(self, config):
        self.config = config
        self._client = None
        self._stream_client = None
        self._lock = threading.Lock()
        self._lifecycle_locks = {}

    def client(self):
        with self._lock:
            if self._client is None:
                self._client = docker.from_env(timeout=30)
            return self._client

    def stream_client(self):
        """Client without a socket read timeout, for long-running exec output streams.

        Callers bound wall time themselves (worker watchdog)."""
        with self._lock:
            if self._stream_client is None:
                self._stream_client = docker.from_env(timeout=None)
            return self._stream_client

    def ping(self) -> bool:
        try:
            return bool(self.client().ping())
        except DockerException:
            with self._lock:
                self._client = None
            return False

    def ensure(self, project_id: str, *, create_volume: bool, wait_healthy: bool, refresh_image: bool = True) -> None:
        """refresh_image=False keeps an existing container on its current image (startup reconciliation);
        the next real use (agent run, project creation) then performs the image update for that project."""
        with self._lock:
            lock = self._lifecycle_locks.setdefault(project_id, threading.Lock())
        with lock:
            self._ensure(project_id, create_volume=create_volume, wait_healthy=wait_healthy, refresh_image=refresh_image)

    def _ensure(self, project_id: str, *, create_volume: bool, wait_healthy: bool, refresh_image: bool = True) -> None:
        """Make sure the project's volume exists and its container is running.

        create_volume=False is used during reconciliation: a missing volume for an existing
        project means data loss, and silently substituting an empty volume would hide it.
        """
        try:
            client = self.client()
            self._ensure_network(client)
            vol = self._ensure_volume(client, project_id, create_volume)
            self._secure_layout(client, project_id, vol)
            ctr = self._ensure_container(client, project_id, vol, refresh_image)
            if wait_healthy:
                self._wait_healthy(ctr)
        except RuntimeUnavailable:
            raise
        except DockerException as exc:
            with self._lock:
                self._client = None
            raise RuntimeUnavailable(f"Docker error for {project_id}: {exc}") from exc

    # -- artifact storage in the project volume -----------------------------
    #
    # Bytes move only through the Docker archive API (PUT/GET /containers/{id}/archive)
    # with fixed paths: no shell, no interpolated commands. The archive API works
    # whether or not the project container is running. Files are written root-owned and
    # mode 0444 inside a root-owned 0755 directory, so the non-root project runtime can
    # read but not modify or delete them.

    def _project_container(self, project_id: str):
        try:
            ctr = self.client().containers.get(container_name(project_id))
        except NotFound as exc:
            raise RuntimeUnavailable(f"Project container for {project_id} does not exist.") from exc
        except DockerException as exc:
            with self._lock:
                self._client = None
            raise RuntimeUnavailable(f"Docker error for {project_id}: {exc}") from exc
        if ctr.labels.get(LABEL_PROJECT) != project_id:
            raise RuntimeUnavailable(f"Container for {project_id} is not labelled for that project.")
        return ctr

    def store_artifact(self, project_id: str, artifact_id: str, local_path: str, tmp_dir: str) -> None:
        """Copy a local file into /workspace/data/artifacts/<artifact_id> (idempotent overwrite)."""
        if not ARTIFACT_ID.match(artifact_id):
            raise ValueError("invalid artifact id")
        ctr = self._project_container(project_id)
        size = os.path.getsize(local_path)
        with tempfile.TemporaryFile(dir=tmp_dir) as tar_fh:
            with tarfile.open(fileobj=tar_fh, mode="w", format=tarfile.PAX_FORMAT) as tar:
                now = int(time.time())
                directory = tarfile.TarInfo(ARTIFACT_SUBDIR)
                directory.type, directory.mode, directory.mtime = tarfile.DIRTYPE, 0o755, now
                tar.addfile(directory)
                member = tarfile.TarInfo(f"{ARTIFACT_SUBDIR}/{artifact_id}")
                member.size, member.mode, member.mtime = size, 0o444, now
                with open(local_path, "rb") as src:
                    tar.addfile(member, src)
            tar_fh.seek(0)
            try:
                ok = ctr.put_archive(DATA_DIR, tar_fh)
            except DockerException as exc:
                raise RuntimeUnavailable(f"Could not store artifact for {project_id}: {exc}") from exc
        if not ok:
            raise RuntimeUnavailable(f"Docker rejected the artifact archive for {project_id}.")

    def open_artifact(self, project_id: str, artifact_id: str):
        """Stream an artifact's bytes. Returns (size, reader, close) with bounded memory."""
        if not ARTIFACT_ID.match(artifact_id):
            raise ValueError("invalid artifact id")
        ctr = self._project_container(project_id)
        try:
            bits, _stat = ctr.get_archive(f"{ARTIFACT_DIR}/{artifact_id}", chunk_size=STREAM_CHUNK)
        except NotFound as exc:
            raise ArtifactMissing(f"{artifact_id} missing for {project_id}") from exc
        except DockerException as exc:
            raise RuntimeUnavailable(f"Could not read artifact for {project_id}: {exc}") from exc
        tar = tarfile.open(fileobj=_IterReader(bits), mode="r|")

        def close():
            tar.close()
            if hasattr(bits, "close"):
                bits.close()

        try:
            member = tar.next()
        except (tarfile.TarError, DockerException) as exc:
            close()
            raise RuntimeUnavailable(f"Unreadable artifact archive for {project_id}: {exc}") from exc
        if member is None or not member.isfile():
            close()
            raise ArtifactMissing(f"{artifact_id} is not a regular file for {project_id}")
        return member.size, tar.extractfile(member), close

    def discard_artifact(self, project_id: str, artifact_id: str) -> None:
        """Delete the bytes of a staged artifact that was never committed (best effort).

        Fixed argv (no shell); the ID is validated. Runs as uid 0, which owns the artifact
        directory, inside the running project container. Committed artifacts are never
        discarded by any caller.
        """
        if not ARTIFACT_ID.match(artifact_id):
            raise ValueError("invalid artifact id")
        ctr = self._project_container(project_id)
        try:
            result = ctr.exec_run(["rm", "-f", "--", f"{ARTIFACT_DIR}/{artifact_id}"], user="0:0")
        except DockerException as exc:
            raise RuntimeUnavailable(f"Could not discard artifact for {project_id}: {exc}") from exc
        if result.exit_code != 0:
            raise RuntimeUnavailable(f"Discarding {artifact_id} failed with exit code {result.exit_code}.")

    # -- internals ---------------------------------------------------------

    def _secure_layout(self, client, project_id: str, vol: str) -> None:
        """Make /workspace, /workspace/data, and /workspace/data/artifacts root-owned.

        A one-shot helper container (project runtime image, root with only CHOWN/FOWNER/
        DAC_OVERRIDE, no network) runs secure_layout.py against the volume: /workspace and
        /workspace/data become root-owned 1777 (sticky: the runtime user can still create and
        edit its own files, e.g. the workspace marker, but cannot rename or replace the
        root-owned entries), artifacts/ becomes root-owned 0755, existing artifact files
        root-owned 0444, and /workspace/scratch stays owned by the runtime user. Works for new
        and pre-existing volumes; idempotent.
        """
        cfg = self.config
        try:
            helper = client.containers.create(
                image=cfg.project_image,
                command=["python", "-I", LAYOUT_SCRIPT],
                labels=_labels(project_id, "layout-helper"),
                volumes={vol: {"bind": WORKSPACE_MOUNT, "mode": "rw"}},
                user="0:0",
                network_mode="none",
                read_only=True,
                cap_drop=["ALL"],
                cap_add=["CHOWN", "FOWNER", "DAC_OVERRIDE"],
                security_opt=["no-new-privileges:true"],
                mem_limit="128m",
                pids_limit=16,
                environment={"STELLARIS_RUNTIME_UID": RUNTIME_USER.split(":")[0]},
            )
        except ImageNotFound as exc:
            raise RuntimeUnavailable(
                f"Project runtime image {cfg.project_image} not found. "
                "Build it with: docker compose --profile build-only build"
            ) from exc
        try:
            helper.start()
            status = helper.wait(timeout=LAYOUT_TIMEOUT_S)
            if status.get("StatusCode") != 0:
                output = helper.logs(stdout=True, stderr=True, tail=20).decode("utf-8", "replace")
                raise RuntimeUnavailable(f"Workspace layout check failed for {project_id}: {output.strip()[:500]}")
        except DockerException as exc:
            if isinstance(exc, RuntimeUnavailable):
                raise
            raise RuntimeUnavailable(f"Workspace layout helper failed for {project_id}: {exc}") from exc
        except Exception as exc:  # requests ReadTimeout from wait()
            if isinstance(exc, RuntimeUnavailable):
                raise
            raise RuntimeUnavailable(f"Workspace layout helper did not finish for {project_id}: {exc}") from exc
        finally:
            try:
                helper.remove(force=True)
            except DockerException:
                log.warning("Could not remove layout helper for %s", project_id)

    def _ensure_network(self, client) -> None:
        name = self.config.project_network
        try:
            client.networks.get(name)
            return
        except NotFound:
            pass
        try:
            client.networks.create(
                name,
                driver="bridge",
                check_duplicate=True,
                options={"com.docker.network.bridge.enable_icc": "false"},
                labels={LABEL_MANAGED: "true", LABEL_ROLE: "project-network"},
            )
            log.info("Created project network %s (inter-container communication disabled)", name)
        except APIError as exc:
            if exc.status_code != 409:
                raise

    def _ensure_volume(self, client, project_id: str, create: bool) -> str:
        name = volume_name(project_id)
        try:
            vol = client.volumes.get(name)
        except NotFound:
            if not create:
                raise RuntimeUnavailable(
                    f"Workspace volume {name} is missing; refusing to replace project data with an empty volume."
                )
            vol = client.volumes.create(name=name, labels=_labels(project_id, "project-workspace"))
        owner = (vol.attrs.get("Labels") or {}).get(LABEL_PROJECT)
        if owner != project_id:
            raise RuntimeUnavailable(f"Volume {name} is not labelled for project {project_id}.")
        return name

    def _ensure_container(self, client, project_id: str, vol: str, refresh_image: bool = True):
        name = container_name(project_id)
        try:
            ctr = client.containers.get(name)
        except NotFound:
            ctr = self._create_container(client, project_id, name, vol)
        if ctr.labels.get(LABEL_PROJECT) != project_id:
            raise RuntimeUnavailable(f"Container {name} is not labelled for project {project_id}.")
        expected_image = client.images.get(self.config.project_image).id if refresh_image else None
        if expected_image and ctr.attrs.get("Image") != expected_image:
            log.info("Updating project runtime image for %s; preserving its workspace volume", project_id)
            if ctr.status == "paused":
                ctr.unpause()
            ctr.stop(timeout=10)
            ctr.remove()
            ctr = self._create_container(client, project_id, name, vol)
        if ctr.status == "paused":
            ctr.unpause()
        elif ctr.status in ("created", "exited"):
            ctr.start()
        ctr.reload()
        return ctr

    def _create_container(self, client, project_id: str, name: str, vol: str):
        cfg = self.config
        try:
            ctr = client.containers.create(
                image=cfg.project_image,
                name=name,
                labels=_labels(project_id, "project-runtime"),
                environment={"STELLARIS_PROJECT_ID": project_id, "STELLARIS_WORKSPACE": WORKSPACE_MOUNT},
                volumes={vol: {"bind": WORKSPACE_MOUNT, "mode": "rw"}},
                network=cfg.project_network,
                restart_policy={"Name": "unless-stopped"},
                user=RUNTIME_USER,
                read_only=True,
                tmpfs={"/tmp": "rw,nosuid,nodev,size=64m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                mem_limit=f"{cfg.project_memory_mb}m",
                nano_cpus=int(cfg.project_cpus * 1_000_000_000),
                pids_limit=cfg.project_pids_limit,
                init=True,
            )
            log.info("Created project container %s", name)
            return ctr
        except ImageNotFound as exc:
            raise RuntimeUnavailable(
                f"Project runtime image {cfg.project_image} not found. "
                "Build it with: docker compose --profile build-only build"
            ) from exc
        except APIError as exc:
            if exc.status_code == 409:  # Created concurrently by a retry; reuse it.
                return client.containers.get(name)
            raise

    def _wait_healthy(self, ctr) -> None:
        timeout = self.config.project_health_timeout_s
        deadline = time.monotonic() + timeout
        while True:
            ctr.reload()
            state = ctr.attrs.get("State") or {}
            health = (state.get("Health") or {}).get("Status")
            if health == "healthy":
                return
            if state.get("Status") in ("exited", "dead"):
                raise RuntimeUnavailable(
                    f"Project container {ctr.name} exited during startup (exit code {state.get('ExitCode')})."
                )
            if time.monotonic() > deadline:
                raise RuntimeUnavailable(
                    f"Project container {ctr.name} was not healthy within {timeout:.0f}s (health={health})."
                )
            time.sleep(0.5)
