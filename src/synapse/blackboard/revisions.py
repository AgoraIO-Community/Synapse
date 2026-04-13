from __future__ import annotations

from datetime import UTC, datetime

from synapse.protocol import SessionBinding, Task


def bump_task_revision(task: Task) -> Task:
    task.task_revision += 1
    return task


def claim_is_active(
    binding: SessionBinding | None,
    *,
    now: datetime | None = None,
) -> bool:
    if binding is None or binding.claim_expires_at is None:
        return False
    current = now or datetime.now(UTC)
    expires_at = _parse_datetime(binding.claim_expires_at)
    return expires_at > current


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
