FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffprobe validates uploaded/generated media before it becomes an artifact. It runs as
# uid 65534 with rlimits (see stellaris_api/media.py). Only this image needs it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY api/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY api/stellaris_api /app/stellaris_api
# Pipeline source executed in the isolated worker. The API never imports it; it snapshots the
# text when a run is accepted and publishes it as the run's immutable code artifact.
COPY worker/bouncing_ball_v1.py /app/pipelines/bouncing_ball_v1.py
COPY worker/paper_extract_v1.py /app/pipelines/paper_extract_v1.py

# Runs as root because it is the trusted Docker controller and needs the Docker socket.
# Project containers and scientific workers never receive that socket.
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=4)"]

# One worker: SQLite-backed startup recovery and the in-process upload transfer lock assume
# no other process is mid-request. Each open SSE stream occupies one thread.
CMD ["gunicorn", "--workers", "1", "--threads", "32", "--timeout", "120", \
     "--bind", "0.0.0.0:8000", "--access-logfile", "-", "stellaris_api.app:create_app()"]
