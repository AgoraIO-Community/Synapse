# Cloudflare Pages Deployment

Use this path when:

- the repo lives on GitHub
- the frontend is deployed from GitHub to Cloudflare Pages
- the API runs on a dedicated server, not your laptop
- local Codex or ACPX executors connect out as detached nodes and do not accept public inbound traffic

This is the recommended production shape for Newbro.

## Target Topology

- GitHub: source of truth for code and deploy triggers
- Cloudflare Pages: hosts `src/newbro/ui`
- Dedicated API host: runs `newbro.service.app`
- Optional standalone connector host: runs only if you want `/api/connectors/...` on a separate origin
- Local workstation: runs `newbro executor run ...` only, with outbound websocket access to the API host

Do not expose your laptop through a public Cloudflare Tunnel for normal production traffic.

## Security Model

Protect the public frontend and API with Cloudflare Access, then keep app-level authentication enabled in Newbro.

Recommended layers:

1. Cloudflare Access in front of the public API origin
2. `SYNAPSE_API_AUTH_REQUIRED=true` in Newbro
3. One of:
   - Cloudflare Access JWT validation through `SYNAPSE_CLOUDFLARE_ACCESS_TEAM_DOMAIN` and `SYNAPSE_CLOUDFLARE_ACCESS_AUDIENCE`
   - `SYNAPSE_API_BEARER_TOKEN` for scripts, automation, or temporary fallback
4. Optional Cloudflare Access service token for machine-to-machine callers:
   - `SYNAPSE_CLOUDFLARE_ACCESS_CLIENT_ID`
   - `SYNAPSE_CLOUDFLARE_ACCESS_CLIENT_SECRET`

Do not rely on CORS as a security boundary.

## Frontend Setup

Cloudflare Pages should build from:

```text
src/newbro/ui
```

Typical build settings:

```text
Build command: npm run build
Build output directory: dist
```

Set frontend environment variables in Cloudflare Pages:

```env
VITE_API_BASE_URL=https://api.example.com
VITE_CONNECTOR_BASE_URL=https://api.example.com
```

If you intentionally deploy the connector host on a separate public origin:

```env
VITE_CONNECTOR_BASE_URL=https://connectors.example.com
```

`VITE_API_BEARER_TOKEN` is supported, but only use it for tightly controlled non-browser cases. In a browser deployment, prefer Cloudflare Access so the frontend can authenticate through cookies or Access headers instead of shipping a long-lived secret.

## API Host Setup

Run the API on a dedicated Linux host or container host.

The safest default is to bind Newbro only to loopback and let Nginx, Caddy, or Cloudflare Tunnel on that server handle the public edge:

```bash
./newbro service install --host 127.0.0.1 --port 8000
```

Required environment settings:

```env
SYNAPSE_API_AUTH_REQUIRED=true
SYNAPSE_CORS_ALLOWED_ORIGINS=https://your-pages-project.pages.dev,https://app.example.com
SYNAPSE_CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com
SYNAPSE_CLOUDFLARE_ACCESS_AUDIENCE=your-access-audience
```

Optional script or service-token settings:

```env
SYNAPSE_API_BEARER_TOKEN=replace-with-random-token
SYNAPSE_CLOUDFLARE_ACCESS_CLIENT_ID=replace-with-access-client-id
SYNAPSE_CLOUDFLARE_ACCESS_CLIENT_SECRET=replace-with-access-client-secret
```

## Connector Host Setup

If the main service already mounts `/api/connectors/...`, you do not need a second public connector origin.

If you do run a standalone connector host:

- keep it on the dedicated server, not your laptop
- bind it to `127.0.0.1` unless a reverse proxy on that same host forwards traffic to it
- point `connector_host.public_base_url` at the public HTTPS origin
- point `connector_host.synapse_base_url` at the internal API origin, usually `http://127.0.0.1:8000`

For machine-to-machine connector calls back into the main API, reuse:

```env
SYNAPSE_API_BEARER_TOKEN=...
```

or the Cloudflare Access service token pair.

## Local Executor Node Setup

Your laptop should only run the detached executor node and connect outward to the public API origin:

```bash
newbro executor run \
  --base-url https://api.example.com \
  --node-id node-123 \
  --token node-token
```

If the public API origin is protected by Cloudflare Access and the executor node is not running in a browser, configure one of:

- `executor_node.api_bearer_token`
- `executor_node.cloudflare_access_client_id`
- `executor_node.cloudflare_access_client_secret`

in `~/.newbro/config.yaml`.

That lets the node authenticate its outbound websocket to `/api/executors/control` without exposing your workstation to inbound traffic.

## Verification

After deployment, verify:

1. The Pages frontend loads from Cloudflare Pages.
2. `POST https://api.example.com/api/sessions` succeeds only when authenticated.
3. The session websocket opens from the browser after Cloudflare Access login.
4. The connector endpoints work from the deployed frontend.
5. A local executor node can connect out to `/api/executors/control`.
6. Nothing on your laptop is publicly reachable on ports `8000`, `8010`, or `5173`.

## Practical Rollout Order

1. Push code to GitHub.
2. Deploy the frontend to Cloudflare Pages.
3. Move the API to a dedicated host.
4. Enable Cloudflare Access on the API origin.
5. Turn on `SYNAPSE_API_AUTH_REQUIRED=true`.
6. Reconnect your laptop only as a detached executor node.
