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

The browser shell starts the realtime STT service after Home session bootstrap
with the local microphone muted. Live ASR turns are only produced after the user
opens a Bro detail page and unmutes the local microphone for that Bro.

Fields:

- `id`
- `raw_text`
- `normalized_text`
- `confidence`
- `started_at`
- `ended_at`

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
