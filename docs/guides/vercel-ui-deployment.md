# Vercel UI Deployment

Use this path when `src/synapse/ui/` is deployed on Vercel and the main Synapse
backend stays on a separate HTTPS origin on your own server.

## Required Runtime Contract

The deployed UI expects one public backend base URL that serves both:

- HTTPS requests for:
  - `POST /sessions`
  - `GET /sessions/{session_id}`
  - `GET /sessions/{session_id}/conversation`
  - `GET /sessions/{session_id}/diagnostics/timeline`
- secure websocket upgrades for:
  - `WS /sessions/{session_id}/stream`

Point `VITE_API_BASE_URL` at that public backend origin itself. Do not point it
at `/sessions`, `/gateway`, or the gateway host on port `8010`.

## Backend Configuration

The backend must allow the deployed frontend origin through
`SYNAPSE_CORS_ALLOWED_ORIGINS`:

```env
SYNAPSE_CORS_ALLOWED_ORIGINS=https://app.example.com
```

If you also use Vercel preview deployments, include those exact preview origins
as additional comma-separated values.

The main Synapse API should remain the upstream for browser session traffic.
The gateway host is a separate vendor-facing process and is not the frontend's
session API origin.

## Vercel Configuration

Set the Vercel frontend env var:

```env
VITE_API_BASE_URL=https://api.example.com
```

That value is consumed by `src/synapse/ui/src/lib/session-client.ts` and is
used for both HTTPS requests and websocket URL derivation.

For this repo's GitHub Actions production deploy path, the workflow currently
injects `VITE_API_BASE_URL=https://newbro.plutoless.com` directly during the
production build. Keep the Vercel project env aligned with the same value if
you also use manual Vercel CLI or dashboard-triggered deploys outside GitHub
Actions.

## Reverse Proxy Shape

If your public backend origin is served through Nginx, proxy the session routes
to the main Synapse API on `127.0.0.1:8000`.

Typical requirements:

- preserve the original `Host`
- forward `X-Forwarded-For` and `X-Forwarded-Proto`
- do not rewrite the `/sessions` path prefix
- keep websocket upgrade handling on `/sessions/{session_id}/stream`

Example shape:

```nginx
location ~ ^/sessions/[^/]+/stream$ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location = /sessions {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /sessions/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Verification

After deployment:

- verify `POST https://your-backend-origin/sessions`
- verify the deployed Vercel UI can load a session and conversation snapshot
- verify the websocket stream opens over `wss://.../sessions/{session_id}/stream`
- verify browser devtools show no CORS failures and no failed websocket
  handshake
