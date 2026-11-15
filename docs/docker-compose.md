# Docker Compose startup and operations

Docker Compose is the supported way to run the full local Stellaris application. Start Docker Desktop first. Run commands from the repository root.

## First startup

```sh
docker compose -f backend/compose.yaml --profile build-only build
docker compose -f backend/compose.yaml up -d --wait
```

The build creates four images: frontend, API, project runtime, and scientific worker. Only `frontend` and `api` are permanent Compose services. Project containers are created dynamically when projects are created. Scientific workers are temporary and isolated per analysis run.

Open `http://localhost:3000`. The frontend waits for the API health check, then proxies `/api/v1` to `http://api:8000` over Docker's network. The API is also published at `http://127.0.0.1:8000` for local inspection. Both ports bind only to loopback because authentication is intentionally omitted in this development MVP.

The frontend runs a production Next.js build by default, so pages load immediately (use this for demos). Frontend source changes require `docker compose -f backend/compose.yaml build frontend` followed by `up -d`.

For hot reload while editing the frontend, layer the development override:

```sh
docker compose -f backend/compose.yaml -f backend/compose.dev.yaml up -d --wait
```

The development server compiles each route on its first request, so first loads can take a minute.

No model credentials are needed to open the workspace or use provider-independent processing. Live research chat, experiment-design tools, and new agent-analyzed reports require model configuration. Saved reports remain readable without it. Feature availability comes from `/api/v1/capabilities`.

## Alternative ports

Defaults are frontend 3000 and API 8000. If port 3000 is occupied, stop that process yourself or choose another Compose frontend port. In PowerShell:

```powershell
$env:STELLARIS_FRONTEND_PORT = '3100'
docker compose -f backend/compose.yaml up -d --wait
```

In a Unix shell:

```sh
STELLARIS_FRONTEND_PORT=3100 docker compose -f backend/compose.yaml up -d --wait
```

Then open `http://localhost:3100`. Compose includes the selected frontend port in the API's allowed browser origins. `STELLARIS_API_PORT` changes the API's host port. Internal traffic still uses `api:8000`.

## Model configuration and secrets

The user may populate `backend/.env` using the names in `backend/.env.example`. Compose loads it at runtime. Never commit credentials or copy them into docs, prompts, or logs. Agents must not inspect that file or mount host AWS profiles.

The current provider is AWS Bedrock with Amazon Nova. Configure `STELLARIS_MODEL_PROVIDER`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `BEDROCK_MODEL_ID`. Temporary credentials may also need `AWS_SESSION_TOKEN`. Live provider requests may incur charges and are separate from provider-free verification.

After configuration changes, run `docker compose -f backend/compose.yaml up -d --force-recreate api`. An unconfigured provider must fail honestly. Do not substitute fake sources, measurements, or conclusions.

## Status and logs

```sh
docker compose -f backend/compose.yaml ps
curl --fail http://127.0.0.1:8000/api/v1/health
curl --fail http://localhost:3000/api/v1/session
docker compose -f backend/compose.yaml logs --tail=50 frontend api
```

Replace 3000 if using a custom frontend port. Health reports database and Docker availability. Session returns an explicit local development identity with `auth_mode: "development_none"` and an empty CSRF token. The frontend accepts that explicit mode. The backend still checks Host/Origin and project-scoped references.

## Rebuild and stop

With the development override, frontend source changes appear through the bind mount without rebuilding. It uses Webpack with file polling so edits are detected through Windows Docker Desktop. Linux dependencies and Next.js build output live in separate Docker volumes, keeping them separate from host `node_modules` and `.next` directories.

With the development override, after changing `frontend/package.json` or `frontend/package-lock.json`, restart the frontend. Startup checks both files against the installed dependencies and runs `npm ci` when they differ. Unchanged dependencies are reused. Installing dependencies can take several minutes:

```sh
docker compose -f backend/compose.yaml restart frontend
```

After changing the frontend Dockerfile, rebuild and recreate only that service:

```sh
docker compose -f backend/compose.yaml up -d --build --no-deps --wait frontend
```

Backend, project-runtime, and worker source changes still require rebuilding the affected images. Compose mounts the canonical `docs/` folder read-only, so local documentation edits appear immediately without rebuilding. To stop the permanent services without deleting data:

```sh
docker compose -f backend/compose.yaml stop
```

Project containers have a separate lifecycle. Preserve their evidence and volumes. Do not use volume deletion or system-prune commands as routine troubleshooting.

## Frontend-only development

The complete Compose workflow includes hot reload and is preferred. To run the frontend on the host instead, stop the Compose frontend with `docker compose -f backend/compose.yaml stop frontend`, start only the API with `docker compose -f backend/compose.yaml up -d --wait api`, then run `npm ci` and `npm run dev` from `frontend/`.

The host frontend defaults to `http://127.0.0.1:8000`. An optional `frontend/.env.local` can set `STELLARIS_API_ORIGIN` to another compatible backend. Restart Next.js after changing it. Docker builds use `http://api:8000`, an internal hostname browsers should not contact directly.

All docs live in root `docs/`. A frontend route serves Markdown directly from that tree. Compose mounts it read-only at `/app/docs`. The frontend image also packages it as a fallback for deployments without that bind mount. There is no second authored documentation folder.

## Production frontend image

The Dockerfile retains its production `runtime` stage as the default for direct Docker builds. Build it independently of the development Compose service:

```sh
docker build -f frontend/Dockerfile --target runtime -t stellaris-frontend:production .
```

## Archived runtime cleanup

Startup reconciliation restores active project containers against their existing volumes.
It leaves archived projects out of automatic recreation, so explicitly removed old test
containers stay removed after restart. Existing archived containers are not automatically
stopped. Container cleanup preserves named workspace volumes and recorded evidence.
