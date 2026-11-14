FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/workspace/scratch

# /workspace is pre-created so a new, empty named volume mounted there inherits this layout
# on first use. Protected ancestors are root-owned: /workspace and /workspace/data are sticky
# (1777) so the runtime user can create and edit its own files there (workspace marker,
# project files) but cannot rename or replace root-owned entries such as data/ or
# data/artifacts/. The API additionally runs secure_layout.py as a one-shot root helper on
# every ensure, which also upgrades volumes created before this layout existed.
RUN groupadd --system --gid 10001 stellaris \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /workspace/scratch stellaris \
    && mkdir -p /workspace/data/artifacts /workspace/scratch \
    && chown 0:0 /workspace /workspace/data /workspace/data/artifacts \
    && chmod 1777 /workspace /workspace/data \
    && chmod 0755 /workspace/data/artifacts \
    && chown 10001:10001 /workspace/scratch \
    && chmod 0700 /workspace/scratch

WORKDIR /opt/stellaris
COPY project_runtime/requirements.txt /opt/stellaris/requirements.txt
RUN pip install --no-cache-dir -r /opt/stellaris/requirements.txt
COPY project_runtime/server.py /opt/stellaris/server.py
COPY project_runtime/agent_runner.py /opt/stellaris/agent_runner.py
COPY project_runtime/report_agent.py /opt/stellaris/report_agent.py
COPY project_runtime/agent_runtime_test.py /opt/stellaris/agent_runtime_test.py
COPY project_runtime/report_runtime_test.py /opt/stellaris/report_runtime_test.py
COPY project_runtime/secure_layout.py /opt/stellaris/secure_layout.py

USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=2s --timeout=2s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]

CMD ["python", "/opt/stellaris/server.py"]
