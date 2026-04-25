# Frontend Workbench

The main frontend under `src/synapse/ui/` renders the `Newbro` command-center
shell at `/`.

It keeps the concept-first visual language, but now uses real session snapshots
plus a focused voice runtime path.

## Current Structure

The current frontend stack is:

- React
- Vite 8
- TanStack Router
- Tailwind CSS v4
- `framer-motion` for shell motion
- Agora connector/browser voice integration for live transcript state

The root shell remains a fixed-height command center:

- left sidebar: `Home`, `Bros`, `Nodes`, `Settings`
- top bar: explicit `Start` / `Stop` / mic controls for voice
- left column: `Interaction memory`
- main column: Bro cards on `Home`, Bro management on `Bros`, node enrollment on
  `Nodes`
- left-menu pages are real routed paths, so refresh and direct open preserve the
  selected page instead of falling back to `Home`

## Data Sources

Current reads and live transport:

- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `WS /api/sessions/{session_id}/stream`
- `GET /api/sessions/{session_id}/personas`
- `GET /api/sessions/{session_id}/executor-nodes`
- `GET /api/connectors/agora-convoai/config`
- `POST /api/connectors/agora-convoai/sessions/prepare`
- `POST /api/connectors/agora-convoai/sessions/activate`
- `POST /api/connectors/agora-convoai/sessions/stop`

Current behavior:

- on load, the app resumes the shell session from `?sid=...` when present;
  otherwise it creates an idle shell session and fetches its snapshot
- once the shell has an active session, it writes that session id back to the
  URL as `sid` so the session can be reopened later from the same link
- if `sid` cannot be resumed, the app opens a fresh session, replaces the URL
  `sid`, and shows a non-blocking resume-failed warning
- the active session stream keeps `personas` and `executor_nodes` fresh while
  the shell stays open
- if persona data is empty or unavailable, the home view falls back to seeded
  sample bros
- Bro liveness is derived from `persona.executor_node_id` plus the matching
  executor node connection state
- the `Bros` page edits persona prompt, avatar, and node binding
- the `Nodes` page creates, edits, rotates, and deletes executor nodes and
  shows the token on create/rotate plus a persistent on-demand
  `Copy connect command` action on ordinary node cards
- sidebar navigation preserves the current `sid` query parameter across
  `Home`, `Bros`, `Nodes`, and `Settings`
- `Interaction memory` hydrates from Synapse durable conversation history when
  the page/session opens, then continues from Synapse user-message and
  assistant stream events instead of relying on local user echo or
  browser-local Agora transcript turns
- pressing `Start` prepares a connector-backed voice session against the
  current shell `session_id`, so the voice binding attaches to the existing
  Synapse session instead of swapping the shell to a new one
- when the browser does not pass an explicit `channel_name`, the connector uses
  that current shell `session_id` as the Agora channel and falls back to a
  unique generated channel only if no Synapse session id is available
- pressing `Stop` tears down only the live voice session and retains the last
  transcript until the next live session replaces it
- Bro Detail draft input uses a separate connector-managed Agora STT path: the
  page first prepares a fresh Agora-safe channel and browser RTC token, then
  starts the ASR bot after the browser joins RTC with the microphone disabled
- Bro Detail does not use the shell `session_id` as the Agora channel name;
  each page start receives a unique channel from the connector to avoid channel
  conflicts
- Bro Detail sends STT heartbeats every 15 seconds; explicit leave stops the ASR
  bot immediately, and missing heartbeats for more than 60 seconds stop it from
  the connector side

## Component Direction

The main reusable pieces are:

- `Sidebar`
- `TopVoiceBar`
- `ConversationMemory`
- `BrosPanel`
- `BrosPage`
- `NodesPage`
- `BroCard`
- `BroPortrait`
- `BroProgress`
- `useVoiceSession`

The visual language should stay close to the reference shell:

- warm off-white surfaces
- soft rounded geometry
- restrained iconography
- subtle motion instead of dashboard-heavy chrome

## Constraints

- Do not change backend or protocol contracts for cosmetic reasons.
- Keep the transport/runtime separation intact: the left-pane interaction
  memory comes from Synapse conversation state, while the voice connector owns
  RTC/RTM/session lifecycle and browser-local microphone/media behavior.
- Treat `src/synapse/ui/` as the only active frontend.
- Do not reintroduce the old chat/workbench root experience unless a later task
  explicitly broadens scope.
