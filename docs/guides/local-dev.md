# Local Development

Preferred local bootstrap and run flow:

```bash
./install.sh
./synapse setup
./synapse doctor
./synapse dev
```

`./install.sh` owns local dependency bootstrap. On reruns it skips system
prerequisite installs when a supported Python 3.12+ interpreter and `bun` are
already available, but it still refreshes the repo virtualenv and frontend
dependencies. It also creates starter `~/.synapse/.env` plus
`~/.synapse/config.yaml` files when they do not already exist. `./synapse
setup` owns interactive runtime configuration for `~/.synapse/.env` plus the
shared `~/.synapse/config.yaml`.

By default, diagnostics timeline polling requests from the frontend inspector are
filtered out of `uvicorn.access` output so local access logs are less noisy. Set
`SYNAPSE_QUIET_DIAGNOSTICS_ACCESS_LOGS=false` if you want to see those polling
requests during development.

Current test command:

```bash
.venv/bin/python -m pytest
```

Real executors now run through the detached executor host.

Typical local real-executor flow:

```bash
./synapse setup
./synapse executor setup
./synapse backend
./synapse executor run
```

`./synapse setup` configures the main control plane, including whether detached
executors are enabled and which executor families the control plane should
expect.
`./synapse executor setup` configures the detached executor host itself,
including the Synapse base URL, a generated executor-node host id, and local
Codex or ACPX command settings.
`./synapse executor run` now reports foreground lifecycle state directly in the
terminal:

- `[start]` after local config is loaded
- `[connect]` before each control-channel dial attempt
- `[ready]` only after the host registers successfully with Synapse
- `[warn]` plus `[retry]` when connection or registration fails and the host is
  retrying
- `[stop]` on manual interrupt

`./synapse dev` and `./synapse start` do not auto-start the executor host.
Run `./synapse executor run` explicitly when you want local real execution.

Backend-only and frontend-only commands:

```bash
./synapse backend
./synapse frontend
```

`./synapse start` is the production-style runtime entrypoint used by the
systemd service path. It expects an existing frontend production build and runs
one main Synapse service on the public port. That service serves the built UI
from `/`, keeps the normal API and websocket routes on the same origin, and
mounts `/gateway/...` routes directly when gateways are enabled.

`./synapse dev` runs the same main service with reload on port `8000` plus the
separate Vite frontend on `5173`. The Vite workspace proxies both `/sessions`
and `/gateway` to the local main service while you iterate on the UI.

`./synapse gateway run` remains available when you want to run the standalone
headless gateway host by itself for separate deployment or direct gateway
testing.

Separate frontend production deployments are documented in
[`./vercel-ui-deployment.md`](./vercel-ui-deployment.md). Local
`./synapse dev` and `./synapse frontend` do not require `VITE_API_BASE_URL`
unless you intentionally want the local browser app to target a separate public
backend.

The repo-root bootstrap launcher keeps first-run setup working even before the
package is installed. After setup, the installed console script and module entry
are also available:

```bash
.venv/bin/synapse dev
.venv/bin/python -m synapse dev
```
