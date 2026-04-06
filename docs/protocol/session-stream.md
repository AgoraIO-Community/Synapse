# Session Stream

The session websocket is the mixed live transport for a session:

- path: `WS /sessions/{session_id}/stream`
- direction: bidirectional

Client actions:

- `send_message`
  - fields:
    - `request_id`
    - `text`
- `send_command`
  - fields:
    - `request_id`
    - `command_type`
    - `task_id` or `reference`
    - optional `payload`
    - optional `reason`

Server events:

- `snapshot`
  - carries the durable `SessionSnapshot`
  - preserves the original debugger-oriented snapshot feed
- `action_accepted`
  - acknowledges a valid client action by `request_id`
- `action_rejected`
  - rejects a client action with stable `error_code` and `message`
- `assistant_response_started`
- `assistant_response_delta`
- `assistant_response_completed`
- `assistant_response_failed`

Assistant stream rules:

- assistant events are correlated by the originating `request_id`
- assistant deltas are transient and are not persisted in conversation history
- only the final assistant reply is durable in `conversation_history`
- communication-model tool calls remain internal and are not exposed on the websocket
