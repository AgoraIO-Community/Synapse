# Synapse

Backend-first prototype for a communication-brain / execution-brain runtime.

## Concept

- `Communication Brain`: handles acknowledgement, clarification, and user-facing status.
- `Execution Brain`: owns task lifecycle and executor orchestration.
- `Shared Blackboard`: the session-level state synchronization layer.
- `Protocols`: explicit schemas for messages, tasks, execution events, and stream events.

## CLI

Synapse requires Python 3.12 or newer.

For a fresh clone, use the repo bootstrap launcher:

```bash
./install.sh
./synapse setup
./synapse gateway setup
./synapse doctor
./synapse dev
```

`./install.sh` installs supported local development dependencies, creates `.venv`,
installs the project in editable mode, installs frontend dependencies, and writes
starter `~/.synapse/.env` plus `~/.synapse/config.yaml` files when they do not
already exist.

`./synapse setup` fills in `~/.synapse/.env` plus the shared
`~/.synapse/config.yaml` runtime/gateway config. By default it prompts for
required runtime values such as `OPENAI_API_KEY`, and it can also enter the
gateway-host setup flow. For gateway-only reconfiguration, use:

```bash
./synapse gateway setup
```

For automation, use:

```bash
OPENAI_API_KEY=... ./synapse setup --non-interactive
```

If you prefer the module entrypoint, it is available from the repo root and after
editable install:

```bash
python3 -m synapse --help
.venv/bin/python -m synapse --help
```

`~/.synapse/.env` is auto-loaded by the backend at startup. You do not need to export
variables manually. OpenAI is required for normal development and demo runtime,
so set `OPENAI_API_KEY` in `~/.synapse/.env` before starting the app.

## Optional ACPX Executor

If you want Synapse to delegate execution through `acpx` instead of the direct
Codex executor, install ACPX first:

```bash
npm install -g acpx@latest
```

Quick verification:

```bash
acpx --version
codex --version
```

Then add at least this to `~/.synapse/.env`:

```env
SYNAPSE_ACPX_EXECUTOR_ENABLED=true
```

Optional overrides:

```env
# SYNAPSE_ACPX_COMMAND=acpx
# SYNAPSE_ACPX_AGENT=codex
# SYNAPSE_ACPX_PERMISSION_MODE=approve-all
# SYNAPSE_ACPX_NON_INTERACTIVE_PERMISSIONS=deny
# SYNAPSE_ACPX_TIMEOUT_SECONDS=300
```

If both ACPX and the direct Codex executor are enabled, Synapse prefers ACPX.

## Common Commands

```bash
./install.sh
./synapse setup
./synapse gateway setup
./synapse doctor
./synapse dev
./synapse backend
./synapse frontend
./synapse start
./synapse gateway run
./synapse service install
./synapse service start
./synapse service stop
./synapse service restart
```

The installed console script is also named `synapse`, so after setup you can run
`.venv/bin/synapse dev` or activate the virtual environment and use `synapse dev`.

## Run Backend

```bash
./synapse backend
```

FastAPI docs will be available at:

```text
http://127.0.0.1:8000/docs
```

If the frontend shows `error` and messages do not progress, first confirm the
backend is running from the same virtual environment where dependencies were
installed.

To run only the frontend:

```bash
./synapse frontend
```

To run only the headless gateway host:

```bash
./synapse gateway run
```

## Ubuntu Systemd

For an Ubuntu server deployment from a repo checkout, install the combined
system service with:

```bash
./synapse service install
./synapse service start
```

The installed `synapse.service` unit runs `synapse start`, so it starts the
main backend and also starts the gateway host when `~/.synapse/config.yaml`
enables gateways.

This server path does not install or serve the Vite frontend. Use a separate
frontend deployment or reverse proxy if you need the browser UI.

The systemd unit runs as the user who invoked `./synapse service install` and
reads shared runtime-plus-gateway config from that user’s home directory:

```text
~/.synapse/.env
~/.synapse/config.yaml
```

If you install the service as `root`, it will run as `root` and use:

```text
/root/.synapse/.env
/root/.synapse/config.yaml
```

If the Codex executor is enabled, set an absolute
`runtime.codex_command` in `~/.synapse/config.yaml` so the service does not
depend on an interactive shell PATH.

When gateway modules are enabled in `~/.synapse/config.yaml`, `./synapse dev`
and `./synapse start` also start the gateway host automatically.

`./synapse dev` is the reload-capable local iteration path. `./synapse start`
does not reload Python code changes, so restart it after editing backend or
gateway host code.

The gateway host talks to the Synapse backend directly using the configured
`SYNAPSE_GATEWAY_SYNAPSE_BASE_URL` and does not use proxy environment variables
for its internal upstream traffic.

## Test

```bash
.venv/bin/python -m pytest
```

Frontend build check:

```bash
cd src/synapse/ui
npm run build
```

## Deploy UI to Vercel

The main UI lives under `src/synapse/ui/`.

Before deploying the frontend separately, make sure the backend is reachable on
its own public HTTPS origin, that the public backend origin preserves secure
websocket upgrades for `WS /sessions/{session_id}/stream`, and that the backend
allows the Vercel frontend origin through CORS:

```env
SYNAPSE_CORS_ALLOWED_ORIGINS=https://app.example.com,https://your-project.vercel.app
```

Then deploy from the UI workspace:

```bash
cd src/synapse/ui
npx vercel env add VITE_API_BASE_URL production
npx vercel --prod
```

Set the production `VITE_API_BASE_URL` value to your public backend base URL,
for example:

```text
https://api.example.com
```

If you also use Vercel preview deployments, add the same variable for the
`preview` environment and include that preview origin in
`SYNAPSE_CORS_ALLOWED_ORIGINS`.

If the backend is served behind Nginx on your server, proxy the public session
routes to the main Synapse API on port `8000` and keep websocket upgrade
headers intact for `/sessions/{session_id}/stream`. See
[`docs/guides/vercel-ui-deployment.md`](./docs/guides/vercel-ui-deployment.md)
for the full deployment contract and an example reverse-proxy shape.

This repo also includes a GitHub Actions workflow at
`.github/workflows/deploy-ui-vercel.yml`:

- pull requests deploy a Vercel preview for `src/synapse/ui`
- pushes to `main` deploy production
- `workflow_dispatch` can trigger a manual production deploy

Before enabling that workflow, configure these GitHub repository settings:

- Actions secret: `VERCEL_TOKEN`
- Actions variable or secret: `VERCEL_ORG_ID`
- Actions variable or secret: `VERCEL_PROJECT_ID`

The production GitHub Actions deploy now injects
`VITE_API_BASE_URL=https://newbro.plutoless.com` directly into the build so the
merge-to-`main` path does not depend on a separate Vercel production env entry.
If you also use manual Vercel CLI deploys outside GitHub Actions, keep the
Vercel project env aligned with that same value.
