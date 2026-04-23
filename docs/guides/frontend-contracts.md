# Frontend Contracts

The frontend should depend on stable protocol projections rather than ad hoc mirrored types.

Preferred direction:

- derive shared schema from protocol models
- consume stable task/session/run/summary projections
- avoid depending on low-level executor events
- use `GET /api/sessions/{session_id}` for durable task/session state reads
  including `personas`, `executor_capabilities`, and `executor_nodes`
- use `GET /api/sessions/{session_id}/conversation` for durable conversation history reads
- use `GET /api/sessions/{session_id}/diagnostics/timeline` for debugger-oriented
  inspection data
- use `GET /api/sessions/{session_id}/executor-nodes` plus the related
  create/update/rotate/delete routes for operator-managed executor-node CRUD
- treat `WS /api/sessions/{session_id}/stream` as the live transport for:
  - `snapshot` for durable task/execution state refresh
  - `assistant_response_*` plus request ack/reject events for chat transport
- do not depend on communication-model tool-call details on the frontend
  websocket; tool activity is internal and debug inspection is log-backed
- default to same-origin transport locally through the main Synapse service,
  but allow a separately deployed UI to target a public main-service base URL
  through `VITE_API_BASE_URL`
- when `VITE_API_BASE_URL` is used, that public backend origin must terminate
  on the main Synapse service rather than the connector host and must preserve secure
  websocket upgrades for `WS /api/sessions/{session_id}/stream`
- allow Agora voice-mode browser calls to use `VITE_CONNECTOR_BASE_URL` for the
  separate connector host; if unset, keep using same-origin `/api/connectors/...`
  requests from the main Synapse service
- the whole frontend shell should follow exactly one active session at a time
- the shell URL may carry that active session as `?sid=<session_id>`, and the
  frontend should attempt to resume it on load before creating a fresh session
- when a fresh session is created or resume falls back, the frontend should
  replace the current URL `sid` with the active session id
- the frontend may hydrate user-visible conversation history from
  `GET /api/sessions/{session_id}/conversation` when a session opens, but the
  live pane should then continue from Synapse user-message and assistant stream
  events instead of repeatedly refetching, locally echoing user turns, or
  using browser transcript
- voice mode attaches its connector binding to that already-active shell
  session instead of switching the shell to a connector-created session
- Bro liveness is derived in the frontend from `persona.executor_node_id`
  plus the matching `executor_nodes[*].connection_status`
- voice mode may also exist without an active session binding before the user
  presses `Start`
- left-sidebar route navigation should preserve the current `sid`
- when the frontend does not supply an explicit connector `channel_name`, the
  connector should derive it from the active `synapse_session_id` and fall back
  to a unique generated channel only when no Synapse session id is available

User-visible conversation history should contain only:

- user messages
- assistant replies
- emitted proactive messages

Voice transcript from the Agora toolkit is not part of that conversation
projection. It remains a separate browser-local voice-toolkit feed, while the
left-pane interaction memory and the rest of the workbench come from Synapse
session state.
