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

- `POST /sessions`
- `GET /sessions/{session_id}`
- `WS /sessions/{session_id}/stream`
- `GET /sessions/{session_id}/personas`
- `GET /sessions/{session_id}/executor-nodes`
- `GET /connectors/agora-convoai/config`
- `POST /connectors/agora-convoai/sessions/prepare`
- `POST /connectors/agora-convoai/sessions/activate`
- `POST /connectors/agora-convoai/sessions/stop`

Current behavior:

- on load, the app creates an idle shell session and fetches its snapshot
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
- `Interaction memory` remains a browser-local live transcript surface driven by
  the Agora toolkit
- pressing `Start` creates a connector-backed voice session and rebinds the
  whole shell to the returned `synapse_session_id`
- pressing `Stop` tears down the live voice session, restores the idle shell
  session, and retains the last transcript until the next live session replaces
  it

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
- Keep the transport/runtime separation intact: voice transcript stays a
  browser-local feed while shell state comes from Synapse projections.
- Keep `example-ui/` separate from the main frontend.
- Do not reintroduce the old chat/workbench root experience unless a later task
  explicitly broadens scope.
