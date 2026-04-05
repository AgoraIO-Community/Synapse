# V2 Overview

Synopse `v2` is a blackboard-centered dual-brain runtime.

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

Use the topic docs in this directory for detail:

- [Communication Brain](./communication-brain.md)
- [Execution Brain](./execution-brain.md)
- [Blackboard](./blackboard.md)
- [Sessions and Runs](./sessions-and-runs.md)
- [Notifications and Interruptions](./notifications-and-interruptions.md)
- [Executors](./executors.md)
- [Repository Structure](./repository-structure.md)
