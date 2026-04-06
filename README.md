# Synopse

Backend-first prototype for a communication-brain / execution-brain runtime.

## Concept

- `Communication Brain`: handles acknowledgement, clarification, and user-facing status.
- `Execution Brain`: owns task lifecycle and executor orchestration.
- `Shared Blackboard`: the session-level state synchronization layer.
- `Protocols`: explicit schemas for messages, tasks, execution events, and stream events.

## Run

## Backend Setup

Synopse requires Python 3.12 or newer.

Create a virtual environment in the repo root:

```bash
python3.12 -m venv .venv
```

If `python3.12` is not available on your machine, use another Python 3.12+
interpreter path that resolves to the same version.

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -e '.[dev]'
```

Configure environment variables:

```bash
cp .env.example .env.local
# then fill in OPENAI_API_KEY in .env.local
```

`.env.local` is auto-loaded by the backend at startup. You do not need to export
variables manually.

OpenAI is required for normal development and demo runtime. Without a valid
`OPENAI_API_KEY` in `.env.local` or your shell environment, the backend should
fail to start.

## Run Backend

```bash
uvicorn synopse.api.app:app --reload
```

If you prefer not to activate the virtual environment first:

```bash
.venv/bin/uvicorn synopse.api.app:app --reload
```

FastAPI docs will be available at:

```text
http://127.0.0.1:8000/docs
```

If the frontend shows `error` and messages do not progress, first confirm the
backend is running from the same virtual environment where dependencies were
installed.

Frontend:

```bash
cd frontend
bun install
bun run dev
```

## Test

```bash
pytest
```

Or without activating the virtual environment:

```bash
.venv/bin/python -m pytest
```

Frontend build check:

```bash
cd frontend
npm run build
```
