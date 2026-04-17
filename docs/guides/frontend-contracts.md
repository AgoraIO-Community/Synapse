# Frontend Contracts

The frontend should depend on stable protocol projections rather than ad hoc mirrored types.

Preferred direction:

- derive shared schema from protocol models
- consume stable task/session/run/summary projections
- avoid depending on low-level executor events
- use `GET /sessions/{session_id}` for durable task/session state reads
- use `GET /sessions/{session_id}/conversation` for durable conversation history reads
- use `GET /sessions/{session_id}/diagnostics/timeline` for debugger-oriented
  inspection data
- treat `WS /sessions/{session_id}/stream` as the live transport for:
  - `snapshot` for durable task/execution state refresh
  - `assistant_response_*` plus request ack/reject events for chat transport
- do not depend on communication-model tool-call details on the frontend
  websocket; tool activity is internal and debug inspection is log-backed
- default to same-origin transport locally, but allow a separately deployed UI
  to target a public backend base URL through `VITE_API_BASE_URL`

User-visible conversation history should contain only:

- user messages
- assistant replies
- emitted proactive messages
