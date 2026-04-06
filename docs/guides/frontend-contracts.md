# Frontend Contracts

The frontend should depend on stable protocol projections rather than ad hoc mirrored types.

Preferred direction:

- derive shared schema from protocol models
- consume stable task/session/run/summary projections
- avoid depending on low-level executor events
- use `GET /sessions/{session_id}` for durable task/session state reads
- treat `WS /sessions/{session_id}/stream` as a mixed event stream: `snapshot` events remain available for debugger/state views, while chat UIs should consume only `assistant_response_*` events plus request ack/reject transport events
- do not depend on communication-model tool-call details on the frontend stream; tool activity is internal

User-visible conversation history should contain only:

- user messages
- assistant replies
- emitted proactive messages
