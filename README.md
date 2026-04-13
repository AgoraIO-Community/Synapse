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

`./synapse setup` fills in `~/.synapse/.env` with real runtime values. By
default it prompts for
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

The systemd unit runs as the deploying user and reads runtime config from:

```text
~/.synapse/.env
~/.synapse/config.yaml
```

If the Codex executor is enabled, prefer an absolute
`SYNAPSE_CODEX_COMMAND=/absolute/path/to/codex` in `~/.synapse/.env` so the
service does not depend on an interactive shell PATH.

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
