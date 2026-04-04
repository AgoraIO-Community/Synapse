# Memories

Short log of important design decisions and changes for Synopse.

## 2026-04-04

- Established the concept-first architecture around `Communication Brain`, `Execution Brain`, `Shared Blackboard`, and protocol-first boundaries.
- Chose a backend-first FastAPI prototype with typed runtime, task, execution, conversation, and stream protocols.
- Defined V1 runtime scope as single-executor, while keeping schemas multi-executor compatible through task graph and executor identity fields.
- Used an in-memory blackboard and a generic mock executor to validate runtime flow before introducing real executors.
- Treated `docs/design.md` as the current architecture source of truth and `docs/memories.md` as the running decision log.
- Added a separate minimal `React + Vite + TypeScript` frontend workspace for experiencing the runtime through chat, task cards, and a live event feed.
- Renamed the backend Python package from `app/` to `runtime/` so the module path reflects the runtime role instead of a generic placeholder.
