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
./synapse setup
./synapse doctor
./synapse dev
```

`./synapse setup` creates `.venv`, installs the project in editable mode, installs
frontend dependencies with Bun first and npm fallback, and creates `.env.local`
from `.env.example` when missing.

If you prefer the module entrypoint, it is available from the repo root and after
editable install:

```bash
python3 -m synapse --help
.venv/bin/python -m synapse --help
```

`.env.local` is auto-loaded by the backend at startup. You do not need to export
variables manually. OpenAI is required for normal development and demo runtime,
so set `OPENAI_API_KEY` in `.env.local` before starting the app.

## Common Commands

```bash
./synapse setup
./synapse doctor
./synapse dev
./synapse backend
./synapse frontend
./synapse start
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

## Test

```bash
.venv/bin/python -m pytest
```

Frontend build check:

```bash
cd frontend
npm run build
```
