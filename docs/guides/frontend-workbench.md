# Frontend Workbench

The main frontend under `src/synapse/ui/` is the chat-first local workbench for
Synapse. It is not a generic marketing UI and it is not the Agora example
client. Its job is to expose the runtime in a form that is useful for both
normal interaction and developer observation.

## Current Structure

The current frontend stack is:

- React
- Vite 8
- TanStack Router
- TanStack Query
- shadcn-style component primitives

The page is organized as a fixed-height dual-pane layout:

- left: `Conversation`
- right: `Workbench`

The whole page should not vertically scroll. Each pane owns its own scroll
region.

## UX Intent

The frontend is now chat-first.

The left pane is the primary interaction surface:

- a left-edge attached vertical `Text` / `Voice` mode rail on desktop
- text mode:
  - user message history
  - assistant message history
  - streaming assistant output
  - lightweight task event cards attached to the conversation context
  - message composer
- voice mode:
  - live Agora transcript feed
  - voice session status
  - explicit `Start` / `Stop` voice-session control
  - explicit microphone `Mute` / `Unmute` control
  - no text composer

The right pane is the execution workbench:

- active task queue
- selected task detail
- task control actions
- secondary `Debug` tab for lower-level inspection

Important task outcomes should be visible in the conversation without forcing
the user to read raw diagnostics. Lower-level runtime detail still exists, but
it should stay behind the workbench detail and debug surfaces.

## Data Sources

The frontend should continue to use stable runtime projections rather than
ad hoc mirrored debug structures.

Primary reads:

- `POST /sessions`
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/conversation`
- `GET /sessions/{session_id}/diagnostics/timeline`
- `WS /sessions/{session_id}/stream`
- `GET /connectors/agora-convoai/config`
- `POST /connectors/agora-convoai/sessions/prepare`
- `POST /connectors/agora-convoai/sessions/activate`
- `POST /connectors/agora-convoai/sessions/stop`

State ownership:

- TanStack Query owns the durable read models:
  - session snapshot
  - conversation snapshot
- websocket events own live updates and patch the query-backed state in place
- diagnostics timeline remains a polling-based debug feed

The websocket remains the primary transport for user message submission and task
control commands for the currently active mode session.

Mode rules:

- the app boots in `Voice`
- switching modes abandons the current frontend-owned session for that mode
- switching to `Text` creates a fresh `POST /sessions` session
- switching to `Voice` enters an idle voice-mode shell first
- pressing `Start` in voice mode creates a fresh connector-backed voice session
  and then rebinds the whole shell to the returned `synapse_session_id`
- switching away from `Voice` stops the active Agora session through
  `POST /connectors/agora-convoai/sessions/stop`

By default, the browser client talks to those routes on the current origin so
local Vite proxying and same-origin backend hosting keep working. Separate UI
deployments can set `VITE_API_BASE_URL` to a public backend base URL instead,
and that URL must support both HTTPS requests and secure websocket upgrades.
Voice connector calls may independently use `VITE_CONNECTOR_BASE_URL`; if unset,
they also fall back to same-origin `/connectors/...` requests. This keeps the main
workbench session transport on the main Synapse API while allowing the Agora
connector host to sit on a different public origin.
When the backend sits behind an HTTPS reverse proxy such as Nginx, the public
origin must forward `/sessions` to the main Synapse API and preserve websocket
upgrade handling for the session stream route.

## Component and Styling Direction

The component vocabulary should stay aligned with shadcn-style primitives and
the visual language should feel intentional and modern rather than generic
dashboard boilerplate.

Preferred interaction influences:

- AI chat surfaces
- queue/task style workbench panels
- lightweight in-thread step and task activity

The frontend should prefer reusable UI primitives over one large page-local CSS
system. However, presentation reliability is more important than blindly
following a framework pattern. If a styling toolchain feature is unstable in the
current app, prefer a simpler implementation that keeps the UI shippable.

## Current Constraints

- The frontend is intentionally separate from the FastAPI backend and should not
  absorb backend runtime behavior into the browser app.
- The main workbench should stay distinct from `exmaple-ui/`, which is still a
  separate example client surface.
- Runtime-facing behavior should keep working even when the visual system is
  being iterated.

In practice, that means:

- avoid changing session and websocket protocol contracts for cosmetic reasons
- avoid making debug-only backend detail part of the primary chat UX
- keep the workbench useful even when no tasks exist
- keep text and voice mode switching explicit and visible in the left pane
