# Task Execution Detail

`TaskExecutionDetailEntry` is the append-only execution-history projection used to
preserve recent task progress detail without turning the blackboard into a raw
executor log dump.

Fields:

- `detail_id`
- `task_id`
- `run_id`
- `execution_session_id`
- `event_type`
- `text`
- `created_at`
- `payload`

Rules:

- entries are execution-only; they do not replace `TaskSummary`, `TaskMutation`,
  or `TaskCommand`
- each entry is anchored to one task plus the originating run and execution
  session
- `text` is the normalized detail line suitable for prompt context and
  debugging
- `payload` may carry structured extra execution metadata, but communication
  prompt context should stay compact

Read behavior:

- per-task reads may be bounded to the most recent `N` entries while preserving
  append order
- communication prompt context should use only the last 5 tasks with recent
  execution-detail activity and only the last 20 entries per included task
- older tasks should be inspected through `query_task_detail` instead of being
  auto-injected into every turn
