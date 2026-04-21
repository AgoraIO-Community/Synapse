from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from synapse.blackboard import BlackboardStore
from synapse.blackboard.store import BlackboardWriteEvent, BlackboardWriteKind
from synapse.protocol import (
    AttentionItem,
    AttentionItemKind,
    AttentionItemStatus,
    AttentionPriority,
    ExecutionRun,
    InteractionRequest,
    InteractionRequestKind,
    InteractionRequestStatus,
    RunStatus,
    Task,
    TaskSummary,
)


@dataclass(slots=True)
class InteractionResolution:
    request: InteractionRequest
    follow_up_instruction: str


class InteractionManager:
    def __init__(self, store: BlackboardStore) -> None:
        self._store = store

    async def handle_blackboard_write(self, event: BlackboardWriteEvent) -> bool:
        if event.kind == BlackboardWriteKind.RUN and event.entity_id:
            run = await self._store.get_run(event.entity_id)
            if run is None or run.status != RunStatus.BLOCKED:
                return False
            task = await self._store.get_task(run.task_id)
            if task is None:
                return False
            summary = await self._store.get_summary(task.task_id)
            existing = await self._store.list_interaction_requests()
            if any(
                request.run_id == run.run_id
                and request.status == InteractionRequestStatus.PENDING
                for request in existing
            ):
                return False
            request = _build_request_from_run(task=task, run=run, summary=summary)
            await self._store.put_interaction_request(request)
            await self._store.put_attention_item(_build_attention_from_request(task=task, request=request))
            return True

        if event.kind == BlackboardWriteKind.SUMMARY and event.entity_id:
            task = await self._store.get_task(event.entity_id)
            summary = await self._store.get_summary(event.entity_id)
            if task is None or summary is None or not summary.needs_user_input:
                return False
            existing = await self._store.list_interaction_requests()
            if any(
                request.task_id == task.task_id
                and request.status == InteractionRequestStatus.PENDING
                for request in existing
            ):
                return False
            request = _build_request_from_summary(task=task, summary=summary)
            await self._store.put_interaction_request(request)
            await self._store.put_attention_item(_build_attention_from_request(task=task, request=request))
            return True

        return False

    async def resolve_request(
        self,
        request_id: str,
        *,
        action: str,
        answer_text: str | None = None,
        option_id: str | None = None,
        reason: str | None = None,
    ) -> InteractionResolution:
        request = await self._store.get_interaction_request(request_id)
        if request is None:
            raise KeyError(f"Unknown interaction request: {request_id}")
        if request.status != InteractionRequestStatus.PENDING:
            raise ValueError("Interaction request is no longer pending.")
        if action not in request.available_actions:
            allowed = ", ".join(request.available_actions) or "none"
            raise ValueError(f"Action '{action}' is not allowed. Allowed: {allowed}.")
        if action == "answer" and not (answer_text and answer_text.strip()):
            raise ValueError("answer_text is required for answer actions.")

        resolved_status = _resolved_status_for_action(action)
        resolved_at = _now_iso()
        updated_request = request.model_copy(
            update={
                "status": resolved_status,
                "resolved_at": resolved_at,
                "details": {
                    **request.details,
                    **({"selected_option_id": option_id} if option_id else {}),
                    **({"resolution_reason": reason} if reason else {}),
                },
            }
        )
        await self._store.put_interaction_request(updated_request)
        await self._mark_attention_for_request(
            request_id=request.request_id,
            status=AttentionItemStatus.ACTED,
        )
        return InteractionResolution(
            request=updated_request,
            follow_up_instruction=_build_follow_up_instruction(
                request=updated_request,
                action=action,
                answer_text=answer_text,
            ),
        )

    async def add_task_signal_attention(
        self,
        *,
        task: Task,
        kind: AttentionItemKind,
        body: str,
    ) -> AttentionItem:
        item = AttentionItem(
            attention_id=f"attention-{uuid4().hex[:8]}",
            source="task_signal",
            kind=kind,
            priority=AttentionPriority.P2,
            title=_task_signal_title(task, kind),
            body=body,
            task_id=task.task_id,
            dedupe_key=f"{kind.value}:{task.task_id}:{task.task_revision}",
            created_at=_now_iso(),
        )
        await self._store.put_attention_item(item)
        return item

    async def cancel_requests_for_task(self, task_id: str) -> None:
        requests = await self._store.list_interaction_requests()
        for request in requests:
            if request.task_id != task_id or request.status != InteractionRequestStatus.PENDING:
                continue
            await self._store.put_interaction_request(
                request.model_copy(
                    update={
                        "status": InteractionRequestStatus.CANCELLED,
                        "resolved_at": _now_iso(),
                    }
                )
            )
            await self._mark_attention_for_request(
                request_id=request.request_id,
                status=AttentionItemStatus.DISMISSED,
            )

    async def _mark_attention_for_request(
        self,
        *,
        request_id: str,
        status: AttentionItemStatus,
    ) -> None:
        items = await self._store.list_attention_items()
        for item in items:
            if item.request_id != request_id or item.status == status:
                continue
            await self._store.put_attention_item(item.model_copy(update={"status": status}))


