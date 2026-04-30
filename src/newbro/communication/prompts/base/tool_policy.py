from __future__ import annotations

from newbro.communication.context import CommunicationContext


def build_tool_policy_prompt(context: CommunicationContext) -> str:
    lines = [
        "Tool-selection policy:",
        "- create_task: brand-new work or actionable user requests that should become a task.",
        "- update_task: change core structured task fields such as title, goal, priority, executor preference, or latest_instruction.",
        "- add_task_note: append extra user context, examples, preferences, or clarifications to an existing task.",
        "- add_constraint: append execution constraints such as deadlines, formatting rules, do-not-send, forbidden actions, or required approach.",
        "- control_task: pause, resume, cancel, retry, or preempt a task.",
        "- resolve_interaction_request: approve, deny, answer, confirm, or cancel a pending interaction request when the user is replying to one.",
        "- list_tasks: resolve references like 'that one', 'the email task', or 'the last task' before a write or query when the target is uncertain.",
        "- query_task_summary: answer user-facing progress questions.",
        "- query_task_detail: answer deeper status questions that need more execution detail.",
        "Decision rules:",
        "- Default to the task model for actionable requests, even when the user phrases them as a question.",
        "- Only clear social chat, subjective/persona questions, and Newbro meta questions should stay as pure chat.",
        "- Fact-checking, claim verification, current-world information requests, and other requests that depend on live external facts should normally become tasks instead of pure chat replies.",
        "- Requests to inspect the user's machine, inspect the current repo/workspace, run commands, or read the environment should normally become tasks.",
        "- If a live-verification or external-info request is missing a required detail such as location, ticker, date, or target claim, ask a short clarification instead of pretending to know or refusing generically.",
        "- For existing-task writes or queries, if the target is uncertain, call list_tasks first.",
        "- If runtime_context.interaction_requests contains a pending request and the user's latest message is clearly answering that request, prefer resolve_interaction_request over treating the message as generic chat.",
        "- Short follow-up corrections such as 'it should be X', 'actually X', 'to X', 'from X', or 'X instead of Y' should normally apply to the focused task or focused task bundle. If the corrected field is ambiguous, ask one short clarification instead of guessing.",
        "- Casual cancellation language such as 'forget it', 'never mind', or 'cancel that' should normally use control_task with command_type='cancel_task' when one active target is clear.",
        "- Prefer add_task_note or add_constraint over update_task when the user is appending context rather than changing the task's core identity.",
        "- Use at most one write tool unless a read-then-write step is necessary.",
        "- When using control_task, command_type must exactly match the schema value such as 'resume_task', not shortened verbs like 'resume'.",
        "- Always pass task_id from context rather than a text reference when the task is visible in active_tasks or focused_tasks.",
        "- Refinements to a running task (adding details, constraints) -> add_constraint / add_task_note. Do NOT cancel + recreate.",
        "- Cancel + create only when the user abandons the previous goal entirely.",
        "- When uncertain whether to update or create, ask a short clarification.",
        "- Creating a new task does NOT require pausing or cancelling other tasks. Tasks run in parallel.",
    ]
    if context.executor_runtime.has_real_executor:
        lines.append(
            "- At least one real executor is available, so normal actionable requests should usually become tasks."
        )
    else:
        lines.append(
            "- Only the mock executor is available. Do not create ordinary work tasks unless the user explicitly asks for a mock or simulated task."
        )
        lines.append(
            "- When only the mock executor is available, normal task requests should be blocked with a clear natural-language explanation instead of fake task creation."
        )
        lines.append(
            "- Do not reply with generic manual tips unless the user explicitly asks for instructions."
        )
        lines.append(
            "- Do not fall back to generic advice like 'check a website or app' for live verification requests unless the user explicitly asks for self-service alternatives."
        )
    lines.append(
        "- Only set create_task.mock_safe=true when the user explicitly wants a mock, simulated, or record-only task."
    )
    return "\n".join(lines)
