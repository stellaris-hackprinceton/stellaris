> Ported reference ADR. Verification statements below describe the source branch; current integration checks are recorded separately.

# ADR-0001: Slurm + Apptainer remote execution, demonstrated on a local simulated cluster

Status: Accepted; implemented and verified on the local simulated cluster (scripts/hpc_test.py, 31 checks, 2026-11-14)
Date: 2026-11-14

## Context

The product document lists "HPC cluster connectivity / Slurm job submission" as an optional
execution backend. The MVP backend runs scientific code only in temporary, network-less Docker
worker containers (`backend/api/stellaris_api/worker.py`). The contract (§7, §13) deferred SSH,
cloud, and Slurm execution until job IDs, credential handling, approval, and cancellation
semantics were defined. No real cluster account is available for the hackathon, so the user chose
a **local simulated cluster**.

## Decision

1. **New execution backend `slurm`**, selectable per analysis run alongside the default
   `isolated_python`. It reuses the existing worker contract unchanged: `/input/manifest.json`,
   read-only inputs, a writable `/output`, and `/output/result.json` validated by the existing
   output validator. Pipelines (`bouncing_ball_v1`, `python_analysis_v1`) do not change.
2. **Container runtime: Apptainer (Singularity).** The backend converts the pinned worker Docker
   image to a SIF (`docker save` → `apptainer build worker-<image-id>.sif docker-archive://…`).
   The SIF is cached on the cluster, keyed by the Docker image ID. Its SHA-256 goes in provenance.
   Jobs run `apptainer exec --containall --cleanenv --no-home --net --network none` with input bound
   read-only and output bound writable.
3. **Submission flow** (one handler in the run executor):
   accepted snapshot → `awaiting_approval` (approval action `remote_compute`) → stage the input tar
   over SFTP to `<cluster scratch>/stellaris/<run_id>/` → `sbatch` with `--job-name=stellaris-<run_id>`,
   `--time`, `--mem`, `--cpus-per-task`, optional `--gres=gpu:N`, separate `--output`/`--error` files →
   poll `squeue`/`sacct` → stream stdout/stderr by SFTP offset tailing → when the job state is
   `COMPLETED`, tar `/output` back through the existing tar reader and validator → remove the remote
   run directory.
4. **Transport: SSH from the primary backend only** (paramiko, key auth). The private key is a
   file mounted only into the API container. It never reaches project containers, the agent, workers,
   logs, or provenance. Project agents cannot submit jobs directly. They can only propose analysis
   runs, which still need user approval.
5. **Approval is always required** for `slurm` runs, including on the simulated cluster. The
   approval snapshot binds the cluster, partition, resources, SIF digest, input hashes, and code hash.
   `estimated_cost` is `null` on the local cluster.
6. **Restart behaviour differs from Docker.** Slurm jobs outlive backend restarts, so the run keeps
   `remote_job.job_id` and the backend **reattaches** on restart instead of marking `WORKER_LOST`. A run
   that crashed between `sbatch` and persisting the job ID is recovered by `squeue --name=stellaris-<run_id>`.
   The job name is unique per run, which makes submission idempotent.
7. **State mapping** (`sacct` → run outcome): `COMPLETED` → collect and validate; `FAILED` → `WORKER_FAILED`;
   `TIMEOUT` → `EXECUTION_TIMEOUT`; `OUT_OF_MEMORY` → `RESOURCE_LIMIT_EXCEEDED`;
   `CANCELLED` by Stellaris → `cancelled`; `CANCELLED` externally → `REMOTE_JOB_CANCELLED`;
   `NODE_FAIL`/`BOOT_FAIL`/`PREEMPTED`/`LOST` → `WORKER_LOST`; queued longer than `max_queue_wait_s` →
   `scancel` + `REMOTE_QUEUE_TIMEOUT`; unreachable cluster → `REMOTE_UNAVAILABLE` (retryable). Cancel
   runs `scancel`. Queue time does not count toward wall time.
