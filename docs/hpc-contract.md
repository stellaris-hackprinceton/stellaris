# HPC execution contract

Status: integrated; offline transport and unavailable-mode checks passed. Live Slurm/Apptainer execution was not exercised in this integration.

This additive `/api/v1` extension selects remote Slurm execution for a scientific analysis run.
It requires a configured, reachable cluster. HPC remains unavailable by default. A configured
local simulated cluster is opt-in through the `hpc` Compose profile; it is not a real cluster.
No frontend implementation or live cluster is implied by this contract.

## Analysis request

The existing analysis request accepts an optional `execution` object:

```json
{
  "backend": "slurm",
  "resources": {
    "partition": "compute",
    "wall_time_s": 600,
    "memory_mb": 1536,
    "cpus": 1,
    "gpus": 0
  }
}
```

Omitting `execution` preserves `isolated_python`. Slurm resource fields may be omitted and are
filled from configured worker defaults and the selected partition limits. Requests exceeding
actual advertised limits fail validation. The accepted run snapshot captures the resolved
cluster identity, requested resources, code version and hashes of every execution input.
`execution_backend` on the Run is `slurm` when selected. `remote_job` is null until submission,
then has this shape:

```ts
type RemoteJob = {
  scheduler: "slurm",
  job_id: string,
  state: string,
  cluster_label: string,
  submitted_at: Timestamp,
  started_at: Timestamp | null,
  ended_at: Timestamp | null
}
```

The run resource exposes the scheduler ID and lifecycle timestamps. The provenance execution
record may also include final node, scheduler reason, and exit code.

## Approval and execution

Every Slurm run requires a persisted, explicit `remote_compute` approval, including on the local
simulated cluster. The approval snapshot binds the cluster, partition and resource request, worker
image/SIF digest, pipeline source digest, code artifact and input artifact hashes. The API returns
`409 FEATURE_UNAVAILABLE` if no configured cluster is reachable; it never falls back to host or
plain-process execution.

- `GET /projects/{project_id}/runs/{run_id}/approvals` returns the run's approvals.
- `POST /projects/{project_id}/approvals/{approval_id}/decision` accepts
  `{ "decision": "approve" | "reject", "action_sha256": "…" }` with the standard
  idempotency header. A mismatched digest returns `409 APPROVAL_CHANGED`; a contradictory or
  stale decision returns `409 APPROVAL_ALREADY_DECIDED`.
- Approval moves a run through `awaiting_approval` back to `running`; rejection or expiry cancels
  it and records an explanatory warning. Cancelling a running Slurm job requests scheduler
  cancellation. A backend restart reattaches to the run-named scheduler job rather than silently
  submitting duplicate work.

The primary API alone owns SSH transport and generated key material in its runtime data volume.
Project agents and worker containers receive neither credentials nor scheduler access. The
remote worker uses Apptainer with declared read-only inputs, writable output, and no requested
network. The returned output is passed through the same manifest and scientific-output validator
as local execution. Provenance records cluster identity, scheduler job, resource request, image
digest and isolation limitations. No output is published before normal validation succeeds.

## Capabilities and errors

`GET /capabilities` reports this descriptor in `remote_compute` when the cluster is reachable;
otherwise the field is `null`:

```ts
type RemoteComputeCapability = {
  scheduler: "slurm",
  container_runtime: "apptainer",
  cluster_kind: string,
  cluster_label: string,
  approval_required: true,
  max_queue_wait_s: number,
  partitions: {
    name: string,
    max_wall_time_s: number,
    max_memory_mb: number,
    max_cpus: number,
    max_gpus: number
  }[]
}
```

The `features.remote_compute` flag and `execution.allowed_backends` also reflect the reachable
configuration and whether isolated workers are available. Keep local simulated cluster
availability visibly labeled.

Run error codes include `REMOTE_UNAVAILABLE` (retryable transport failure), `REMOTE_QUEUE_TIMEOUT`,
`REMOTE_JOB_CANCELLED`, `REMOTE_SUBMISSION_FAILED`, `REMOTE_OUTPUT_INVALID`, `WORKER_FAILED`,
`EXECUTION_TIMEOUT`, `RESOURCE_LIMIT_EXCEEDED`, and `WORKER_LOST`. Public errors must not include
SSH commands, private key locations, credentials, or private host paths. Scheduler logs and
partial outputs are retained only under the existing run inspection and failure semantics.

Queue time is separate from job wall time. The backend reports limitations that Slurm cannot
enforce for the current setup, including bounded output/tmp only at collection and absent PID/open
file limits. A local simulated cluster exercises real Slurm/Apptainer execution but does not
represent real-cluster availability, site policy, or network guarantees. Real cluster execution
has not been verified by this contract.

SSH API reference: [Paramiko client documentation](https://docs.paramiko.org/en/stable/api/client.html). External clusters require an operator-pinned host key; first-use pinning is restricted to the local simulator.
