# Stellaris

A persistent workspace for research, experiments, inspectable evidence, and scientific reports.

## Run with Docker Compose

Start Docker Desktop, then run from the repository root:

```sh
docker compose -f backend/compose.yaml --profile build-only build
docker compose -f backend/compose.yaml up -d --wait
```

Open [Stellaris](http://localhost:3000). The API is available locally on port 8000. Compose connects the frontend directly to the API container. No separate frontend development server or Python environment is required.

All authored documentation lives in [`docs/`](docs/README.md). Start with the [Compose guide](docs/docker-compose.md). The frontend also serves this same documentation tree at `/docs/`.

The next interface is specified publicly in [Research desk widgets](docs/research-workspace-spec.md), [Materials views](docs/materials-views-spec.md), and [Reports](docs/reports-spec.md). These documents describe proposed behavior, not completed UI changes.