8. **Local simulated cluster.** The Compose file gets an opt-in `hpc` profile with a
   `stellaris-slurm` service: a single-node Slurm (munge + slurmctld + slurmd + slurmdbd/sacct storage)
   with Apptainer and sshd. It sits on an `internal: true` Docker network shared only with the API, so
   jobs have no internet egress even before Apptainer's own network isolation. Capabilities report
   `cluster_kind: "local_simulated"`. Provenance and reports state that execution happened on a local
   simulated cluster. **Results are not labelled simulated data**: the computation is real, only the
   cluster is local.
9. **Contract changes.** These are additive within `/api/v1` and recorded in `Contracts.md`:
   `execution` on analysis RunInput, `remote_job` on Run, `slurm` in `execution_backend` /
   `allowed_backends`, `capabilities.remote_compute`, approval action `remote_compute`, and new run
   error codes.

## Consequences

- One worker image serves both backends, and output validation stays in one place.
- The approval resource and the `awaiting_approval` state were previously only on paper. They are
  now implemented, and the frontend needs an approval UI.
- Apptainer inside Docker needs elevated privileges (user namespaces or `--privileged`) on the
  **simulated cluster container only**. That container holds no secrets and has no egress. This is
  acceptable for local development. It must never be used as a pattern for production. If Apptainer
  cannot run in Docker Desktop on macOS, the implementation spike must report it. It must not
  silently fall back to plain processes.
- On a real cluster, `--network none` depends on site Apptainer configuration. Network isolation
  becomes a reported property of the cluster, not a guarantee. Real external clusters (credentials
  per user, host key pinning, cost) remain future work.

## Implementation notes (2026-11-14)

The feasibility check on Docker Desktop (arm64) changed some details of the design above:

- **No slurmdbd/sacct.** Accounting storage is off. Job state comes from `scontrol show job`.
  `MinJobAge=86400` keeps finished jobs queryable for a day, and `jobcomp/filetxt` keeps a
  completion log. A job that has aged out is reported as `LOST`, which maps to `WORKER_LOST`.
- **Scheduling.** Without slurmdbd, the main scheduler marks jobs `InvalidAccount`, but the backfill
  scheduler still starts them. `bf_interval=1` makes jobs start within about one second.
- **cgroups.** slurmd 23.11 cannot disable its cgroup plugin. The entrypoint therefore delegates
  cgroup v2 controllers inside the privileged container and uses `IgnoreSystemd=yes`. Memory limits
  are enforced by polling (`OverMemoryKill`). A job over its memory request ends `FAILED`, which maps
  to `WORKER_FAILED`, not `OUT_OF_MEMORY`. Real clusters with cgroup enforcement report
  `OUT_OF_MEMORY`, which maps to `RESOURCE_LIMIT_EXCEEDED`.
- **`--unsquash`.** Rootless Apptainer mounts SIFs with squashfuse, and Docker Desktop's FUSE cannot
  exec from that mount (`exec ... invalid argument`). Each job therefore unpacks the SIF to a temporary
  sandbox, which adds about 9 s. The setting is `STELLARIS_SLURM_UNSQUASH`, on by default.
- **The SIF is built when approval is requested.** The approval snapshot binds the worker image ID
  and the SIF SHA-256. Execution refuses to run if either changed after approval.
- **Keys.** The API generates an Ed25519 key in `/data/hpc`. It publishes only the public key, through
  the `stellaris-hpc-keys` volume, which the cluster's sshd reads. The host key is pinned on first
  use, in `/data/hpc/known_hosts`, and later changes are rejected.
- **Separate executor pool.** Slurm runs hold a slot while they poll, so they use their own queue
  (`STELLARIS_SLURM_MAX_CONCURRENT_RUNS`, default 4). A run waiting for approval holds no slot.
- **Not enforced in Slurm jobs.** Job `/tmp` and output sizes are bounded only when outputs are
  collected. PID and open-file limits are not set. Both gaps are recorded in provenance.

## Alternatives considered

- **Fake `sbatch`/`sacct` shell stubs:** cheaper, but they don't exercise real scheduler states,
  restart reattachment, or `sacct` accounting. Rejected for fidelity.
- **Docker-in-Slurm / Podman:** less common on real HPC sites than Apptainer. Rejected.
- **Agent-driven SSH:** gives credentials and arbitrary commands to the LLM runtime. Rejected.
