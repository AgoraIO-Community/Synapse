# V2 Overview

Synapse `v2` is a blackboard-centered dual-brain runtime.

For the unified open-source architecture overview, start with
[../../ARCHITECTURE.md](../../ARCHITECTURE.md).

The three core runtime actors are:

- `Communication Brain`
- `Execution Brain`
- `Shared Blackboard`

Core principle:

- Communication Brain owns user intent and task manipulation.
- Execution Brain owns sessionized execution.
- Blackboard is the only shared source of truth.

Key changes from the current prototype:

- no standalone `Message Interpreter`
- no action-bundle-centered runtime entrance
- stronger separation between communication and execution
- explicit execution lineage through tasks, sessions, and runs
- proactive notifications and interruptions as dedicated orchestration concerns

This overview is intentionally short. The root `ARCHITECTURE.md` explains the full stable architecture target, while the topic docs in this directory provide subsystem detail.

Use the topic docs in this directory for detail:

- [Communication Brain](./communication-brain.md)
- [Execution Brain](./execution-brain.md)
- [Blackboard](./blackboard.md)
- [Sessions and Runs](./api/sessions-and-runs.md)
- [Notifications and Interruptions](./notifications-and-interruptions.md)
- [Observability](./observability.md)
- [Executors](./executors.md)
- [Repository Structure](./repository-structure.md)
