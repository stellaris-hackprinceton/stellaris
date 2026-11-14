#!/bin/bash
# Starts munge, slurmctld, slurmd, and sshd for the local simulated cluster (ADR-0001).
set -euo pipefail

# cgroup v2 inside a privileged container: move our processes out of the root cgroup so
# controllers can be delegated, and pre-create the scope slurmd expects (no systemd here).
if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
    mkdir -p /sys/fs/cgroup/init /sys/fs/cgroup/system.slice
    for pid in $(cat /sys/fs/cgroup/cgroup.procs); do echo "$pid" > /sys/fs/cgroup/init/cgroup.procs 2>/dev/null || true; done
    echo "+cpu +memory +pids" > /sys/fs/cgroup/cgroup.subtree_control
    echo "+cpu +memory +pids" > /sys/fs/cgroup/system.slice/cgroup.subtree_control
fi

# Size the single node from what the container actually sees, keeping 1 GiB for daemons.
cpus=$(nproc)
mem_mb=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 - 1024 ))
[ "$mem_mb" -ge 512 ] || mem_mb=512
sed -i "s/^NodeName=.*/NodeName=stellaris-slurm CPUs=${cpus} RealMemory=${mem_mb} State=UNKNOWN/" /etc/slurm/slurm.conf

[ -s /etc/munge/munge.key ] || dd if=/dev/urandom bs=1 count=1024 of=/etc/munge/munge.key 2>/dev/null
chown munge:munge /etc/munge/munge.key && chmod 0400 /etc/munge/munge.key
mkdir -p /run/munge && chown munge:munge /run/munge
su -s /bin/sh munge -c /usr/sbin/munged

# Host keys persist on the state volume so the backend's pinned key stays valid.
mkdir -p /state/ssh
[ -s /state/ssh/ssh_host_ed25519_key ] || ssh-keygen -q -t ed25519 -N "" -f /state/ssh/ssh_host_ed25519_key
mkdir -p /state/scratch /state/slurmctld && chown stellaris:stellaris /state/scratch && chmod 0700 /state/scratch
chown slurm:slurm /state/slurmctld && touch /state/jobcomp.log && chown slurm:slurm /state/jobcomp.log

/usr/sbin/slurmctld || { tail -20 /var/log/slurm/slurmctld.log; exit 1; }
/usr/sbin/slurmd || { tail -20 /var/log/slurm/slurmd.log; exit 1; }
echo "stellaris-slurm ready: ${cpus} CPUs, ${mem_mb} MiB"
exec /usr/sbin/sshd -D -e
