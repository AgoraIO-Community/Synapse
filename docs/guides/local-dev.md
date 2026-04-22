# Local Development

Preferred local bootstrap and run flow:

```bash
./install.sh
./synapse setup
./synapse doctor
./synapse dev
```

`./install.sh` owns local dependency bootstrap and creates starter
`~/.synapse/.env` plus `~/.synapse/config.yaml` files when they do not already
exist. `./synapse setup` owns interactive runtime configuration for
`~/.synapse/.env` plus the shared `~/.synapse/config.yaml`.

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

`./synapse dev` and `./synapse start` do not auto-start the executor host.
Run `./synapse executor run` explicitly when you want local real execution.

Backend-only and frontend-only commands:

```bash
./synapse backend
./synapse frontend
```

`./synapse start` is the production-style runtime entrypoint used by the
systemd service path. It expects an existing frontend production build, starts
the in-repo `synapse.edge` transport on the public port, and keeps the main
backend behind that edge layer on an internal port.

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
