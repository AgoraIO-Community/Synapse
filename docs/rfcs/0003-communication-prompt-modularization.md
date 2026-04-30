# RFC 0003: Communication Prompt Modularization

This RFC proposes a prompt-module structure for the Communication Brain.

It is a proposal document, not the current source of truth for runtime behavior.
When this RFC conflicts with stable docs under `docs/architecture/` or current
code, treat the stable docs and implemented behavior as authoritative until this
proposal is fully adopted.

## Summary

Synapse currently assembles Communication Brain prompts inline inside
`src/synapse/communication/models/openai.py`.

That file currently mixes:

- prompt text
- scenario-specific message assembly
- runtime context serialization
- provider transport invocation

This RFC proposes moving prompt assembly into a dedicated
`newbro.communication.prompts` package while preserving current behavior.

The immediate target is the two currently implemented prompt paths:

- normal reply generation
- proactive notification rendering

## Problem

The current shape has a few concrete issues:

- prompt text is coupled to the OpenAI transport adapter
- prompt tuning requires editing the same file that owns provider invocation
- prompt assembly logic is not reusable or independently testable
- tests already depend on prompt ordering and key fragments, but that interface
  is still implicit

This is manageable while there is only one communication model implementation,
but it becomes harder to maintain as prompt tuning grows.

## Goals

- introduce a dedicated `newbro.communication.prompts` package
- separate prompt assembly from `OpenAICommunicationModel`
- preserve current behavior and message ordering where practical
- keep runtime context as a structured payload instead of mixing it into prose
- make prompt-builder tests the primary interface for prompt-shape regression

## Non-Goals

- no prompt templating engine
- no provider/plugin prompt contribution system
- no new prompt entrypoints for interruption, task-summary, or task-query until
  those paths have real callers
- no change to tool schemas, blackboard semantics, or notification policy
- no change to runtime enforcement boundaries in `communication/policies/` or
  tool implementations

## Current State

Current prompt assembly lives in:

- `src/synapse/communication/models/openai.py`

Current runtime policy still belongs in:

- `src/synapse/communication/policies/tool_usage_policy.py`
- `src/synapse/communication/policies/reply_style.py`

The broader communication package boundary already anticipates a prompt package
in the long-form V2 proposal:

- `docs/rfcs/0001-design-v2.md`

## Proposed Design

### Package Layout

Add:

```text
src/synapse/communication/prompts/
├─ __init__.py
├─ base/
│  ├─ __init__.py
│  ├─ identity.py
│  ├─ reply_style.py
│  ├─ guardrails.py
│  └─ tool_policy.py
├─ tasks/
│  ├─ __init__.py
│  ├─ normal_reply.py
│  └─ proactive_notification.py
├─ examples/
│  ├─ __init__.py
│  ├─ tool_usage.py
│  └─ notification_style.py
├─ runtime_context.py
└─ builders.py
```

### Prompt Section Responsibilities

#### Base sections

- `identity`
  - defines the Communication Brain role
  - reminds the model that replayed recent history is authoritative
- `reply_style`
  - short natural spoken replies
  - action-commitment wording over system acknowledgements
- `guardrails`
  - do not leak internal runtime vocabulary unless asked
  - do not emit mechanical success receipts
- `tool_policy`
  - model-facing tool selection guidance
  - includes current mock-only vs real-executor branch logic

#### Task sections

- `normal_reply`
  - latest user message
  - available tools
  - use tools only when needed, then produce one natural final reply
- `proactive_notification`
  - generate one proactive update from selected facts
  - do not use tools
  - do not expose notification/runtime internals

#### Supporting sections

- `examples/tool_usage.py`
  - current few-shot examples for normal replies
  - keeps mock-only vs real-executor branches
- `examples/notification_style.py`
  - current wording examples for proactive notifications
- `runtime_context.py`
  - serializes runtime context JSON
  - serializes selected notification facts JSON

### Builder Interfaces

`builders.py` should provide:

- `build_reply_messages(user_text, context)`
- `build_notification_messages(context, candidates)`

These builders should return the final OpenAI-compatible message list.

### Message Shape

Normal reply message order should remain:

1. identity
2. tool policy
3. reply style
4. guardrails
5. normal-reply task block
6. tool-usage examples
7. runtime context JSON
8. replayed recent history

Notification message order should remain:

1. identity
2. reply style
3. guardrails
4. proactive-notification task block
5. notification-style examples
6. runtime context JSON
7. selected notification facts JSON
8. replayed recent history

Keeping the message order stable reduces behavior drift and keeps the current
tests easy to migrate.

### Model Boundary

`OpenAICommunicationModel` should become a thin transport adapter that:

- asks builders for messages
- runs the provider tool-calling loop
- maps tool results into `CommunicationModelResult`

It should not remain the owner of prompt prose or message-list assembly.

### Policy Boundary

Prompt guidance is advisory.

Hard behavior enforcement must remain in runtime code such as:

- communication tool implementations
- task validation
- executor capability checks
- `communication/policies/*`

This avoids creating two conflicting sources of truth.

### Stable vs Dynamic Prompt Content

The proposal intentionally distinguishes:

- stable prompt text
  - identity
  - style
  - guardrails
  - examples
- dynamic payloads
  - runtime context JSON
  - selected notification facts
  - replayed conversation history

This split should stay explicit even if Synapse does not yet implement a formal
prompt-cache boundary.

## Testing Strategy

Add prompt-builder unit tests that assert:

- required sections are present
- normal reply and notification message ordering is stable
- runtime context payload shape stays stable
- mock-only and real-executor wording branches remain correct

Update existing `OpenAICommunicationModel` tests so they validate builder-driven
message output rather than private inline helper functions.

Keep existing communication and notification integration tests passing to verify
that behavior remains unchanged.

## Alternatives Considered

### Keep prompts inline in `openai.py`

Rejected because it keeps prompt maintenance coupled to provider transport code.

### Introduce a heavy templating system now

Rejected because current prompts are small enough for Python constants and
simple functions. A template engine would add complexity without clear current
benefit.

### Build future unused prompt modules up front

Rejected for now. `task_summary`, `task_query`, and `interruption` should only
be added once there are real independent prompt entrypoints for them.

## Adoption Notes

When this proposal is implemented and treated as current design, stable docs may
be updated to mention the concrete prompt-package structure under
`newbro.communication.prompts`.

Until then, this RFC is design intent only.
