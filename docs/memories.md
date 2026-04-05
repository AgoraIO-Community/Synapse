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
- Added a first-class conversation-only path with `chat_reply` so ordinary chat is no longer forced into `clarify`; clarification is now reserved for unresolved task/control intent.
- Added a generic external-executor integration layer plus an isolated Codex-backed executor adapter, while keeping the execution brain and transport on normalized executor protocols and exposing executor capabilities through session snapshots.
- Tightened `conversation-only` to social/meta chat only, routing capability-gated questions into normal executor tasks, and enriched response generation context so replies are authored from the agent’s perspective instead of echoing the user message.
- Switched task defaulting so Codex becomes the effective default executor when enabled, while completion replies prefer real executor result text over generic success status when available.
- Added a runtime guard so capability-gated questions are blocked with a clear explanation when only the mock executor is active, instead of producing misleading fake-success task flows.
- Simplified task creation so every `create_task` now requires a real executor, closing the hole where some LLM-produced tasks could still bypass the mock-executor guard.
- Added streamed response generation on the existing session websocket, with transient partial communication chunks updating one live assistant bubble while only the final communication event is persisted.
- Separated concise spoken-style communication from fuller task output, keeping task-board results sourced from artifacts while response generation summarizes them for TTS-friendly delivery.
- Removed `pause_task` and `resume_task` from the current runtime surface, leaving `cancel_task` and `retry_task` as the supported explicit task controls.
- Added blackboard-backed message history for both message interpretation and response generation, capped at 30 persisted user/assistant messages and excluding transient stream chunks.
- Added LLM latency diagnostics to trace payloads, recording total request duration for normal calls and `ttfb_ms` for true streamed responses, while hiding transient `response_chunk` entries from the operator activity feed/export.
- Enriched `response_render_completed` so it now carries a nested `llm_response` summary with final rendered text plus duration and optional `ttfb_ms` when the response came from the LLM.
- Switched the Codex executor to `codex exec --json`, normalizing in-flight agent activity back into `ExecutionEvent` updates and keeping those mid-run updates transient on the execution stream instead of introducing a Codex-specific protocol surface.
- Tightened message interpretation so obvious social and subjective prompts such as feelings or opinion questions stay in `conversation_only`, while explicit executor-backed work requests still route to tasks even when phrased with a social opener.
- Reduced message-interpreter prompt size by replacing the full serialized session snapshot with compact interpreter context: only recent message history plus pending clarifications and executor capability summaries.
- Updated task graph construction to preserve an explicit `requires_executor_capability = false` override from the action bundle while still defaulting new tasks to real-executor requirements.
- Trimmed unnecessary interpreter JSON-schema fields so the model no longer has to fill redundant routing flags or runtime-owned create-task knobs on every action.
- Reshaped the interpreter Structured Outputs action schema into a lean single action object that stays OpenAI-compatible while still avoiding most redundant null-heavy padding fields.
- Added a stable prompt-cache key and shorter static interpreter instructions so repeated structured interpreter calls can reuse the same cached prompt prefix more effectively.
- Removed local semantic routing rewrites after `responses.parse()` so the interpreter now trusts the LLM's structured `conversation_only` / `task` / `clarification` result instead of reclassifying it in app code.
- Bound task-bearing user messages back to their resolved `task_id` in message history and changed terminal task replies to render from task-scoped history plus the originating user message, so unrelated later chat no longer pollutes a task's completion reply.
- Added fail-fast validation for interpreter-produced `create_task` actions so non-empty task goals are required, titles are derived only from valid goals, and malformed task payloads are rejected before blank tasks can enter the execution brain.
- Added a compact `active_tasks` summary to interpreter input, exposing only active task ids and goals so follow-up messages can better resolve to existing work without reintroducing the full session snapshot.
- Tightened `update_task` so it now requires a non-empty goal, and changed follow-ups against already-`done` tasks to fall back to creating a new task instead of restarting the completed one in place.
