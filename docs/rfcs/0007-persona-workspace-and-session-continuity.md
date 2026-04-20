# RFC 0007: Persona Workspace and Session Continuity

## Summary

Synapse should stop treating workspace placement, persona identity, and executor-native
session continuity as the same concern.

This RFC defines four separate concepts:

- `Persona`: who is assigned to do the work
- `Task`: the durable user-visible work item
- `WorkspaceContext`: the filesystem/project context where files are created and reused
- `ExecutionSession`: the executor-side continuity lineage for one task

The default policy becomes:

- a new unrelated task gets a new `WorkspaceContext`
- resuming the same task reuses the same `WorkspaceContext` and the same `ExecutionSession`
- creating a follow-up task for the same project reuses the same `WorkspaceContext` but starts a new `ExecutionSession` by default

This preserves project continuity without forcing users to create a new persona for every
unrelated task, and without leaking executor memory or files across unrelated work.

## Motivation

The current design space has three tempting but flawed anchors:

1. **Workspace bound to persona**

   This makes follow-up work convenient, but it means one persona accumulates unrelated files
   over time. If Mochi first builds a red-black-tree demo and later draws a cat, the second
   task starts in a directory polluted by the first.

2. **Workspace bound to task**

   This gives perfect isolation, but it breaks common follow-up flows. If the user says "add
   tests to the red-black-tree project," a brand-new task gets a brand-new directory and loses
   access to the existing files unless special logic is added.

3. **Workspace bound to executor session**

   This is the wrong level of abstraction. Executor sessions are executor-specific continuity
   objects. They can be recreated, swapped across executor families, or intentionally reset.
   A project workspace should survive those events.

The real requirement is not "bind workspace to persona" or "bind workspace to session." The
real requirement is:

- isolate unrelated work
- preserve project files for related work
- allow the same persona to work on multiple unrelated projects over time
- keep executor-native memory continuity optional and task-scoped

## Design Goals

- **Isolation by default**: unrelated tasks should not share files or hidden thread state.
- **Project continuity when intended**: explicit follow-up work should reuse the prior project
  directory.
- **Persona reuse**: the same persona should be able to work on unrelated tasks without
  forcing the user to create a new persona.
- **Executor independence**: workspace identity must not depend on ACPX, Codex, or any
  executor-specific session handle.
- **Clear semantics**: filesystem continuity and executor-memory continuity must be modeled
  separately.
- **Incremental rollout**: the design should allow a small first implementation and a cleaner
  long-term model.

## Non-Goals

- solving full multi-project IDE semantics inside the task model
- adding per-persona permanent project homes
- making follow-up detection fully automatic from natural language alone
- guaranteeing cross-executor conversational continuity for new tasks

## Core Model

### Persona

`Persona` is the assignee and prompt/style identity.

It may influence:

- base prompt
- user-facing naming
- scheduling and availability

It must not define:

- where project files live
- whether a new task shares hidden executor memory with a prior task

### Task

`Task` remains the durable user-visible work item.

It answers:

- what is the user asking for
- what is the current status
- which persona is assigned
- which workspace context this task should run inside

### WorkspaceContext

`WorkspaceContext` is the missing concept.

It is the identity for a reusable filesystem context. It represents a project-like working
directory that can outlive a task and can be reused by later related tasks.

Suggested shape:

```python
class WorkspaceContext(BaseModel):
    workspace_context_id: str
    root_path: str
    created_from_task_id: str | None = None
    created_by_persona_id: str | None = None
    label: str | None = None
    latest_task_id: str | None = None
    status: Literal["active", "archived"] = "active"
    metadata: dict[str, object] = Field(default_factory=dict)
```

This does not replace `Task`. It is the filesystem continuity anchor referenced by tasks.

### ExecutionSession

`ExecutionSession` remains the executor-side continuity lineage for one task.

It answers:

- which executor-native thread/session can continue this task
- which resume handle is valid for this task lineage
- which runs belong to the same execution lineage

It should stay task-scoped by default. It should not become persona-scoped.

## Key Rule

Filesystem continuity and executor-memory continuity are two different axes.

- `WorkspaceContext` controls files
- `ExecutionSession` controls executor-native continuation

They may move together for the same task resume, but they should not be collapsed into one
field or one policy.

## Behavioral Policy

### 1. New unrelated task

When the user creates a new task with no continuation hint:

- create a new `WorkspaceContext`
- create a new `ExecutionSession`
- assign any requested persona

This is the default isolation path.

### 2. Resume or reopen the same task

When the user is resuming the same task lineage:

- reuse the same `WorkspaceContext`
- reuse the same `ExecutionSession` when the executor supports resume
- fall back to recreating the executor session from the stored resume handle when needed

This is existing task continuity, not project-follow-up creation.

### 3. Create a follow-up task on the same project

When the user says something like "in that red-black-tree project, add tests":

- create a new `Task`
- reuse the previous task's `WorkspaceContext`
- create a new `ExecutionSession` by default

This is the most important rule in the RFC.

The new task should see the same files, but it should not automatically inherit all hidden
executor conversation memory from the previous task. Reusing workspace is usually correct here;
reusing the executor-native thread is often too sticky and causes prompt pollution.

### 4. Correction or task recreation

If Synapse recreates a task due to user correction, cancellation reversal, or other
task-replacement flows:

- carry over the same `WorkspaceContext`
- usually start a fresh `ExecutionSession` for the new task identity
- preserve explicit provenance such as `recreated_from_task_id`

This matches the existing behavior direction where `session_affinity` is copied forward during
recreation, but clarifies the intended semantics.

### 5. Executor-family handoff

If the same task switches executor family:

- keep the same `WorkspaceContext`
- create a new `ExecutionSession` for the new executor family

This keeps the project directory stable while respecting executor-specific resume semantics.

### 6. Persona change

If a different persona takes over a project:

- keep the same `WorkspaceContext`
- keep or recreate the `ExecutionSession` according to normal task rules

Persona reassignment must not force a new workspace.

## Explicit Continuation API

The system should support explicit project continuation at task creation time.

Recommended additions:

```python
create_task(
    title: str,
    goal: str,
    persona_name: str | None = None,
    continue_from_task_id: str | None = None,
)
```

Semantics:

- if `continue_from_task_id` is omitted, create a fresh `WorkspaceContext`
- if `continue_from_task_id` is provided, inherit that task's `WorkspaceContext`

This is a better public API than using persona identity to imply project continuity.

An internal advanced field like `workspace_context_id` may also exist later, but
`continue_from_task_id` is the most natural user-facing entry point because users think in
terms of "continue that task/project," not in terms of an opaque workspace id.

## Directory Layout

Long-term layout:

```
~/.synapse/workspaces/
  ws-3fa21d4b/
    .synapse-workspace.json
    ...
  ws-a91e8c02/
    .synapse-workspace.json
    ...
```

Rationale:

- workspace identity is independent from persona naming
- a single project can survive persona reassignment
- a single persona can touch many unrelated projects over time
- executor sessions can come and go without changing the directory path

Optional metadata inside `.synapse-workspace.json` can store:

- `workspace_context_id`
- `created_from_task_id`
- `label`
- `created_by_persona_id`

Human-friendly browsing can be handled by UI or metadata. The directory name itself should
prioritize stable identity over user-facing aesthetics.

## Data Model Changes

### Long-Term Target

Add a first-class `WorkspaceContext` protocol object and blackboard storage:

```python
put_workspace_context(...)
get_workspace_context(...)
list_workspace_contexts(...)
```

Add `workspace_context_id` to `Task`.

Possible future `Task` shape:

```python
class Task(BaseModel):
    task_id: str
    root_task_id: str
    parent_task_id: str | None = None
    title: str
    goal: str
    workspace_context_id: str | None = None
    ...
```

### Near-Term Compatibility Path

Today, Synapse already has `task.session_affinity`, and it is being used to store a workspace
path rather than a true session identity.

The near-term implementation can:

- keep using `task.session_affinity` as the resolved workspace path
- reinterpret it as a compatibility field for workspace placement
- avoid treating it as executor-session identity

This gives a small implementation path without blocking on a new protocol object.

Long-term, `session_affinity` should either be renamed to `workspace_affinity` or replaced by
`workspace_context_id` plus resolved-path lookup.

## Execution Rules

### Session Manager

`SessionManager.ensure_session()` should continue to manage executor-native continuity only for
the same task lineage.

It should not try to reuse a prior executor session just because:

- the persona is the same
- the workspace is the same

That would reintroduce hidden context pollution.

### Executor Adapters

