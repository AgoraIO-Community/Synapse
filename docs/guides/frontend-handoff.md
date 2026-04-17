# Frontend Handoff

This document is the handoff note for continuing the main frontend redesign in
`src/synapse/ui/`.

It is intended for the next agent or engineer picking up the work. It reflects
the current agreed product direction, the current technical state, and the next
implementation priorities.

## Current Branch and Recent Commits

Active branch:

- `codex/refine-onboarding`

Recent frontend-related commits:

- `64e9eab` Rework frontend into chat-first workbench
- `dc8d32f` Polish workbench UI presentation
- `b808264` Refine conversation pane visuals

There are additional uncommitted frontend changes in the current worktree. The
next agent should inspect `git status` before continuing.

## Agreed Product Direction

The main frontend is a chat-first AI workbench.

The page structure is:

- left: `Conversation`
- right: `Workbench`

The left pane is the primary experience and should dominate attention.

The right pane is secondary and exists to show:

- active tasks
- selected task detail
- secondary debug surfaces

### Left Pane Requirements

The left pane is the current priority. The user explicitly wants the left side
finished before continuing work on the right side.

The left pane should follow these UX principles:

- compress the header aggressively
- remove clutter from the top of the page
- maximize vertical space for messages and the composer
- make the prompt input the primary anchor at the bottom
- make task status feel like in-thread suggestions or work-log bubbles
- hide empty-state content completely once there is any conversation content
- keep the overall look modern, minimal, and visually striking

The user specifically wants these references reflected in the design:

- `AI Elements / prompt-input`
- `AI Elements / suggestion`
- the previously provided `tailwind-plus-protocol/protocol-ts` theme direction

### Empty State

When there are no conversation messages:

- empty-state content can float in the middle
- starter prompts should appear there
- the empty state should feel like a polished AI welcome state

Once there is any conversation content:

- the empty state must disappear completely
- no duplicate onboarding hints should remain
- the layout should become a normal conversation layout

### Fonts

The user explicitly requested:

- headings: `Noto Sans SC` and `Noto Sans`
- body copy: `Geist`

That direction is already in progress and should be preserved.

## Agreed Stack Direction

The frontend should stay on:

- Vite 8
- TanStack Router
- TanStack Query
- Tailwind CSS v4
- shadcn-style primitives

Important stack decision:

- do **not** continue trying to make TanStack Start the active runtime layer
- `@tanstack/react-start` may still be present in dependencies, but it is not
  the chosen runtime direction

### Tailwind / shadcn Rule

This is an explicit user instruction:

- use Tailwind CSS + shadcn conventions
- do **not** keep building the page through a large custom CSS file
- existing CSS-driven implementations should be removed or minimized

Practical interpretation for the next agent:

- move visual implementation into Tailwind utility classes and shadcn component
  composition
- keep `app.css` only for the smallest possible global concerns if absolutely
  necessary
- do not reintroduce semantic CSS blocks for page sections unless there is no
  reasonable utility-first alternative

## Current Technical State

The current frontend already uses:

- React
- Vite 8
- TanStack Router
- TanStack Query
- shadcn-style component wrappers

The current app files of interest:

- `src/synapse/ui/src/App.tsx`
- `src/synapse/ui/src/main.tsx`
- `src/synapse/ui/src/router.tsx`
- `src/synapse/ui/src/routes/__root.tsx`
- `src/synapse/ui/src/lib/session-client.ts`
- `src/synapse/ui/src/components/ui/*`
- `src/synapse/ui/src/styles/app.css`

Current state management split:

- TanStack Query:
  - session creation
  - session snapshot
  - conversation snapshot
- websocket:
  - live snapshot updates
  - assistant response streaming
  - command/message acknowledgement
- diagnostics timeline:
  - polling-based debug feed

Current tests:

- `src/synapse/ui/src/__tests__/App.test.tsx`

Current verified commands:

```bash
cd src/synapse/ui
bun run test
bun run build
```

These are currently expected to pass.

## Current Known Gaps

The frontend has improved, but it is not done.

The major remaining issues are:

- the left pane still has too much custom CSS involvement
- the left pane does not yet fully feel like a polished AI chat product
- the prompt input is better than before, but still not close enough to the
  `prompt-input` reference
- the in-thread task event presentation still needs more refinement
- the right pane has not yet received the same level of visual cleanup as the
  left pane

Also note:

- browser-based validation should continue to be done with `$agent-browser`
- there may be other local apps running on `5173`; the agent should verify which
  local port is actually serving Synapse before trusting the page content

## Required Workflow for the Next Agent

The next agent should continue in this order:

1. Finish the left pane completely
2. Convert the left pane to true Tailwind/shadcn implementation style
3. Keep validating with `$agent-browser` after each visible change
4. Commit progress in small, meaningful steps
5. Only after the left pane feels finished, move on to the right pane

### Left Pane Implementation Priorities

Recommended order:

1. remove or drastically shrink remaining top clutter
2. make the prompt input feel like a true AI composer
3. improve message bubble hierarchy and spacing
4. make task event cards feel like `suggestion` / work-log bubbles
5. ensure conversation mode and empty-state mode feel like two distinct,
   intentional states

### Right Pane Work After Left Is Done

Once the left pane is strong enough:

- refine queue/task cards
- refine detail hierarchy
- reduce dashboard-like emptiness
- keep debug secondary

## Agent-Browser Expectations

The user explicitly asked that the implementation be checked frequently with
`$agent-browser`.

Do not rely only on code inspection for visual work.

Use it to validate:

- empty-state appearance
- content-state appearance
- mobile layout
- task-created / task-completed state
- prompt input spacing and behavior

## Constraints

Do not change:

- backend API contracts
- websocket message shapes
- core runtime behavior for cosmetic reasons

Prefer:

- presentation-layer refactors
- query/cache/view-model cleanup
- component extraction

Avoid:

- large CSS-only rewrites
- reintroducing debugger-first layout choices
- broad protocol or backend changes while finishing the left pane
