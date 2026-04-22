# RFC 0004: Headless Gateway Host and CLI Gateway Setup

This RFC proposes a first-party gateway host for vendor-facing voice gateways.

It is a proposal document, not the current source of truth for runtime behavior.
When this RFC conflicts with stable docs under `docs/architecture/`, `docs/guides/`,
or current code, treat the stable docs and implemented behavior as authoritative.

## Summary

Synapse should support vendor-facing gateway modules without pushing vendor runtime
logic into the main API server.

This RFC proposes:

- a separate headless gateway host process
- first-party in-repo gateway modules under `src/synapse/gateways/`
- shared gateway base classes for transport, bindings, and runtime wiring
- interactive gateway configuration through `synapse setup` and
  `synapse gateway setup`

The first module is `agora-convoai`.

## Problem

The existing Agora bridge lived only as an example backend and mixed:

- vendor runtime ownership
- Synapse transport adaptation
- example-specific browser startup routes

That shape worked for a single example, but it did not establish a reusable
first-party gateway surface for additional vendors.

## Goals

- keep the main Synapse API vendor-blind
- make gateway modules addable by creating a folder plus classes
- keep frontend concerns out of the gateway host
- keep the current Synapse session HTTP and websocket transport intact in V1
- provide one CLI-managed configuration path for core runtime and gateway setup

## Non-Goals

- no third-party plugin SDK in V1
- no dynamic external gateway discovery
- no session-stream redesign in this RFC
- no browser UI inside the gateway host

## OpenClaw Lesson

The useful OpenClaw lesson is separation, not feature parity.

Core host responsibilities:

- lifecycle
- registration
- startup and shutdown
- shared transport surfaces

Module responsibilities:

- vendor config
- vendor runtime lifecycle
- vendor callback translation
- vendor-specific HTTP routes

Synapse copies that separation while staying much smaller in scope.

## Proposed Design

### Gateway Host

Add a dedicated host app under:

```text
src/synapse/gateway_host/
```

The host is headless:

- no frontend routes
- no static assets
- no browser-specific API contract

### First-Party Modules

Add:

```text
src/synapse/gateways/
├─ base/
└─ agora_convoai/
```

The first-party registry is explicit and in-repo only.

### Shared Base Classes

The shared framework should stay small:

- `BaseGatewayTransport`
  - wraps current Synapse HTTP and websocket APIs
  - normalizes current assistant streaming and notification watch flows
- `BaseGatewayRuntime`
  - vendor runtime lifecycle contract
- `BaseGatewayModule`
  - route registration and orchestration contract
- shared binding registry
  - maps vendor runtime sessions to Synapse sessions

### Route Model

Modules register namespaced routes on the host:

- `/gateway/agora-convoai/health`
- `/gateway/agora-convoai/config`
- `/gateway/agora-convoai/sessions/prepare`
- `/gateway/agora-convoai/sessions/activate`
- `/gateway/agora-convoai/sessions/stop`
- `/gateway/agora-convoai/chat/completions`

These are headless gateway routes. Any browser demo remains a client of these
routes and is not part of the host design.

## CLI Setup

Add:

- `synapse gateway setup`
- `synapse gateway run`

Also extend:

- `synapse setup`
  - asks whether to configure the gateway host
- `synapse dev`
  - starts the gateway host when gateway modules are enabled
- `synapse start`
  - starts the gateway host when gateway modules are enabled

Gateway config remains in the repo-root `.env.local`.

## Agora Module

`agora-convoai` is the first module and the reference implementation.

The module owns:

- Agora SDK session lifecycle
- Agora credential and provider config
- custom-LLM callback translation
- proactive speech delivery

The main Synapse API does not own Agora lifecycle or Agora auth.

## Adoption Notes

When this design is adopted in stable docs, update:

- README CLI and run instructions
- `docs/guides/agora-conversational-ai.md`
- `docs/architecture/repository-structure.md`
- `docs/memories.md`

