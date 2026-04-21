from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
import re

from synapse.protocol import Task, TaskStatus


ResolutionStatus = Literal["resolved", "ambiguous", "not_found"]

ACTIVE_TASK_STATUSES = {
    TaskStatus.CREATED,
    TaskStatus.QUEUED,
    TaskStatus.WAITING_EXECUTOR,
    TaskStatus.RUNNING,
    TaskStatus.WAITING_USER_INPUT,
    TaskStatus.PAUSED,
}


@dataclass(slots=True)
class TaskResolutionCandidate:
    task: Task
    score: int
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskResolution:
    status: ResolutionStatus
    task: Task | None = None
    candidates: list[TaskResolutionCandidate] = field(default_factory=list)


class TaskResolver:
    def resolve(
        self,
        tasks: list[Task],
        *,
        task_id: str | None = None,
        reference: str | None = None,
    ) -> TaskResolution:
        if task_id:
            for task in tasks:
                if task.task_id == task_id:
                    return TaskResolution(status="resolved", task=task)
            return TaskResolution(status="not_found")

        if not reference or not reference.strip():
            return TaskResolution(status="not_found")

        candidates = self.list_relevant(tasks, reference=reference)
        if not candidates:
            return TaskResolution(status="not_found")
        if len(candidates) == 1:
            return TaskResolution(status="resolved", task=candidates[0].task, candidates=candidates)

        top_candidate = candidates[0]
        second_candidate = candidates[1]
        if top_candidate.score >= second_candidate.score + 25:
            return TaskResolution(
                status="resolved",
                task=top_candidate.task,
                candidates=candidates,
            )
        return TaskResolution(status="ambiguous", candidates=candidates)

    def list_relevant(
        self,
        tasks: list[Task],
        *,
        reference: str,
        limit: int = 5,
    ) -> list[TaskResolutionCandidate]:
        needle = reference.strip().lower()
        if not needle:
            return []

        tokens = _reference_tokens(needle)
        matches: list[TaskResolutionCandidate] = []
        total_tasks = len(tasks)
        for index, task in enumerate(tasks):
            score, reasons = _score_task_match(task, needle=needle, tokens=tokens)
            if score <= 0:
                continue
            if task.status in ACTIVE_TASK_STATUSES:
                score += 8
                reasons.append("active")
            # Favor newer tasks when textual relevance is otherwise close.
            score += index + 1
            matches.append(TaskResolutionCandidate(task=task, score=score, reasons=reasons))

        matches.sort(key=lambda item: (item.score, item.task.task_revision), reverse=True)
        return matches[:limit]


def describe_candidates(
    candidates: list[TaskResolutionCandidate],
    *,
    limit: int = 3,
) -> str:
    labels = [f"{candidate.task.task_id} ({candidate.task.title})" for candidate in candidates[:limit]]
    return ", ".join(labels)


def _reference_tokens(reference: str) -> list[str]:
    return [token for token in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", reference) if token]


def _score_task_match(
    task: Task,
    *,
    needle: str,
    tokens: list[str],
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    weighted_fields = [
        ("title", task.title, 120, 70, 18),
        ("goal", task.goal, 100, 55, 12),
        ("latest_instruction", task.latest_instruction or "", 90, 45, 10),
    ]

    notes = [
        item.strip()
        for item in task.metadata.get("notes", [])
        if isinstance(item, str) and item.strip()
    ]
    constraints = [
        item.get("constraint", "").strip()
        for item in task.metadata.get("constraints", [])
        if isinstance(item, dict) and isinstance(item.get("constraint"), str)
    ]
    if notes:
        weighted_fields.append(("notes", " ".join(notes), 60, 30, 8))
    if constraints:
        weighted_fields.append(("constraints", " ".join(constraints), 70, 35, 8))

    for field_name, raw_value, exact_score, substring_score, token_score in weighted_fields:
        value = raw_value.lower()
        if not value:
            continue
        if value == needle:
            score += exact_score
            reasons.append(f"exact_{field_name}")
            continue
        if needle in value:
            score += substring_score
            reasons.append(f"substring_{field_name}")
        matched_tokens = [token for token in tokens if len(token) >= 2 and token in value]
        if matched_tokens:
            score += token_score * len(matched_tokens)
            reasons.append(f"token_{field_name}")

    return score, reasons
