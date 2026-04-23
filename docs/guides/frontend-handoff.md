# Frontend Handoff

This document records the current handoff state for `src/synapse/ui/` after the
root shell was rebuilt to match the provided JSX layout and then wired to a
real voice transcript flow.

## Current Product State

The root route now renders a `Newbro` command-center shell instead of the prior
live chat/workbench runtime.

Current visible structure:

- left sidebar with literal sample branding
- top voice summary bar with real session controls
- `Interaction memory` transcript panel
- `Bro` card grid with hold-to-talk visual state

The copy is intentionally literal to the reference for this pass.

## Runtime Relationship

The shell is now voice-aware, but still narrower than the previous workbench.

Current behavior:

- the app resumes the shell session from `?sid=...` on load when available,
  otherwise it creates a fresh shell session
- it writes the active session id back to the URL as `sid`
- if that `sid` cannot be resumed, it opens a fresh session, replaces the URL,
  and shows a non-blocking warning
- it fetches that session snapshot for personas
- if `personas` exist, it maps them into `Bro` cards
- if not, it renders the seeded sample cards
- pressing `Start` prepares and activates a gateway-backed voice session
- the connector attaches that voice session to the existing shell
  `synapse_session_id`
- browser-local Agora transcript turns stream into `Interaction memory`
- pressing `Stop` tears the voice session down without changing the shell
- the stopped transcript remains visible until the next live session replaces it
- left-sidebar route navigation preserves the active `sid`

The current root page does **not** expose:

- the text composer
- the previous workbench/task detail panes
- the websocket-backed conversation shell
- right-side debug or task-control surfaces

## Important Files

- `src/synapse/ui/src/App.tsx`
- `src/synapse/ui/src/components/newbro/*`
- `src/synapse/ui/src/__tests__/App.test.tsx`
- `src/synapse/ui/src/routes/__root.tsx`

## Verified Commands

```bash
cd src/synapse/ui
npm test
npm run build
```

These should pass from the current state.

## Next Likely Directions

If work continues on this shell, choose one direction explicitly before
implementing:

1. polish the current voice-transcript shell further
2. add more Synapse runtime surfaces into this layout deliberately
3. expose the older runtime shell on a secondary route

Do not mix those directions casually; the UI contract stays cleaner if one is
chosen first.

## Constraints

- Keep backend and protocol contracts unchanged unless the task explicitly
  requires runtime changes.
- Preserve the componentized structure under `src/components/newbro/`.
- Keep voice transcript as a browser-local feed; do not redefine it as durable
  conversation history without an explicit product decision.
