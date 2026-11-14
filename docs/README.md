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

## Product and implementation

- [Product vision](product-vision.md).
- [Frontend–backend contract](frontend-backend-contract.md). The authoritative interface includes the current development mode without authentication.
- [File workspace contract](file-workspace-contract.md) (proposed, additive). Covers tagged files, notes, collections, and relations. Its [implementation plan](backend/file-workspace-plan.md) has not been started yet.
- [Frontend implementation specification](frontend-implementation-spec.md). The original three-agent implementation breakdown is retained as a reference.
- Historical frontend handoffs: [Agent A](handoffs/agent-a.md), [Agent B](handoffs/agent-b.md), [Agent C](handoffs/agent-c.md). Current startup guidance is in the Compose guide.

## Agent practices and tooling

- [Claude Code delegation](agents/claude-code.md).
- [Domain practices](agents/domain.md), [issue tracker](agents/issue-tracker.md), and [triage labels](agents/triage-labels.md).
- [Graphify installation and repository map](tooling/graphify.md).

## Archived material

- [Original frontend contract draft](archive/frontend-backend-contract-original.md), superseded by the authoritative contract above.
- [Next.js starter README](archive/nextjs-starter.md), retained scaffolder material rather than Stellaris startup guidance.
