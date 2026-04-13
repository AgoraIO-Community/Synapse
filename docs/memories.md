# Memories

Short log of important design decisions and changes for Synapse.

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

## 2026-04-06

- Tightened `control_task` so the communication tool surface accepts only canonical protocol command tokens such as `resume_task`, and invalid LLM-emitted aliases now round-trip through the OpenAI tool loop instead of crashing the message route.
- Switched the communication LLM path to a traditional OpenAI-compatible `chat.completions` loop that replays the local 30-message conversation history each turn instead of using Responses API conversation-state handles.
- Tightened executor selection so `create_task` rejects unknown `preferred_executor` ids and queued tasks with already-invalid executor ids now fail with a summary instead of crashing execution.
- Added a real Codex app-server executor path in `src/synapse`, wired runtime bootstrap to enable it via `SYNAPSE_CODEX_EXECUTOR_ENABLED`, and made Codex the default executor when enabled successfully while keeping mock available for explicit fallback and tests.
- Changed session message and command handling to schedule execution in a background loop instead of awaiting executor completion inline, so Codex-backed work no longer blocks the HTTP request path and snapshot updates flow over the existing session stream.
- Reused the session websocket as a bidirectional mixed stream, keeping snapshot/debug events while adding websocket `send_message` / `send_command` actions plus transient assistant-response events and hiding internal communication tool calls from the frontend transport.
- Reworked the communication tool surface around `add_task_note`, `add_constraint`, and `list_tasks`, removed silent latest-task fallback for ambiguous references, and added communication eval scaffolding for tool choice and spoken-reply quality regression checks.
- Added executor-availability context to the communication model and blocked capability-gated requests in mock-only mode, so requests like checking CPU usage no longer fall back to generic chat advice when no real executor is available.
- Added a repo-root `ARCHITECTURE.md` as the unified stable architecture overview and aligned the stable split docs to the same dual-brain, blackboard-centered target design.
- Unified Communication Brain around a task-first mental model with explicit mock-safe task creation, and added stable `TaskExecutionMode` blackboard projection with `undecided / lightweight / managed` classification.
- Added end-to-end proactive notification delivery with persisted `NotificationCandidate` projections, basic merge/defer policy, and emitted assistant updates written into user-visible conversation history.
- Narrowed `SessionSnapshot` to durable task/execution state only, and split durable conversation history plus debugger-oriented mutation/command/recent-write data into separate session projections and stream events.
- Added realtime-only `llm_trace` websocket events so the debugger UI can inspect LLM request/response payloads for normal message turns and proactive notification rendering without polluting durable projections.
- Enriched live `llm_trace` message payloads with tool invocation result summaries/previews and added a dedicated Tool Call History panel derived from those realtime trace events.
- Replaced derived Tool Call History with first-class realtime `tool_call` websocket events emitted from actual tool invocation attempts, including success/failure outcomes, so the debugger no longer reconstructs history from `llm_trace`.
- Added a diagnosis-first observability subsystem with canonical backend diagnostic events, correlation ids, reason codes, stdout JSON logging, and a per-session timeline API without changing the product-facing websocket stream contract.
- Added readable compact colorized console logs for observability when stdout is a terminal, while keeping JSON-line output when logs are redirected or piped.
- Removed the dedicated debug route and debugger-only websocket events, moving prompt/tool/blackboard inspection onto log-backed diagnostics timeline events while keeping the session websocket focused on assistant transport and durable snapshots.
- Quieted local access logs by filtering diagnostics timeline polling requests from `uvicorn.access` by default, and made the frontend diagnostics polling visibility-aware instead of polling continuously in hidden tabs.
- Removed the dedicated LLM trace UI and dropped backend prompt-trace diagnostic events, keeping tool-call and lifecycle logs as the main communication-side debugging surface.
- Restored backend-only LLM diagnostic events as summary logs by default, with verbose prompt/message payloads gated behind `SYNAPSE_LOG_LLM_DETAILS`, while leaving the dedicated LLM trace UI removed.

## 2026-04-07

- Tightened Communication Brain prompt policy so fact-checking, current-world information, and other live external-fact requests now default toward executor-backed `create_task` handling, with short clarifications for missing required details and no generic website/app fallback advice in mock-only mode.
- Focused notification LLM rendering on selected candidate-linked task context by adding structured recent-chat continuity, key-task, and relevant-task payloads, and added explicit diagnostics for adopted notification plans plus key-task/relevant-task selection on proactive updates.
- Tightened proactive notification wording so notification messages stay plain-text and spoken-style, explicitly avoiding markdown and list formatting in user-visible updates.

