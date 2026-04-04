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
- Added explicit backend WebSocket runtime support and gated frontend message sending on the initial stream snapshot so the UI does not accept input before realtime is actually connected.
- Renamed key runtime files and variables toward the architecture language: `Action Router`, `Message Interpreter`, `Interaction Policy`, `Event-to-Response Mapper`, `Runtime State Store`, and `Executor Adapter Router`.
- Added a real OpenAI-backed path for `message_interpreter` and `response_generator`, with schema-strict interpretation and explicit fail-fast behavior when OpenAI is enabled but unavailable.
- Removed stub LLM mode from normal runtime behavior; OpenAI is now required for development/demo, while fake providers remain available only in tests.
- Added auto-loaded `.env.local` support plus `.env.example` so local runtime configuration no longer requires manual shell exports.
- Added a dedicated trace stream beside the main event stream so module-level causality can be inspected without mixing trace records into the product-facing runtime feed.
