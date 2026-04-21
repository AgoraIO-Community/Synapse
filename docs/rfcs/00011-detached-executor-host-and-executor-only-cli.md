# RFC 0011: Detached Executor Host and Executor-Only CLI

This RFC proposes a detached execution architecture for Synapse.

It is a proposal document, not the current source of truth for runtime
behavior. When this RFC conflicts with stable docs under `docs/architecture/`,
`docs/protocol/`, `docs/guides/`, or current code, treat the stable docs and
implemented behavior as authoritative.

## Summary

Synapse should detach real executor runtime from the main API process.

The target shape is:

- `Synapse` remains the durable control plane.
- real executors run inside a separate `executor host` process.
- the executor host usually runs on the user's personal machine.
- the executor host opens an outbound websocket connection to cloud Synapse.
- the executor host manages local executor adapters such as Codex or ACPX.
- blocked questions and user-visible task state still flow through normal
  Synapse protocol objects.

This is motivated by the expected deployment shape:

- most real executors live on a personal computer
- users may access the same cloud Synapse service from multiple devices
- the cloud service should not need direct inbound access to the personal
  machine

This RFC also proposes explicit CLI separation:

- `synapse setup` configures the main Synapse control plane only
- `synapse executor setup` configures the detached executor host only
- `synapse executor run` runs the detached executor host only
- `synapse dev` and `synapse start` do not auto-start the executor host

## Problem

The current codebase already has the right architectural intent:

- `Communication Brain`
- `Execution Brain`
- `Blackboard`
- normalized executor abstractions

But live executor ownership still sits too close to the main runtime process.

That is a mismatch for the expected real-world topology:

- the user wants one cloud Synapse service
- the user may talk to that cloud service from a phone, laptop, or browser on
  another machine
- the actual coding or desktop-capable executors often need to run on the
  user's personal computer, near local files, tools, and credentials

If Synapse keeps real executors in-process inside the main API server, several
problems follow:

- the cloud service must own machine-local execution concerns
- local-device capabilities are hard to expose safely to a cloud runtime
- multi-device access becomes awkward because the device with the executor and
  the device talking to Synapse may not be the same
- lifecycle and deployment concerns for control-plane logic and executor logic
  stay entangled

The system needs a cleaner split:

- Synapse as control plane
- detached executor host as live execution worker

## Goals

- keep `Task`, `ExecutionSession`, `ExecutionRun`, and `SessionBinding`
  Synapse-owned
- move live executor process and session ownership out of the main API server
- let a personal-machine executor host dial out to cloud Synapse
- preserve the current dual-brain model and blackboard-centered control flow
- keep blocked-input and user-facing interaction flows Synapse-owned
- support running the detached executor host by itself from the CLI
- keep detached executor setup separate from the main `synapse setup` flow
- make offline host behavior explicit rather than silently failing

## Non-Goals

- shared multi-user executor fleets in the first version
- first-class multi-host routing for one user in the first version
- automatic executor-host startup from `synapse dev` or `synapse start`
- replacing the existing session websocket used by frontend clients
- changing stable docs or `docs/memories.md` as part of this proposal alone
- defining a production-grade device enrollment system in the first version

## Deployment Model

### Control Plane

Cloud Synapse remains responsible for:

- user-facing HTTP and websocket APIs
- Communication Brain behavior
- Execution Brain scheduling and durable projections
- blackboard state
- summaries, notifications, and interaction requests
- task control semantics such as pause, resume, retry, and cancel

### Executor Host

The executor host is a headless process that runs separately from the main
Synapse API.

The executor host is responsible for:

- holding the live outbound websocket connection to Synapse
- advertising locally available executor adapters
- launching and supervising local executor sessions and processes
- translating executor-native events into normalized execution events
- forwarding blocked-input state back to Synapse
- receiving cancel or follow-up instructions from Synapse

### V1 Cardinality

The first version assumes:

- one default personal executor host per user or workspace

The design should preserve naming and metadata so multiple hosts can be added
later, but V1 should not require pool scheduling, host choice UI, or
capability-based routing across several hosts.

