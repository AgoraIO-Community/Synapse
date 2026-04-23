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
./newbro setup
./newbro connector setup
./newbro doctor
./newbro dev
```

`./install.sh` installs supported local development dependencies, creates `.venv`,
installs the project in editable mode, installs frontend dependencies, and writes
starter `~/.newbro/.env` plus `~/.newbro/config.yaml` files when they do not
already exist.

`./newbro setup` fills in `~/.newbro/.env` plus the shared
`~/.newbro/config.yaml` runtime/api/connectors config. By default it prompts for
required runtime values such as `OPENAI_API_KEY`, and it can also enter the
connector-host setup flow. For connector-only reconfiguration, use:

```bash
./newbro connector setup
```

For automation, use:

```bash
OPENAI_API_KEY=... ./newbro setup --non-interactive
```

If you already have legacy Synapse config under `~/.synapse` and `~/.newbro`
does not exist yet, the CLI migrates that home directory to `~/.newbro` on the
first run.

## Install From PyPI

Install the public package with:

```bash
python3 -m pip install newbro-cli
newbro --help
newbro executor setup
newbro executor run --base-url https://synapse.example.com --node-id node-1234 --token secret
```

`~/.newbro/.env` is auto-loaded by the backend at startup. You do not need to export
variables manually. OpenAI is required for normal development and demo runtime,
so set `OPENAI_API_KEY` in `~/.newbro/.env` before starting the app.

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

Then add at least this to `~/.newbro/.env`:

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
./newbro setup
./newbro connector setup
./newbro doctor
./newbro dev
./newbro backend
./newbro frontend
./newbro start
./newbro connector run
./newbro service install
./newbro service start
./newbro service stop
./newbro service restart
```

The installed console script is named `newbro`, so after setup you can run
`.venv/bin/newbro dev` or activate the virtual environment and use `newbro dev`.

## Run Backend

```bash
./newbro backend
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
./newbro frontend
```

To run only the headless connector host:

```bash
./newbro connector run
```

## Ubuntu Systemd

For an Ubuntu server deployment from a repo checkout, install the combined
system service with:

```bash
./newbro service install
```

`./newbro service install` now installs or updates the unit, reloads systemd,
enables the unit, and restarts the service so the latest code is live
immediately.

The installed `newbro.service` unit runs `newbro start`, so it serves one
main Synapse service on the public port.

This path stays inside the repo checkout. The main service serves
`src/synapse/ui/dist` at `/`, keeps the normal API and websocket routes on the
same origin, and mounts `/api/connectors/...` routes directly when connectors are
enabled.

The systemd unit runs as the user who invoked `./newbro service install` and
reads shared runtime-plus-connector config from that user’s home directory:

```text
~/.newbro/.env
~/.newbro/config.yaml
```

If you install the service as `root`, it will run as `root` and use:

```text
/root/.newbro/.env
/root/.newbro/config.yaml
```

If the Codex executor is enabled, set an absolute
`runtime.codex_command` in `~/.newbro/config.yaml` so the service does not
depend on an interactive shell PATH.

`./newbro dev` and `./newbro start` do not auto-start the standalone connector
host. Run `./newbro connector run` separately when you want the detached connector
process for direct connector testing or separate deployment.

`./newbro dev` is the reload-capable local iteration path. `./newbro start`
does not reload Python code changes, so restart it after editing backend,
connector modules, or other Python service code.

The connector host talks to the Synapse backend directly using the configured
`SYNAPSE_CONNECTOR_SYNAPSE_BASE_URL` and does not use proxy environment variables
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

Release build and publish:

```bash
python3 -m pip install '.[release]'
python3 -m build
python3 -m twine check dist/*
python3 -m twine upload dist/*
```

Or use the helper script:

```bash
PYPI_TOKEN='pypi-...' ./scripts/publish_pypi.sh
PYPI_TOKEN='pypi-...' ./scripts/publish_pypi.sh --testpypi
./scripts/publish_pypi.sh --dry-run
```

## Deploy UI to Vercel

The main UI lives under `src/synapse/ui/`.

Before deploying the frontend separately, make sure the backend is reachable on
its own public HTTPS origin, that the public backend origin preserves secure
websocket upgrades for `WS /api/sessions/{session_id}/stream`, and that the backend
allows the Vercel frontend origin through CORS:

```env
SYNAPSE_CORS_ALLOWED_ORIGINS=https://app.example.com,https://your-project.vercel.app
```

Then deploy from the UI workspace:

```bash
cd src/synapse/ui
npx vercel env add VITE_API_BASE_URL production
npx vercel env add VITE_CONNECTOR_BASE_URL production
npx vercel --prod
```

Set the production frontend base URLs to your public server origin, for
example:

```text
VITE_API_BASE_URL=https://newbro.plutoless.com
VITE_CONNECTOR_BASE_URL=https://newbro.plutoless.com
```

If you also use Vercel preview deployments, add the same variable for the
`preview` environment and include that preview origin in
`SYNAPSE_CORS_ALLOWED_ORIGINS`.

If the deployed UI enables voice mode, the connector host must also allow the
frontend origin. Configure that in `~/.newbro/config.yaml` under:

```yaml
connector_host:
  cors_allowed_origins:
    - https://newbro.agora-io.czhen.work
```

If the backend is served behind Nginx on your server, proxy the public session
routes to the main Synapse API on port `8000`, proxy `/api/connectors/...` to the
connector host on `8010`, and keep websocket upgrade headers intact for
`/api/sessions/{session_id}/stream`. See
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
`VITE_API_BASE_URL=https://newbro.plutoless.com` and
`VITE_CONNECTOR_BASE_URL=https://newbro.plutoless.com` directly into the build so
the merge-to-`main` path does not depend on separate Vercel production env
entries.
If you also use manual Vercel CLI deploys outside GitHub Actions, keep the
Vercel project env aligned with those same values.
