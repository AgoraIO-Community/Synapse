# AGENTS.md

## Project
Synopse is a backend-first prototype for a communication-brain / execution-brain runtime.

Core concepts:
- Communication Brain
- Execution Brain
- Shared Blackboard
- Protocol-first runtime

## Stack
- Python 3.12
- FastAPI
- Pydantic
- Pytest
- React
- Vite
- TypeScript

## Run
```bash
uvicorn runtime.main:app --reload
```

## Test
```bash
pytest
```

## Guardrails
- Keep Communication Brain and Execution Brain separate.
- Keep transport thin.
- Treat protocol models as the source of truth.
- Runtime V1 is single-executor, but schemas must stay multi-executor compatible.

## Project Memory
Treat `docs/` as the project memory.

- `docs/design.md` is the current architecture doc.
- `docs/memories.md` records important design decisions and changes.

When architecture, protocols, or runtime behavior changes in a meaningful way:
- update `docs/design.md`
- append a short note to `docs/memories.md`

Do not update memory docs for tiny refactors, formatting-only changes, or test-only changes.
Keep memory notes short and factual.
Do not claim this is automated; it is a repo convention for agents working here.