## Core Design

### Durable Ownership Stays In Synapse

This RFC keeps durable execution ownership in Synapse.

Synapse remains the source of truth for:

- `Task`
- `ExecutionSession`
- `ExecutionRun`
- `SessionBinding`
- `InteractionRequest`
- `TaskSummary`

The executor host does not become a second durable state authority. It only
owns live executor runtime and reports normalized state transitions back to
Synapse.

This keeps the existing design intent intact:

- Communication Brain and Execution Brain stay separate
- blackboard remains the shared fact layer
- user-facing semantics do not move into the personal-machine worker

### Full Detach For Real Executors

The target direction is full detach for real executors.

In the adopted detached model:

- the main Synapse process should not directly launch Codex, ACPX, or similar
  real executor runtimes
- real execution should happen through the executor host
- local development still works by running the control plane and the executor
  host on the same machine as separate processes

This keeps deployment topology explicit instead of relying on hidden in-process
fallbacks.

### Outbound Control Channel

The executor host should connect to Synapse through a dedicated executor-control
websocket. This is separate from:

- the frontend session websocket
- gateway-host upstream transport

The control channel direction is:

```text
Executor Host -> Synapse executor-control websocket
```

This outbound model is the right default because:

- the personal machine can initiate the connection to cloud Synapse
- Synapse does not need direct inbound reachability to the personal machine
- multiple user devices can still talk to the same cloud control plane

## Control Channel Protocol

The exact wire schema can evolve, but the message families should be explicit.

### Host To Synapse

- `register_host`
  - authenticate the host
  - identify `host_id`
  - advertise executor adapters and capabilities
- `heartbeat`
  - keep liveness current
- `run_event`
  - publish normalized progress, blocked, completed, failed, or cancelled run
    events
- `interaction_state`
  - report executor-native blocked-input metadata when a run needs user input
- `host_status`
  - report availability or degraded local state

### Synapse To Host

- `dispatch_run`
  - ask the host to start or continue a run for a Synapse-owned task/session
- `cancel_run`
  - stop a live run
- `supply_interaction_response`
  - deliver the user's answer back to a blocked local executor
- `release_run`
  - end host-side ownership for a run/session when Synapse decides the live
    association should be dropped
- `ack`
  - acknowledge channel-level delivery when useful

## Host Identity And Authentication

The first version should use a dedicated host credential model.

Minimum host identity:

- `host_id`
- `host_token`
- optional metadata such as machine label, platform, and advertised adapters

The host authenticates when opening the executor-control websocket.

This RFC explicitly rejects using normal end-user session auth as the primary
host identity because:

- a detached worker is not the same thing as an interactive user session
- the host should have a stable machine identity across several user devices
- operational controls and revocation should be host-oriented

Dynamic enrollment and richer device management can be added later. V1 can use
CLI-configured static credentials.

## Execution Flow

### Dispatch

Recommended flow:

1. A user creates or updates a task through normal Synapse APIs.
2. Synapse Execution Brain decides the task should run on the default personal
   executor host.
3. Synapse creates or updates its normal `Task`, `ExecutionSession`,
   `ExecutionRun`, and `SessionBinding` objects.
4. Synapse sends `dispatch_run` to the connected executor host.
5. The host starts or resumes the local executor session and streams normalized
   events back with `run_event`.

### Progress And Completion

The executor host translates local executor output into normalized events and
streams them back to Synapse.

Synapse remains responsible for:

- updating task/run/session state
- summary refresh
- notification planning
- projecting state to user-facing session streams

### Blocked Input

Blocked-input flow must remain Synapse-owned.

Recommended flow:

1. A local executor needs user input.
2. The executor host reports blocked state over the control channel.
3. Synapse creates or updates a normal `InteractionRequest`.
4. The user answers through any Synapse client device.
5. Synapse sends `supply_interaction_response` back to the executor host.
6. The executor host resumes the local executor session.

This preserves one user-facing interaction model even though live execution is
off-box.

### Cancel And Control

When the user cancels or otherwise controls a task:

1. Synapse validates the command against its normal execution state and
   capabilities.
