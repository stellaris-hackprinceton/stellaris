# LOCAL SIMULATED CLUSTER (ADR-0001). Single-node Slurm (slurmctld + slurmd) with Apptainer
# and sshd, for development and demos only. It runs privileged so Apptainer can create
# namespaces; it holds no secrets and sits on an internal (no-egress) Docker network.
# Never use this image or its privileges as a production pattern.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends software-properties-common gnupg ca-certificates \
    && add-apt-repository -y ppa:apptainer/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        slurmctld slurmd slurm-client munge openssh-server apptainer squashfs-tools tar python3 tini \
    && rm -rf /var/lib/apt/lists/*

# `stellaris` is the cluster account the backend submits as (no password; key auth only).
RUN useradd --create-home --shell /bin/bash --uid 20001 stellaris \
    && mkdir -p /state /var/spool/slurmctld /var/spool/slurmd /var/log/slurm /run/sshd /etc/stellaris-keys \
    && chown slurm:slurm /var/spool/slurmctld /var/spool/slurmd /var/log/slurm

COPY hpc/slurm.conf /etc/slurm/slurm.conf
COPY hpc/cgroup.conf /etc/slurm/cgroup.conf
COPY hpc/sshd_config /etc/ssh/sshd_config.d/stellaris.conf
COPY hpc/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
