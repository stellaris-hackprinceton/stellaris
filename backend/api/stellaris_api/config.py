"""Runtime configuration read from environment variables.

Blank values are treated as unset so an empty placeholder never overrides a default.
"""

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "")
    return value.strip() if value.strip() else default


def _csv(name: str, default: str) -> frozenset:
    return frozenset(item.strip() for item in _env(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class Config:
    db_path: str
    project_image: str
    project_network: str
    project_memory_mb: int
    project_cpus: float
    project_pids_limit: int
    project_health_timeout_s: float
    allowed_hosts: frozenset
    allowed_origins: frozenset
    upload_tmp_dir: str
    upload_expiry_s: int
    max_file_bytes: int
    max_video_duration_ms: int
    max_project_bytes: int
    media_probe_timeout_s: float
    event_retention_s: int
    # Scientific workers (one temporary container per analysis run).
    worker_image: str
    worker_memory_mb: int
    worker_cpus: float
    worker_pids_limit: int
    worker_wall_time_s: int
    worker_output_mb: int
    worker_tmp_mb: int
    run_tmp_dir: str
    pipelines_dir: str
    max_concurrent_runs: int
    max_log_chunk_bytes: int
    max_run_log_bytes: int


def load_config() -> Config:
    return Config(
        db_path=_env("STELLARIS_DB_PATH", "/data/stellaris.sqlite3"),
        project_image=_env("STELLARIS_PROJECT_IMAGE", "stellaris-project-runtime:dev"),
        project_network=_env("STELLARIS_PROJECT_NETWORK", "stellaris-projects"),
        project_memory_mb=int(_env("STELLARIS_PROJECT_MEMORY_MB", "512")),
        project_cpus=float(_env("STELLARIS_PROJECT_CPUS", "1.0")),
        project_pids_limit=int(_env("STELLARIS_PROJECT_PIDS_LIMIT", "256")),
        project_health_timeout_s=float(_env("STELLARIS_PROJECT_HEALTH_TIMEOUT_S", "45")),
        allowed_hosts=_csv("STELLARIS_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"),
        allowed_origins=_csv(
            "STELLARIS_ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
        ),
        # Temporary upload bytes live in the API's own volume until completion moves them
        # into the project volume.
        upload_tmp_dir=_env("STELLARIS_UPLOAD_TMP_DIR", "/data/uploads"),
        upload_expiry_s=int(_env("STELLARIS_UPLOAD_EXPIRY_S", "86400")),
        max_file_bytes=int(_env("STELLARIS_MAX_FILE_BYTES", str(256 * 1024 * 1024))),
        max_video_duration_ms=int(_env("STELLARIS_MAX_VIDEO_DURATION_MS", "300000")),
        max_project_bytes=int(_env("STELLARIS_MAX_PROJECT_BYTES", str(2 * 1024 * 1024 * 1024))),
        media_probe_timeout_s=float(_env("STELLARIS_MEDIA_PROBE_TIMEOUT_S", "60")),
        event_retention_s=int(_env("STELLARIS_EVENT_RETENTION_S", str(7 * 24 * 3600))),
        worker_image=_env("STELLARIS_WORKER_IMAGE", "stellaris-worker:dev"),
        worker_memory_mb=int(_env("STELLARIS_WORKER_MEMORY_MB", "1536")),
        worker_cpus=float(_env("STELLARIS_WORKER_CPUS", "1.0")),
        worker_pids_limit=int(_env("STELLARIS_WORKER_PIDS_LIMIT", "128")),
        worker_wall_time_s=int(_env("STELLARIS_WORKER_WALL_TIME_S", "600")),
        worker_output_mb=int(_env("STELLARIS_WORKER_OUTPUT_MB", "256")),
        worker_tmp_mb=int(_env("STELLARIS_WORKER_TMP_MB", "256")),
        # Run scratch files (input archives, collected outputs) live in the API volume only.
        run_tmp_dir=_env("STELLARIS_RUN_TMP_DIR", "/data/runs"),
        pipelines_dir=_env("STELLARIS_PIPELINES_DIR", "/app/pipelines"),
        max_concurrent_runs=int(_env("STELLARIS_MAX_CONCURRENT_RUNS", "2")),
        max_log_chunk_bytes=int(_env("STELLARIS_MAX_LOG_CHUNK_BYTES", "4096")),
        max_run_log_bytes=int(_env("STELLARIS_MAX_RUN_LOG_BYTES", str(1024 * 1024))),
    )