def _build_request_from_run(
    *,
    task: Task,
    run: ExecutionRun,
    summary: TaskSummary | None,
) -> InteractionRequest:
    prompt = (
        run.block_reason
        or (summary.conversational_summary if summary is not None else None)
        or f"{task.title} needs your input."
    )
    kind = _classify_prompt(prompt, run.metadata.get("blocked_event"))
    return InteractionRequest(
        request_id=f"ireq-{uuid4().hex[:8]}",
        task_id=task.task_id,
        execution_session_id=run.execution_session_id,
        run_id=run.run_id,
        executor_type=run.executor_type,
        kind=kind,
        prompt=prompt,
        details=_request_details(task=task, blocked_event=run.metadata.get("blocked_event")),
        available_actions=_actions_for_kind(kind),
        answer_schema={"type": "string"} if kind == InteractionRequestKind.QUESTION else None,
        opaque=_request_opaque(blocked_event=run.metadata.get("blocked_event")),
        created_at=_now_iso(),
    )


def _build_request_from_summary(
    *,
    task: Task,
    summary: TaskSummary,
) -> InteractionRequest:
    prompt = summary.conversational_summary or f"{task.title} needs your input."
    kind = _classify_prompt(prompt, None)
    return InteractionRequest(
        request_id=f"ireq-{uuid4().hex[:8]}",
        task_id=task.task_id,
        kind=kind,
        prompt=prompt,
        details=_request_details(task=task, blocked_event=None),
        available_actions=_actions_for_kind(kind),
        answer_schema={"type": "string"} if kind == InteractionRequestKind.QUESTION else None,
        created_at=_now_iso(),
    )


def _build_attention_from_request(*, task: Task, request: InteractionRequest) -> AttentionItem:
    item_kind = {
        InteractionRequestKind.PERMISSION: AttentionItemKind.PERMISSION_REQUEST,
        InteractionRequestKind.QUESTION: AttentionItemKind.QUESTION_REQUEST,
        InteractionRequestKind.CONFIRMATION: AttentionItemKind.CONFIRMATION_REQUEST,
    }[request.kind]
    return AttentionItem(
        attention_id=f"attention-{uuid4().hex[:8]}",
        source="interaction_request",
        kind=item_kind,
        priority=AttentionPriority.P0,
        title=_request_title(task, request.kind),
        body=request.prompt,
        task_id=task.task_id,
        request_id=request.request_id,
        actions=_attention_actions_for_request(request),
        dedupe_key=f"{item_kind.value}:{task.task_id}:{request.run_id or request.request_id}",
        created_at=_now_iso(),
    )


def _request_details(*, task: Task, blocked_event: object) -> dict[str, object]:
    details: dict[str, object] = {}
    persona_name = task.metadata.get("persona_name")
    if isinstance(persona_name, str) and persona_name:
        details["persona_name"] = persona_name
    if isinstance(blocked_event, dict):
        details["blocked_event"] = blocked_event
    return details


