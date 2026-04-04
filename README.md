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
