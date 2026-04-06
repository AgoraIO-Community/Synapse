# Summary and Notification Protocol

User-visible state should be projected through stable summary and notification objects.

`TaskSummary` should include:

- `operational_summary`
- `conversational_summary`
- `latest_user_visible_status`
- `needs_user_input`
- `summary_generated_at`

Summary principle:

- structured facts come first
- natural-language rendering can be generated later from those facts

`NotificationCandidate` should exist before any proactive message is emitted.

Notification principles:

- candidate first
- delivery later
- digest preferred
- user-visible history only records emitted messages
