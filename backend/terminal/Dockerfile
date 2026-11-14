FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends bash coreutils && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10004 --create-home --home-dir /home/terminal --shell /bin/bash terminal \
    && mkdir -p /workspace && chown 10004:10004 /workspace
USER 10004:10004
WORKDIR /workspace
ENV HOME=/home/terminal TERM=xterm-256color
ENTRYPOINT ["/bin/bash", "--noprofile", "--norc"]
