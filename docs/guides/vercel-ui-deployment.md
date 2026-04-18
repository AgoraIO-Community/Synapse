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

If the deployed UI also enables the compact Agora voice accessory in the main
workbench, set a second frontend env var:

```env
VITE_GATEWAY_BASE_URL=https://gateway.example.com
```

That value is used only for browser calls to:

- `GET /gateway/agora-convoai/config`
- `POST /gateway/agora-convoai/sessions/prepare`
- `POST /gateway/agora-convoai/sessions/activate`
- `POST /gateway/agora-convoai/sessions/stop`

The main shell's `Voice` mode now rebinds the whole frontend to the
gateway-returned `synapse_session_id`, so deployed environments must ensure the
public main-backend origin and the public gateway origin are both reachable from
the browser during mode switches.

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
VITE_GATEWAY_BASE_URL=https://gateway.example.com
```

That value is consumed by `src/synapse/ui/src/lib/session-client.ts` and is
used for both HTTPS requests and websocket URL derivation.
`VITE_GATEWAY_BASE_URL` is consumed by
`src/synapse/ui/src/lib/gateway-client.ts` for voice gateway calls only.

For this repo's GitHub Actions production deploy path, the workflow currently
injects `VITE_API_BASE_URL=https://newbro.plutoless.com` directly during the
production build. Keep the Vercel project env aligned with the same value if
you also use manual Vercel CLI or dashboard-triggered deploys outside GitHub
Actions.

## Reverse Proxy Shape

If your public backend origin is served through Nginx, proxy the session routes
to the main Synapse API on `127.0.0.1:8000`.

If you choose not to expose a separate `VITE_GATEWAY_BASE_URL`, the same public
origin must also proxy `/gateway/agora-convoai/*` to the gateway host on
`127.0.0.1:8010`.

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
- verify `GET https://your-gateway-origin/gateway/agora-convoai/config` when
  `VITE_GATEWAY_BASE_URL` is set
- verify the main UI can start and stop the voice accessory without CORS or
  mixed-origin failures
- verify browser devtools show no CORS failures and no failed websocket
  handshake
