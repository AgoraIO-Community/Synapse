# Draft-to-Execute Protocol

`newbro v0` uses a voice-driven draft-to-execute workflow.

The stable contract is:

```text
ASR turns = append-only evidence
Draft = current mutable intent
Task = immutable execution contract after Send
```

## ASR Turn

An `AsrTurn` is one completed voice turn. It is evidence for Draft Brain and is
not executed directly.

Fields:

- `id`
- `raw_text`
- `normalized_text`
- `confidence`
- `started_at`
- `ended_at`

## Bro Detail ASR Lifecycle

Bro Detail uses a dedicated Agora STT bot for draft shaping. The connector owns
the STT bot lifecycle; the browser owns RTC join, local microphone tracks, and
press-to-talk interaction.

Entering Bro Detail follows this state machine:

```text
Enter Bro Detail
  -> prepare unique Agora-safe channel + browser RTC token
  -> browser joins RTC with mic disabled
  -> ASR bot starting
  -> ASR bot ready + mic off
```

Microphone interaction is press-to-talk:

```text
ASR bot ready + mic off
  -> press mic
mic enabled locally
  -> release mic
mic disabled locally
  -> final ASR segment may trigger Draft updating
  -> ASR bot ready + mic off
```

Each prepare call creates a fresh Agora `channel_name` instead of reusing the
Synapse session id. The channel is ASCII-safe, bounded to the Agora channel name
limits, and returned by the connector so the browser RTC join and STT bot join
use the same channel.

STT recognition defaults to one source language via Agora
`languages: ["zh-CN"]`, while explicit connector config can override the
language list. This follows Agora's quality and cost guidance to avoid
multi-language recognition unless the workflow needs it. The STT bot also
subscribes explicitly to the browser RTC UID so it transcribes the user's audio
source rather than relying on implicit channel subscription behavior. The STT
publisher and subscriber bot UIDs are distinct, matching the Agora REST STT join
contract.

The browser heartbeats active STT sessions every 15 seconds. Explicit Bro Detail
leave stops the STT bot immediately. If the browser disappears without leave,
the connector stops the STT bot after more than 60 seconds without heartbeat.

Bro Detail accumulates ASR as strict time-structured original-language text.
For official Agora protobuf payloads, the browser uses `original_transcript`
for translation messages when present and otherwise uses top-level `words`.
Official JSON aliases are normalized, including `offset` as the sentence start
time and `duration` as milliseconds. `text_ts` / `textTs` is treated as the
recency timestamp for a sentence's candidate text. Timed candidates are grouped
by UID and sentence start time; untimed candidates with `textTs` are held as the
current provisional sentence until timed metadata arrives. Within one sentence
segment, only the candidate with the latest `textTs` is retained; sentence
segments are sorted by `time` and then joined. For Agora STT payloads,
`words[].isFinal` and JSON wrapper `isFinal` mean the current candidate is
stable, not that the semantic voice turn ended. Draft updates receive the
cumulative original-language transcript on mic release, about 1.2 seconds of
ASR silence, or a legacy explicit `end_of_segment === true` signal. The browser
does not merge translated transcript text into this original transcript stream.

## Draft Session

A `DraftSession` is the mutable pre-send workspace for one potential task.
The v0 runtime keeps one active draft session per Synapse session.

Fields:

- `id`
- `assigned_bro_id`
- `asr_turns`
- `current_draft`
- `snapshots`
- `status`
- `created_at`
- `updated_at`

## Draft

A `Draft` is the latest clean task intent shown to the user before Send.

Fields:

- `text`
- `last_update_summary`

Draft Brain rewrites the Draft after each ASR turn through the LLM-backed Draft
Cleaner. The cleaner receives ordered ASR turns, the latest turn, the assigned
Bro id, and the previous draft. It emits only plain clean sendable task text, not
JSON or labeled sections. The runtime stores that text directly in `Draft.text`.
It must keep only the current final execution intent, not the whole revision
history. If the LLM draft cleaner is not configured, draft generation fails
instead of falling back to deterministic rewriting.

## Send Boundary

`Send` freezes the current Draft into a queued `Task`.

When `assigned_bro_id` matches a runtime `Persona`, Send assigns the created
task to that Bro by setting the task's persona metadata and marking the persona
`busy` with `current_task_id`. The task still uses the runtime executor type as
its executor; the Bro id is not treated as an executor id. If the Bro is bound
to an executor node, the node binding is copied into task metadata so execution
can wait on or dispatch to that node.

Each runtime Bro carries a `bro_detail_session_id` generation. Send copies that
generation into task metadata and uses it as the task's executor-session
continuity key. Draft tasks from the same Bro detail generation reuse one
executor session when the executor family and bound node also match. Rebinding
the Bro to a different executor node rotates the generation, so future tasks no
longer reuse the old executor session and the Bro detail UI no longer shows the
old generation in Recent tasks.

For v0, draft-created tasks store the draft contract in `Task.metadata`:

- `immutable: true`
- `source_kind: draft_session`
- `draft_session_id`
- `draft_snapshot_id`
- `asr_turn_ids`
- `assigned_bro_id`
- `draft_text`
- `persona_id`, `persona_name`, `bro_detail_session_id`, and
  `executor_node_id` when Send targets a configured runtime Bro

After Send, later voice input creates or updates a separate draft session. It
must not mutate the sent task contract.

## Stop Boundary

`Stop Task` maps to the existing `cancel_task` command in v0. The product labels
this terminal state as `Stopped`, while backend compatibility keeps the existing
`cancelled` task status.
