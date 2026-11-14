FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/workspace/scratch

# /workspace is pre-created with the runtime user's ownership so a new, empty named
# volume mounted there inherits that ownership and layout on first use.
RUN groupadd --system --gid 10001 stellaris \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /workspace/scratch stellaris \
    && mkdir -p /workspace/data /workspace/scratch \
    && chown -R 10001:10001 /workspace

WORKDIR /opt/stellaris
COPY project_runtime/server.py /opt/stellaris/server.py

USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=2s --timeout=2s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]

CMD ["python", "/opt/stellaris/server.py"]