## 2026-04-08

- Added a standalone `examples/agora_conversational_ai` bridge that binds one live Agora Conversational AI agent to one Synapse session, exposes an OpenAI-compatible `/chat/completions` edge outside the main app, and reuses `conversation_appended` notification events to drive Agora `/speak` delivery for proactive updates only.
- Added a configurable frontend adapter and example-local React voice client under `examples/agora_conversational_ai`, so browser testing can start and stop Agora sample sessions through local normalized routes instead of binding the UI directly to an external sample-backend contract.
- Moved example auth and notification REST ownership fully to the external sample backend by storing `sample_session_id` in bridge bindings and proxying notification speech through a sample-backend speak route instead of using local auth-header env configuration.
- Collapsed `examples/agora_conversational_ai` into a single local backend using `agora-agent` plus local client-token generation, removed the separate sample-backend proxy model, and made `/frontend/session/start` / `/stop` own ConvoAI lifecycle directly inside this repo.

## 2026-04-12

- Switched `examples/agora_conversational_ai` to a bridge-first LLM path, reserving `bridge_session_id` before Agora activation and passing the public `/chat/completions` URL into the Agora SDK so live ConvoAI turns route through the bound local Synapse session instead of calling OpenAI directly from Agora.
- Reworked `examples/agora_conversational_ai` from an embedded-runtime example into an external bridge that creates and streams Synapse sessions through the main `8000` API server while keeping Agora lifecycle and the public custom-LLM callback on the separate `8010` bridge backend.

## 2026-04-13

- Renamed the public package, CLI, docs, env prefixes, and example bridge surface from `synopse` to `synapse`, and added a repo-root `synapse` bootstrap launcher plus a first-class Python CLI for setup, doctor, and local app startup.
- Split local bootstrap so `install.sh` now installs supported dev dependencies and repo packages, while `synapse setup` became an env-configuration wizard for the root `.env.local` with a non-interactive automation path.
- Added a separate headless gateway host plus first-party `src/synapse/gateways/` modules, promoted Agora ConvoAI into the new gateway module structure, and extended the CLI so gateway config can be prompted from `synapse setup` or `synapse gateway setup` and auto-started from `synapse dev` / `synapse start`.

## 2026-04-14

- Switched gateway host configuration to a shared `config/gateway.yaml` contract referenced by `SYNAPSE_GATEWAY_CONFIG_FILE`, renamed public gateway config naming from `modules` to `gateways`, and moved Agora ConvoAI ASR/TTS selection to YAML-backed managed or BYOK settings.
- Updated the Agora gateway prepare flow so frontend requests can override `agent_instructions`, `agent_greeting`, `agent_uid`, and `user_uid` per session while keeping the Synapse bridge-backed LLM path internal.
- Moved the live runtime env and gateway YAML out of the repo and into `~/.synapse/.env` plus `~/.synapse/config.yaml`, keeping repo files as setup templates only.
- Moved the main React/Vite frontend workspace from repo-root `frontend/` to `src/synapse/ui/`, while keeping `synapse frontend`, `synapse dev`, and `install.sh` wired to the new location.
- Moved the Agora example browser client from `examples/agora_conversational_ai/frontend/` to repo-root `exmaple-ui/` while keeping `src/synapse/ui/` as the main CLI-managed frontend workspace.
- Removed the CLI dependency on a tracked repo `.env.example` and moved the setup wizard to a code-defined env template while keeping `~/.synapse/.env` as the rendered config destination.
- Updated `install.sh` to create starter `~/.synapse/.env` and `~/.synapse/config.yaml` files during bootstrap without overwriting existing user config, leaving `synapse setup` for filling in real values afterward.
- Pinned Agora ConvoAI gateway setup to the `US` region, removed interactive prompts for token TTL and speak/request tuning, and changed the managed Minimax default voice to `English_magnetic_voiced_man`.
- Removed the legacy `examples/agora_conversational_ai` bridge package and its dedicated integration tests, leaving the first-party `src/synapse/gateways/agora_convoai/` gateway module plus repo-root `exmaple-ui/` as the supported Agora path.
- Added a first-class `synapse service` CLI for Ubuntu/systemd deployment from a repo checkout, installing one combined `synapse.service` unit that runs `synapse start` as the deploy user and keeps runtime config in `~/.synapse`.
