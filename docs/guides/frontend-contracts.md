# Frontend Contracts

The frontend should depend on stable protocol projections rather than ad hoc mirrored types.

Preferred direction:

- derive shared schema from protocol models
- consume stable task/session/run/summary projections
- avoid depending on low-level executor events
- use `GET /sessions/{session_id}` for durable task/session state reads
  including `personas`, `executor_capabilities`, and `executor_nodes`
- use `GET /sessions/{session_id}/conversation` for durable conversation history reads
- use `GET /sessions/{session_id}/diagnostics/timeline` for debugger-oriented
  inspection data
- use `GET /sessions/{session_id}/executor-nodes` plus the related
  create/update/rotate/delete routes for operator-managed executor-node CRUD
- treat `WS /sessions/{session_id}/stream` as the live transport for:
  - `snapshot` for durable task/execution state refresh
  - `assistant_response_*` plus request ack/reject events for chat transport
- do not depend on communication-model tool-call details on the frontend
  websocket; tool activity is internal and debug inspection is log-backed
- default to same-origin transport locally through the main Synapse service,
  but allow a separately deployed UI to target a public main-service base URL
  through `VITE_API_BASE_URL`
- when `VITE_API_BASE_URL` is used, that public backend origin must terminate
  on the main Synapse service rather than the connector host and must preserve secure
  websocket upgrades for `WS /sessions/{session_id}/stream`
- allow Agora voice-mode browser calls to use `VITE_CONNECTOR_BASE_URL` for the
  separate connector host; if unset, keep using same-origin `/connectors/...`
  requests from the main Synapse service
- the whole frontend shell should follow exactly one active session at a time
- in voice mode, that active session is the connector-returned
  `synapse_session_id`
- Bro liveness is derived in the frontend from `persona.executor_node_id`
  plus the matching `executor_nodes[*].connection_status`
- voice mode may also exist without an active session binding before the user
  presses `Start`
- switching modes abandons the previous frontend-owned session and creates a
  fresh session for the selected mode

User-visible conversation history should contain only:

- user messages
- assistant replies
- emitted proactive messages

Voice transcript from the Agora toolkit is not part of that durable conversation
history projection. It remains a separate browser-local feed for voice mode
while the workbench and task state come from the active Synapse session
websocket.
