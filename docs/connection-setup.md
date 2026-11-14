# Connection troubleshooting

Start with the [Docker Compose guide](docker-compose.md). Merging source does not build images or start services.

## The connection screen shows HTTP 500

Expand Connection details and note the failed request. `/api/v1/session` is the first request.

1. Confirm Docker Desktop is running.
2. From the repository root, run `docker compose -f backend/compose.yaml ps`.
3. Build all images with `docker compose -f backend/compose.yaml --profile build-only build`.
4. Start the application with `docker compose -f backend/compose.yaml up -d --wait`.
5. Check `http://127.0.0.1:8000/api/v1/health`, then the frontend's `/api/v1/session`.

`ECONNREFUSED` means no service accepts the configured connection. The earlier frontend port 5000 did not match the backend's port 8000. Host development now defaults to 8000. Compose supplies the internal `api:8000` address automatically.

For a separate frontend development server, check your own `STELLARIS_API_ORIGIN` configuration and restart Next.js after correcting it. Do not point a host frontend at Docker's internal hostname `api`.

## Session works but project creation fails

The backend intentionally omits authentication and returns `auth_mode: "development_none"` with an empty CSRF token. The frontend accepts this explicit mode and still requires a resolved session and stable command identifiers.

HTTP 403 with `CSRF_FAILED` may indicate an unrecognized browser origin. Use the frontend port configured through Compose. Do not disable Host/Origin checks to work around an address mismatch.

Project creation also requires the project-runtime image and Docker access. Use the complete build command, not only the API image build. Inspect structured errors instead of fabricating a successful project locally.

## Research chat fails

Check feature availability through `/api/v1/capabilities` and redacted backend errors. Opening projects does not establish live model access. Only the user should populate secrets in `backend/.env`. See [model configuration](docker-compose.md#model-configuration-and-secrets).
