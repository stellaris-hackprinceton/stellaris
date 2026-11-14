"""Enforce the protected project-volume layout. Run as root by the API's one-shot helper.

    /workspace                    root:root 1777  (sticky: runtime user keeps its own files)
    /workspace/data               root:root 1777  (sticky)
    /workspace/data/artifacts     root:root 0755  (only the trusted backend writes here)
    /workspace/data/artifacts/*   root:root 0444  regular files only
    /workspace/scratch            runtime user (created 0700 if missing; otherwise untouched)

The project runtime may be running concurrently, so every step works on directory file
descriptors opened with O_NOFOLLOW and re-checks that the name still refers to the inode
that was secured. A non-directory occupying a protected name (e.g. a planted symlink) is
renamed aside rather than followed. Nothing is deleted.
"""

import os
import stat
import sys
import time

WORKSPACE = "/workspace"
RUNTIME_UID = int(os.environ.get("STELLARIS_RUNTIME_UID", "10001"))
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def _aside(parent_fd: int, name: str) -> None:
    target = f".displaced-{name}-{time.time_ns()}"
    os.rename(name, target, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    print(f"moved non-directory {name!r} aside to {target!r}", file=sys.stderr)


def secure_dir(parent_fd: int, name: str, mode: int) -> int:
    """Return an fd for parent/name, a real directory now owned by root with `mode`."""
    for _attempt in range(5):
        try:
            st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            try:
                os.mkdir(name, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            continue
        if not stat.S_ISDIR(st.st_mode):
            _aside(parent_fd, name)
            continue
        try:
            fd = os.open(name, DIR_FLAGS, dir_fd=parent_fd)
        except OSError:
            continue  # Replaced between stat and open; retry.
        os.fchown(fd, 0, 0)
        os.fchmod(fd, mode)
        # Root now owns it, so the runtime user can no longer rename it out of a sticky
        # parent. Confirm the name still refers to the directory that was secured.
        now = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        opened = os.fstat(fd)
        if (now.st_dev, now.st_ino) == (opened.st_dev, opened.st_ino):
            return fd
        os.close(fd)
    sys.exit(f"could not secure {name!r}: it kept changing")


def secure_artifact_files(dir_fd: int) -> None:
    for name in os.listdir(dir_fd):
        if name.startswith(".displaced-"):
            continue
        try:
            st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(st.st_mode):
            _aside(dir_fd, name)  # The backend only ever stores regular files here.
            continue
        fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
        try:
            if stat.S_ISREG(os.fstat(fd).st_mode):
                os.fchown(fd, 0, 0)
                os.fchmod(fd, 0o444)
        finally:
            os.close(fd)


def ensure_scratch(workspace_fd: int) -> None:
    try:
        os.stat("scratch", dir_fd=workspace_fd, follow_symlinks=False)
        return  # Agent scratch space belongs to the runtime user; leave it as it is.
    except FileNotFoundError:
        pass
    os.mkdir("scratch", 0o700, dir_fd=workspace_fd)
    fd = os.open("scratch", DIR_FLAGS, dir_fd=workspace_fd)
    try:
        os.fchown(fd, RUNTIME_UID, RUNTIME_UID)
    finally:
        os.close(fd)


def main() -> None:
    workspace_fd = os.open(WORKSPACE, DIR_FLAGS)  # The volume mount point itself.
    os.fchown(workspace_fd, 0, 0)
    os.fchmod(workspace_fd, 0o1777)
    data_fd = secure_dir(workspace_fd, "data", 0o1777)
    artifacts_fd = secure_dir(data_fd, "artifacts", 0o755)
    secure_artifact_files(artifacts_fd)
    ensure_scratch(workspace_fd)
    for fd in (artifacts_fd, data_fd, workspace_fd):
        os.close(fd)
    print("workspace layout secured")


if __name__ == "__main__":
    main()
