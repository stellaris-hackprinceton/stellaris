# Agent execution, organization permissions, and chat controls

Status: **Implemented and locally verified.**
Recorded November 14, 2026, from the user's decisions and inspection of the live app.

## Confirmed direction

- Keep LangChain Deep Agents with the configured Bedrock provider.
- Keep temporary worker containers for code execution. The user explicitly retained
  this architecture after considering execution inside the persistent project container.
- The agent should generate the scripts needed for an experiment while designing it,
  and be able to execute code through the LangChain/Deep Agents framework.
- Execution must support more than a hard-coded Python-only workflow. Advertise the
  runtimes actually installed; do not promise that every language or dependency exists.
- Let the agent organize the project's original materials, collected data and results:
  sort/group them, assign tags, and manage organization.
- Add an organization-permission button cycler to the agent side panel.
- Add a Clear chat action to that panel.
- The user subsequently authorized implementation with Luna subagents.

## Starting implementation and gaps (before this change)

- `backend/project_runtime/requirements.txt` pins `deepagents==0.7.38`.
- `agent_runner.py` uses `FilesystemBackend` for project scratch. Its custom tools
  retrieve/read papers and propose experiments/claims; no executable-script publishing
  or worker-execution tool is connected.
- The model can write scratch files, but those files do not automatically become
  immutable code artifacts attached to an executable experiment.
- The live agent instructions explicitly emphasize the bouncing-ball MVP and require
  a supplied Python implementation for custom work. This makes unrelated plans repeat
  bouncing-ball limitations, even when the user is researching hand gestures.
- Analysis currently offers `bouncing_ball_v1` and `python_analysis_v1`; the latter
  requires an existing code artifact. Worker invocation explicitly launches Python.
- Images and charts already exist as output artifacts and can be previewed. This is
  distinct from a dedicated AI image-generation service, which is not connected.
- Materials already supports tags, notes, collections, relations and presentation.
  Those are the foundation for agent organization tools.

## 1. Agent-written executable experiments

Desired flow:

**Describe a goal → agent designs the experiment and writes its implementation →
save inspectable code → execute in a worker → collect images/data/results → inspect
and report actual evidence.**

- [ ] Document additive execution/experiment contracts before changing their behavior.
- [ ] Remove bouncing-ball assumptions from general experiment-design instructions;
  retain the existing tracker as an optional specialized implementation.
- [ ] Connect Deep Agents to the trusted worker controller through a sandbox adapter
  and its execution tool. Verify the adapter protocol against installed version 0.7.38
  before choosing APIs from current documentation.
- [ ] Keep agent credentials and Docker lifecycle control out of generated-code
  workers. Do not use local-shell execution on the Mac or inside the credential-bearing
  agent process as a shortcut.
- [ ] Give filesystem tools and execution a consistent analysis workspace. Preserve
  files across commands within an analysis task; do not create an empty workspace
  for every command. Keep persistent research scratch distinct from worker inputs,
  generated files and published evidence.
- [ ] Publish generated scripts as immutable, project-scoped code artifacts and link
  their exact versions to the experiment and executions. A saved textual plan alone
  must not be presented as a runnable implementation.
- [ ] Publish runtime/dependency capabilities. Select an installed interpreter or
  command environment rather than always launching Python. Report unavailable
  runtimes/dependencies honestly; choose the initial language set before implementation.
- [ ] Return actual exit status, bounded stdout/stderr, failures and cancellation to
  the agent so it can inspect and correct its code. Retain executed code versions,
  commands, inputs and provenance when it iterates.
- [ ] Preserve existing resource/network limits and explicit failure states. Decide
  dependency installation and network policy before adding package-download behavior.
- [ ] Collect validated images, plots, annotated media, tables and measurements through
  the existing artifact/results system. Generating an illustration must not label it
  observed evidence or imply an experiment was performed.
- [ ] Make the Analysis UI use the saved agent-generated implementation and its inputs,
  with inspectable code and real outputs. Manual script upload can remain available;
  users should not need it for every agent-designed experiment.

Implementation seam: `agent_runner.py`, trusted orchestration in `agent_runs.py`,
the existing analysis/worker modules, worker image, shared contracts and Studio.
The existing full-text tool's request/reply path is worth inspecting for returning
trusted tool results; its asynchronous proposal mechanism alone is insufficient for
an agent that needs execution feedback before its next reasoning step.

## 2. Organize project materials with a permission cycler

