# Synopse

Backend-first prototype for a communication-brain / execution-brain runtime.

## Concept

- `Communication Brain`: handles acknowledgement, clarification, and user-facing status.
- `Execution Brain`: owns task lifecycle and executor orchestration.
- `Shared Blackboard`: the session-level state synchronization layer.
- `Protocols`: explicit schemas for messages, tasks, execution events, and stream events.

## Run

```bash
uvicorn runtime.main:app --reload
```

If the frontend shows `error` and messages do not progress, make sure backend WebSocket support and Python dependencies are installed:

```bash
source .venv/bin/activate
pip install -e '.[dev]'
```

OpenAI is required for normal development and demo runtime:

```bash
cp .env.example .env.local
# then fill in OPENAI_API_KEY in .env.local
```

`.env.local` is auto-loaded by the backend at startup. You do not need to export variables manually.

Without a valid `OPENAI_API_KEY` in `.env.local` or your shell environment, the backend should fail to start.

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

Frontend build check:

```bash
cd frontend
npm run build
```