`executor.create_session(workspace_id=...)` should receive the resolved workspace path from the
task's bound `WorkspaceContext`.

Executor adapters may still return executor-native resume handles, but those handles stay inside
`ExecutionSession.latest_resume_handle`.

### Persona Session Names

Persona-scoped stable executor session names should not be the main continuity mechanism.

Why:

- they couple unrelated tasks together through hidden executor memory
- they make persona identity act like project identity
- they do not generalize well across executors

Executor-native continuity should come from task-scoped resume handles, not persona naming.

## Communication Brain Guidance

The Communication Brain should treat project continuation as an explicit choice.

Examples:

- "Let Mochi make a red-black-tree demo."
  - create task
  - new workspace context

- "Let Mochi draw a cat."
  - create task
  - new workspace context

- "In the red-black-tree project, add unit tests."
  - create task with `continue_from_task_id=<red-black-tree-task>`
  - reuse workspace context

- "Resume that cancelled red-black-tree task."
  - resume existing task lineage
  - reuse execution session when possible

The brain should not infer "same persona" as meaning "same project."

## Alternatives Considered

### Persona-level workspace

Rejected.

Pros:

- simple mental model
- follow-up tasks work naturally

Cons:

- unrelated tasks for the same persona pollute one another
- users must create new personas just to get isolation
- persona identity becomes overloaded as project identity

### Task-level workspace only

Rejected as the full design.

Pros:

- strong isolation

Cons:

- follow-up tasks cannot see previous project files without extra continuation logic
- common "keep working on that project" flows are awkward

### Session-level workspace

Rejected.

Pros:

- seems to align with continuity at first glance

Cons:

- executor-specific
- does not survive executor handoff cleanly
- confuses filesystem identity with executor-memory identity

## Migration Plan

### Phase 1: Pragmatic fix

- keep default isolated workspaces for new tasks
- add `continue_from_task_id` to `create_task`
- on continuation, copy the prior task's workspace binding
- keep same-task resume behavior in `ExecutionSession`
- stop depending on persona-scoped executor session naming for continuity

This phase is intentionally small and can be implemented with current task fields.

### Phase 2: First-class workspace contexts

- introduce `WorkspaceContext` as a protocol and blackboard object
- add `workspace_context_id` to `Task`
- move path resolution behind the workspace-context layer
- deprecate direct user-facing mutation of `session_affinity`

### Phase 3: Richer project UX

- expose project/workspace history in the UI
- allow users to explicitly continue from a prior project
- optionally support archiving and labeling workspace contexts

## Compatibility Notes

Existing task-recreation flows already copy `session_affinity` from the old task to the new one.
That behavior is directionally correct and should be preserved during migration, but the field
should be understood as workspace continuity rather than session identity.

Existing directories such as:

```
~/.synapse/workspaces/{persona}/{task_id}/
```

can be supported during migration. New tasks can move to workspace-id-based directories without
requiring immediate cleanup of older ones.

## Examples

### Example A: Unrelated tasks, same persona

1. User: "Mochi, build a red-black-tree demo."
2. Synapse creates task `task-rbt`, workspace `ws-rbt`, execution session `exec-rbt`.
3. User later: "Mochi, draw a cat."
4. Synapse creates task `task-cat`, workspace `ws-cat`, execution session `exec-cat`.

Result:

- same persona
- different projects
- no file pollution
- no hidden executor-memory carry-over

### Example B: Follow-up task on the same project

1. User: "Mochi, build a red-black-tree demo."
2. Task `task-rbt` runs in `ws-rbt`.
3. User later: "Add unit tests in that project."
4. Synapse creates `task-rbt-tests` with `continue_from_task_id=task-rbt`.

Result:

- new task id
- same workspace `ws-rbt`
- new execution session by default

### Example C: Resume the same cancelled task

1. `task-rbt` is cancelled mid-run.
2. User says: "Resume it."

Result:

- same task
- same workspace `ws-rbt`
- same execution lineage when possible via resume handle

## Decision

Adopt a project-oriented workspace model:

- workspace continuity is anchored to `WorkspaceContext`
- task continuity is anchored to `ExecutionSession`
- persona identity remains orthogonal to both

The immediate implementation path should be:

- default new task => new workspace
- explicit continue => reuse workspace
- same-task resume => reuse workspace and task session lineage

This is the smallest design that satisfies isolation, continuity, and persona reuse at the same
time.
