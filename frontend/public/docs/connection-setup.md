# Connecting the Stellaris frontend

The merged frontend requires a running backend. Starting Next.js alone does not supply authentication, project storage, or scientific execution.

## Local configuration

In `frontend/`, copy `.env.example` to `.env.local` and set the backend origin:

```dotenv
STELLARIS_API_ORIGIN=http://127.0.0.1:5000
NEXT_PUBLIC_LOGIN_URL=
```

Use the real backend's HTTP(S) origin without `/api/v1`. Restart Next.js after changing this setting. `NEXT_PUBLIC_LOGIN_URL` is optional and must point to an actual login flow when one exists.

Start the frontend with `npm run dev`. For a production check, use `npm run build`, then `npm start`.

## What the backend needs to provide

The frontend first requests `/api/v1/session`, then `/api/v1/capabilities`. Requests are forwarded to the configured backend origin. An authenticated session supplies the session cookie and CSRF token. The complete [API contract](frontend-backend-contract.md) defines the payloads and all subsequent project requests.

As of this integration, `backend/` contains only `.gitkeep`. There is no backend startup command or API implementation in this repository yet. Configure an existing compatible backend, or implement the contracted backend before expecting project workflows to load. Do not fabricate a session or research results to bypass this requirement.

## If the connection screen appears

- Open “Connection details” to identify whether session or capability loading failed.
- Check the frontend terminal for proxy errors. `ECONNREFUSED` means no service accepted the connection at the configured backend address. Next.js may return HTTP 500 for that failed forwarding request.
- Confirm the backend origin and port, start the actual backend, and restart Next.js if configuration changed.
- A backend HTTP 401 requires the configured login flow. A backend HTTP 500 requires inspecting the backend's own logs.
- Use “Retry connection” after correcting the service or configuration.

This screen does not indicate that the frontend components failed to merge. It protects the workspace from displaying fabricated or unauthenticated project data.
