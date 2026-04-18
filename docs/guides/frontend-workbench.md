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

- user message history
- assistant message history
- streaming assistant output
- lightweight task event cards attached to the conversation context
- message composer
- a compact auxiliary voice accessory backed by the Agora gateway

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
- `GET /gateway/agora-convoai/config`
- `POST /gateway/agora-convoai/sessions/prepare`
- `POST /gateway/agora-convoai/sessions/activate`
- `POST /gateway/agora-convoai/sessions/stop`

State ownership:

- TanStack Query owns the durable read models:
  - session creation result
  - session snapshot
  - conversation snapshot
- websocket events own live updates and patch the query-backed state in place
- diagnostics timeline remains a polling-based debug feed

The websocket remains the primary transport for user message submission and task
control commands.

By default, the browser client talks to those routes on the current origin so
local Vite proxying and same-origin backend hosting keep working. Separate UI
deployments can set `VITE_API_BASE_URL` to a public backend base URL instead,
and that URL must support both HTTPS requests and secure websocket upgrades.
Voice gateway calls may independently use `VITE_GATEWAY_BASE_URL`; if unset,
they also fall back to same-origin `/gateway/...` requests. This keeps the main
workbench session transport on the main Synapse API while allowing the Agora
gateway host to sit on a different public origin.
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
- keep voice mode explicitly auxiliary unless the product contract is revised
