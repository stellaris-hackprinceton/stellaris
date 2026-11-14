# Stellaris frontend documentation

These shared specifications live in `frontend/public/docs/` so they can be committed with the frontend and read by every implementation agent.

1. [Frontend–backend contract](frontend-backend-contract.md) defines API resources, commands, uploads, live events, errors, and scientific provenance.
2. [Frontend implementation specification](frontend-implementation-spec.md) defines screens, module interfaces, file ownership, implementation order, and ready-to-assign briefs for two Claude agents and one GPT-6.1 Sol agent.

Read the contract before implementing the frontend specification. Both documents describe proposed behavior and do not imply completed implementation. Follow the frontend's `AGENTS.md` and its bundled Next.js documentation guidance before writing application code.

When the frontend is served, these files are available at `/docs/README.md`, `/docs/frontend-backend-contract.md`, and `/docs/frontend-implementation-spec.md`. Agent implementation handoffs belong in `public/docs/handoffs/`.