- [ ] Add tools for inspecting project materials and organizing videos, collected
  datasets, scripts and results using tags, collections, labels and explicit links.
- [ ] Add a compact cycler in the agent panel with a visible current setting and a
  short explanation. Proposed states: **Organization off → Ask before changes →
  Allow organization**. Proposed default: **Ask before changes**. These labels/default
  are recommendations, not additional user-confirmed decisions.
- [ ] Persist the setting per project and enforce it in the backend at mutation time.
  A prompt instruction or frontend-only disabled button is insufficient.
- [ ] In Ask mode, show the proposed changes before applying them. In Allow mode,
  apply permitted organization and record what changed; expose results in Materials.
  Changing the mode must not silently execute previously queued actions.
- [ ] Keep organization scoped to the selected project. Do not interpret organization
  permission as blanket permission to execute code, delete evidence, access provider
  credentials or mutate other projects.
- [ ] Preserve original artifact bytes, stable IDs, citations, experiment inputs and
  provenance. Start with catalog organization and labels. If actual filesystem moves
  or folders are desired, specify their mapping separately so sorting does not break
  existing artifact paths or references.
- [ ] Handle archived projects, stale revisions and conflicting user edits honestly.

Decide before implementation: final cycler states/default; whether folders are logical
collections or actual workspace directories; allowed bulk/destructive operations;
and how a mode change affects an already executing organization action.

## 3. Clear chat

- [ ] Add a clearly labeled Clear chat action with a concise confirmation of its scope.
- [ ] Clear the displayed conversation and reset the agent conversation context/thread;
  merely hiding messages in the browser is insufficient.
- [ ] Keep project files, sources, experiments, measurements, saved code, results and
  reports. Clear chat is not a project reset.
- [ ] Define how cleared chat is persisted: deletion versus archived conversation
  history, including any retained references needed by run provenance.
- [ ] Define behavior during a streaming response or active agent action before
  implementation. Avoid clearing a message while a running task still writes to it.
- [ ] Reset related draft/retry state safely so clearing cannot resend an old command.

## Verification and delivery when implementation is authorized

- Use bounded slices: code publication/execution, matching UI, organization tools and
  permission enforcement, then chat clearing. Update contracts alongside each slice.
- Prefer Docker/API and real end-to-end checks over an extensive new unit-test suite.
- Use real retrieved material and actual user-provided inputs. Do not fabricate
  experiments, observations, image evidence or measurements to demonstrate success.
- Test at least two supported runtimes, actual saved code/output provenance, a failed
  command corrected by the agent, cancellation and project isolation.
- Check permission enforcement directly through the backend, including mode changes,
  archived projects and stale revisions. Verify Clear chat's defined persistence and
  active-run behavior without removing project evidence.
- Browser inspection uses isolated WebKit binaries/profiles/tooling under `/tmp`.
  Never inspect `.env` files or host profiles. Runtime may load configured credentials;
  keep paid model checks minimal and report which actually ran.
- Use the user's current agent preference and commit/push verified slices when the
  user resumes implementation. Implementation and bounded live checks are now authorized.

## Framework references

- [Deep Agents sandboxes](https://docs.langchain.com/oss/python/deepagents/sandboxes):
  sandbox backends add command execution to filesystem operations.
- [Deep Agents backends](https://docs.langchain.com/oss/python/deepagents/backends):
  filesystem, composite routing and sandbox/backend extension concepts.

These are framework references. Stellaris uses explicit LangChain publication/execution tools
with the existing trusted worker controller, rather than a native SandboxBackend shell.

## Implemented delivery

The additive [agent execution contract](agent-execution-contract.md) defines the shipped
interfaces. Deep Agents can publish immutable implementations and execute Python,
JavaScript or shell scripts using actual worker capabilities. Studio selects saved
implementations; the bouncing-ball tracker remains an explicit optional method.
Each execution gets read-only declared inputs and publishes validated outputs; retained
output artifacts can be declared as inputs for later runs. This does not add a persistent
interactive execution shell or arbitrary package installation.

Organization uses logical catalog tags and collections, with backend-enforced Off, Ask
and Allow permissions (default Ask). It does not move immutable evidence on disk. Clear
chat archives the conversation, advances its generation and resets agent scratch context;
active agent runs block it. Compact controls appear below the composer and explain their
behavior on hover. Literature opens in a large dialog instead of the side inspector.

Verification and limitations are recorded in [agent execution verification](agent-execution-verification.md).
