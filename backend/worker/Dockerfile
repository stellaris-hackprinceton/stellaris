# Scientific worker image: one temporary container per analysis run, created by the API.
# Never started by Compose. Contains no credentials and no backend code besides the
# version inventory; the executed pipeline/script is copied into /input for each run.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

# libglib2.0-0: runtime dependency of OpenCV's headless wheel on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY worker/requirements.txt /opt/stellaris/requirements.txt
RUN pip install -r /opt/stellaris/requirements.txt

# 10002 runs analysis code; 10003 runs only the idle keep-alive process, so analysis code
# (which cannot signal another uid) cannot end the container before output is collected.
RUN groupadd --system --gid 10002 worker \
    && useradd --system --uid 10002 --gid 10002 --no-create-home --home-dir /tmp worker \
    && groupadd --system --gid 10003 keeper \
    && useradd --system --uid 10003 --gid 10003 --no-create-home --home-dir /tmp keeper \
    && mkdir -p /input /output \
    && chmod 0555 /input

COPY worker/versions.py /opt/stellaris/versions.py
RUN python /opt/stellaris/versions.py > /opt/stellaris/versions.json \
    && chmod 0444 /opt/stellaris/versions.json

USER 10003:10003
WORKDIR /tmp
CMD ["sleep", "3600"]
