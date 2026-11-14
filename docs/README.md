# Stellaris documentation

This is the single canonical documentation tree. Root README and agent entrypoints link here. The frontend serves these same files at `/docs/` without a second copy.

## Start and operate

- [Docker Compose startup and operations](docker-compose.md).
- [Connection troubleshooting](connection-setup.md).
- [Backend architecture and behavior](backend/README.md).
- [Backend implementation progress](backend/implementation-plan.md).
- [Backend verification evidence](backend/verification.md).
- [Current Compose startup verification](verification/compose-startup.md).
- [Experiment launch selection verification](verification/experiment-launch.md).
- [Broad layout verification](verification/broad-layout.md).
- [Project home design and verification](verification/project-home.md).
- [Visual desk implementation and verification](verification/virtual-desk.md).
- [Sketch-derived logo candidates and verification](design/logo-treatments/README.md).
- [Logo reconstruction from the original S artwork](design/logo-reconstruction/README.md).

## Product and implementation

- [Experiment studio design](design/experiment-studio.md). Current visual system, navigation hierarchy, terminology, and responsive behavior.
- [Experiment studio verification](verification/experiment-studio.md). Frontend checks, browser behavior, and remaining provider/deployment limits.

- [Product vision](product-vision.md).
- [Visual research desk direction](design/virtual-desk.md). Approved application-wide card and shelf layout; supersedes earlier paired-widget dimensions.
- [Research desk and widget specification](research-workspace-spec.md). Card contents, shelf layout, responsive behavior, data flow, and acceptance scenarios.
- [Materials curated views specification](materials-views-spec.md). View layouts, saved collections/presentations, inspection, navigation, and backend prerequisites. Curated features remain capability-gated.
- [Reports library and generation specification](reports-spec.md). Report browsing, saved excerpts, composer placement, evidence selection, and execution states.
- [Frontend–backend contract](frontend-backend-contract.md). The authoritative interface includes the current development mode without authentication.
- [Full-text paper ingestion](research-contract.md). Integrated backend support for PDF/arXiv extraction and source locators. The new Literature UI remains pending.
- [Interactive terminal contract](terminal-contract.md). Separate isolated sessions and scratch storage. Frontend integration remains separate.
- [HPC execution contract](hpc-contract.md). Integrated optional backend support. HPC remains disabled under the current user decision.
- [Research, HPC, and terminal integration record](backend/hpc-research-terminal-plan.md). Recorded checks and remaining live-verification gaps.
- [File workspace contract](file-workspace-contract.md). The backend foundation for tagged materials, notes, collections, and explicit relations is implemented. See its [implementation record](backend/file-workspace-plan.md).
- [Unified workspace interface](frontend-workspace.md). Materials, Knowledge graph, Research overview, Tracker, and the shared navigation.
- [Frontend implementation specification](frontend-implementation-spec.md). Pending delivery sequence for the new public specs, followed by the historical three-agent breakdown.
- Historical frontend handoffs: [Agent A](handoffs/agent-a.md), [Agent B](handoffs/agent-b.md), [Agent C](handoffs/agent-c.md). Current startup guidance is in the Compose guide.

## Agent practices and tooling

- [Claude Code delegation](agents/claude-code.md).
- [Domain practices](agents/domain.md), [issue tracker](agents/issue-tracker.md), and [triage labels](agents/triage-labels.md).
- [Graphify installation and repository map](tooling/graphify.md).

## Archived material

- [Original frontend contract draft](archive/frontend-backend-contract-original.md), superseded by the authoritative contract above.
- [Next.js starter README](archive/nextjs-starter.md), retained scaffolder material rather than Stellaris startup guidance.
