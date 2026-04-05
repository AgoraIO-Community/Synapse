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
Treat `docs/` as the project documentation and memory root.

- `docs/README.md` is the docs index.
- `docs/design.md` is the current stable architecture overview.
- `docs/architecture/`, `docs/protocol/`, `docs/guides/`, and `docs/decisions/` contain the stable topic docs.
- `docs/roadmap/` contains the maintained implementation roadmap and verification strategy.
- `docs/rfcs/` contains proposal / RFC-style design docs and must not be treated as the current implementation contract unless their content is merged into the stable docs.
- `docs/memories.md` records short factual notes for adopted, meaningful design and architecture changes.

When architecture, protocols, or runtime behavior changes in an adopted and implementation-relevant way:
- update `docs/design.md`
- update any other stable docs that become the source of truth for that topic
- append a short note to `docs/memories.md`

When implementation priorities, phase boundaries, or verification strategy change meaningfully:
- update `docs/roadmap/`

When a change is still proposal-only:
- update the proposal / RFC docs
- do not append it to `docs/memories.md` yet
- do not present the proposal as current runtime behavior

If stable docs and proposal docs conflict, treat the stable docs as authoritative.

Do not update memory docs for tiny refactors, formatting-only changes, or test-only changes.
Keep memory notes short and factual.
Do not claim this is automated; it is a repo convention for agents working here.
