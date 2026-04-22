# Frontend Workbench

The main frontend under `src/synapse/ui/` currently renders a `Newbro`
command-center shell at `/`. It keeps the JSX-inspired visual layout, but it is
no longer static: the shell now owns a focused live voice-transcript path.

## Current Structure

The current frontend stack is:

- React
- Vite 8
- TanStack Router
- Tailwind CSS v4
- shadcn-style primitives where helpful
- `framer-motion` for the shell motion
- Agora gateway/browser voice integration for live transcript state

The root page is organized as a fixed-height command-center layout:

- left sidebar: `Newbro` navigation and operator card
- top bar: voice status summary plus explicit `Start` / `Stop` / mic controls
- left content column: `Interaction memory` transcript panel
- main content column: `Bro` cards with press-and-hold talk state

The whole page stays within the viewport and the center content area owns the
main scroll region.

## UX Intent

The current root route is still visual-first, but `Interaction memory` now has
real behavior behind it.

Its job is to present the JSX-inspired concept faithfully:

- keep the literal sample copy and labels such as `Newbro`, `Bros`, and
  `Plutoless`
- keep the sidebar and overall shell close to the concept layout
- keep Bro-card hold state local and presentational
- let the top bar explicitly start and stop a real voice session
- use the left panel as live transcript memory rather than placeholder bubbles
- show a populated shell even when no runtime data is available

## Data Sources

The root shell now uses two runtime sources:

Current reads:

- `POST /sessions`
- `GET /sessions/{session_id}`
<<<<<<< Updated upstream
- `GET /sessions/{session_id}/conversation`
- `GET /sessions/{session_id}/diagnostics/timeline`
- `WS /sessions/{session_id}/stream`
- `GET /connectors/agora-convoai/config`
- `POST /connectors/agora-convoai/sessions/prepare`
- `POST /connectors/agora-convoai/sessions/activate`
- `POST /connectors/agora-convoai/sessions/stop`
=======
- `GET /gateway/agora-convoai/config`
- `POST /gateway/agora-convoai/sessions/prepare`
- `POST /gateway/agora-convoai/sessions/activate`
- `POST /gateway/agora-convoai/sessions/stop`
>>>>>>> Stashed changes

Current behavior:

- on load, the app creates an idle shell session and reads `personas`
- if personas exist, they are mapped into `Bro` cards
- if persona data is empty or unavailable, the app falls back to seeded sample
  cards from the JSX concept
- pressing `Start` creates a gateway-backed voice session, initializes the
  Agora browser stack, and rebinds the shell to the returned
  `synapse_session_id`
- `Interaction memory` is populated from browser-local live transcript turns
  emitted by the Agora toolkit
- pressing `Stop` tears down the live voice session, restores the idle shell
  session, and retains the last transcript in the memory panel until the next
  live session replaces it
- the root shell still does not expose the older websocket conversation shell or
  the previous right-side workbench/debug surfaces

## Component Direction

The root page should stay componentized rather than returning to a monolithic
page component.

<<<<<<< Updated upstream
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
=======
The main reusable pieces are:

- `Sidebar`
- `TopVoiceBar`
- `ConversationMemory`
- `BrosPanel`
- `BroCard`
- `BroPortrait`
- `BroProgress`
- `useVoiceSession`
>>>>>>> Stashed changes

The visual language should stay close to the reference JSX:

- warm off-white surfaces
- soft rounded geometry
- restrained iconography
- subtle motion instead of dashboard-heavy chrome

Behavior-level expectations:

- `Interaction memory` is the live voice transcript surface
- transcript history should be scrollable and retained after stop
- top-bar controls own real session start/stop/mute
- Bro cards may react visually to hold state, but that hold state must not be
  treated as the transport/session lifecycle trigger

## Constraints

- Do not change backend or protocol contracts for cosmetic reasons.
- Keep the transport/runtime separation intact: voice transcript stays a
  browser-local feed while shell persona/session reads come from Synapse
  projections.
- Keep `example-ui/` separate from the main frontend.
- Do not casually reintroduce the old chat/workbench runtime into `/`; treat the
  current shell as a focused voice-transcript surface unless a later task
  explicitly broadens it.