def _request_opaque(*, blocked_event: object) -> dict[str, object]:
    if isinstance(blocked_event, dict):
        native_response = blocked_event.get("native_response")
        if isinstance(native_response, dict):
            sanitized: dict[str, object] = {
                "request_id": native_response.get("request_id"),
                "method": native_response.get("method"),
            }
            params = native_response.get("params")
            if isinstance(params, dict):
                sanitized_params: dict[str, object] = {}
                for key in ("threadId", "turnId", "itemId", "reason", "command"):
                    value = params.get(key)
                    if isinstance(value, str) and value:
                        sanitized_params[key] = value
                if sanitized_params:
                    sanitized["params"] = sanitized_params
            return {"native_response": sanitized}
    return {}


def _classify_prompt(prompt: str, blocked_event: object) -> InteractionRequestKind:
    if isinstance(blocked_event, dict):
        explicit = blocked_event.get("interaction_kind")
        if explicit == "permission":
            return InteractionRequestKind.PERMISSION
        if explicit == "confirmation":
            return InteractionRequestKind.CONFIRMATION
        if explicit == "question":
            return InteractionRequestKind.QUESTION
    normalized = prompt.lower()
    if any(token in normalized for token in ["allow", "permission", "approve", "grant access"]):
        return InteractionRequestKind.PERMISSION
    if any(token in normalized for token in ["confirm", "confirmation", "are you sure"]):
        return InteractionRequestKind.CONFIRMATION
    return InteractionRequestKind.QUESTION


def _actions_for_kind(kind: InteractionRequestKind) -> list[str]:
    if kind == InteractionRequestKind.PERMISSION:
        return ["approve", "deny"]
    if kind == InteractionRequestKind.CONFIRMATION:
        return ["confirm", "cancel"]
    return ["answer"]


def _attention_actions_for_request(request: InteractionRequest) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for action in request.available_actions:
        label = {
            "approve": "Allow",
            "deny": "Deny",
            "answer": "Answer",
            "confirm": "Confirm",
            "cancel": "Cancel",
        }.get(action, action.replace("_", " ").title())
        actions.append({"action": action, "label": label})
    return actions


def _request_title(task: Task, kind: InteractionRequestKind) -> str:
    actor = task.metadata.get("persona_name")
    subject = str(actor) if isinstance(actor, str) and actor else task.title
    if kind == InteractionRequestKind.PERMISSION:
        return f"{subject} needs permission"
    if kind == InteractionRequestKind.CONFIRMATION:
        return f"{subject} needs confirmation"
    return f"{subject} needs your input"


def _task_signal_title(task: Task, kind: AttentionItemKind) -> str:
    actor = task.metadata.get("persona_name")
    subject = str(actor) if isinstance(actor, str) and actor else task.title
    if kind == AttentionItemKind.TASK_PAUSED:
        return f"{subject} paused"
    if kind == AttentionItemKind.TASK_RESUMED:
        return f"{subject} resumed"
    return subject


def _resolved_status_for_action(action: str) -> InteractionRequestStatus:
    mapping = {
        "approve": InteractionRequestStatus.APPROVED,
        "deny": InteractionRequestStatus.DENIED,
        "answer": InteractionRequestStatus.ANSWERED,
        "confirm": InteractionRequestStatus.RESOLVED,
        "cancel": InteractionRequestStatus.CANCELLED,
    }
    return mapping[action]


def _build_follow_up_instruction(
    *,
    request: InteractionRequest,
    action: str,
    answer_text: str | None,
) -> str:
    if request.kind == InteractionRequestKind.PERMISSION:
        if action == "approve":
            return "The user approved the pending permission request. Continue from where you left off."
        return (
            "The user denied the pending permission request. Do not perform that action. "
            "Continue with an alternative if possible, otherwise ask for next steps."
        )
    if request.kind == InteractionRequestKind.CONFIRMATION:
        if action == "confirm":
            return "The user confirmed the pending action. Continue."
        return (
            "The user cancelled the pending action. Do not perform it. "
            "Continue only if there is another safe path."
        )
    assert answer_text is not None
    return f"The user answered the pending question: {answer_text.strip()}. Continue from where you left off."


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
