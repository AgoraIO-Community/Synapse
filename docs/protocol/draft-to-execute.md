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
ASR bot ready + mic capturing
  -> release mic
ASR bot ready + transcribing
  -> Draft updating
  -> ASR bot ready + mic off
```

Each prepare call creates a fresh Agora `channel_name` instead of reusing the
Synapse session id. The channel is ASCII-safe, bounded to the Agora channel name
limits, and returned by the connector so the browser RTC join and STT bot join
use the same channel.

STT recognition defaults to Chinese via Agora `languages: ["zh-CN"]`, while
explicit connector config can override the language list. The STT bot also
subscribes explicitly to the browser RTC UID so it transcribes the user's audio
source rather than relying on implicit channel subscription behavior.

The browser heartbeats active STT sessions every 15 seconds. Explicit Bro Detail
leave stops the STT bot immediately. If the browser disappears without leave,
the connector stops the STT bot after more than 60 seconds without heartbeat.

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

- `title`
- `goal`
- `constraints`
- `acceptance_criteria`
- `canonical_instruction`
- `assumptions`
- `missing_info`
- `last_update_summary`
- `confidence`
- `risk_level`

Draft Brain rewrites the full Draft after each ASR turn. It should keep only the
current final execution intent, not the whole revision history.

## Send Boundary

`Send` freezes the current Draft into a queued `Task`.

For v0, draft-created tasks store the draft contract in `Task.metadata`:

- `immutable: true`
- `source_kind: draft_session`
- `draft_session_id`
- `draft_snapshot_id`
- `asr_turn_ids`
- `assigned_bro_id`
- `constraints`
- `acceptance_criteria`
- `assumptions`
- `missing_info`
- `canonical_instruction`

After Send, later voice input creates or updates a separate draft session. It
must not mutate the sent task contract.

## Stop Boundary

`Stop Task` maps to the existing `cancel_task` command in v0. The product labels
this terminal state as `Stopped`, while backend compatibility keeps the existing
`cancelled` task status.