2. Synapse updates durable control-plane objects.
3. Synapse sends the appropriate live control message, such as `cancel_run`, to
   the executor host.
4. The executor host stops the local executor session and reports terminal
   state.

The control plane still owns the semantic meaning of pause, resume, retry, and
cancel.

## Offline Behavior

If the selected executor host is offline, Synapse should not silently reroute or
pretend the work is progressing.

The first-version default is:

- keep the task queued or blocked in explicit host-unavailable state
- preserve the durable task, session, and run lineage in Synapse
- allow later reconnect or explicit reroute behavior

This is better than fail-fast or automatic cloud fallback for V1 because:

- the user's personal machine is the expected home of real executors
- automatic fallback can violate filesystem, credential, or tool assumptions
- a clear host-unavailable state is easier to reason about than hidden routing

## Data Model Direction

This RFC does not require final schema details yet, but the design should leave
room for:

- an `ExecutorHost` concept with `host_id`, connection status, and advertised
  capabilities
- execution-side metadata that records which host owns the live session or run
- explicit host-unavailable reason metadata for summaries or execution state

The important boundary is:

- host identity is execution-infrastructure metadata
- task identity and user-facing semantics remain Synapse protocol concepts

## CLI And Config

The CLI should make detached execution explicit and runnable on its own.

### Main Synapse Setup

`synapse setup` should remain focused on the main control plane:

- API/runtime settings
- shared core credentials
- control-plane-only configuration

It should not prompt for executor-host registration or detached-host auth.

### Executor-Only Setup

Add:

```bash
./synapse executor setup
```

This command configures only the detached executor host, including at least:

- Synapse base URL
- `host_id`
- `host_token`
- enabled local executor adapters and their local command/config settings

### Executor-Only Run

Add:

```bash
./synapse executor run
```

This command starts only the detached executor host.

That matters for local and personal-machine workflows where the user wants to:

- connect a laptop or desktop executor host to a cloud Synapse service
- run the personal-machine worker without also running the cloud-facing API
- keep detached execution lifecycle independent from the main backend process

### No Automatic Combined Startup

`synapse dev` and `synapse start` should not auto-start the executor host.

The detached worker should require an explicit command so the deployment model
stays clear:

- control plane startup is one concern
- executor host startup is another concern

This also avoids accidentally implying that detached execution is just another
embedded subprocess of the main runtime.

## Relationship To Existing Detached Hosts

This RFC intentionally follows the same broad separation lesson as the gateway
host:

- keep the main Synapse API focused on control-plane concerns
- run environment-specific runtime modules in separate headless processes

But the executor host is different from the gateway host in one important way:

- the gateway host adapts vendor runtime back into Synapse session APIs
- the executor host is the live execution worker for Synapse's own execution
  brain

So the executor host must integrate more deeply with execution lifecycle and
task-control flow than a vendor-facing gateway module does.

## Validation Scenarios

The first implementation guided by this RFC should prove these scenarios:

- `synapse executor run` starts the detached worker without starting the main
  Synapse API
- `synapse setup` finishes without executor-host-specific prompts
- `synapse executor setup` writes the detached-host configuration needed to
  authenticate and connect
- a task created from any client device is dispatched by cloud Synapse to the
  connected personal executor host
- local executor progress and completion events appear in normal Synapse task,
  session, run, summary, and frontend session projections
- a blocked local executor question becomes a normal Synapse
  `InteractionRequest`, and answering it from another device resumes the run
- cancelling a live run from Synapse reaches the executor host and stops the
  local executor session
- disconnecting the executor host leaves Synapse in a clear host-unavailable
  execution state without losing durable task identity

## Adoption Notes

If this RFC is adopted into stable architecture and protocol docs later, the
follow-up should update at least:

- `ARCHITECTURE.md`
- `docs/architecture/execution-brain.md`
- `docs/architecture/executors.md`
- `docs/protocol/execution-session-and-run.md`
- CLI and local-development guides

Because this document is proposal-only:

- do not treat it as the current implementation contract
- do not update `docs/memories.md` yet
