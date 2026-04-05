from __future__ import annotations

from datetime import UTC, datetime, timedelta

from synopse.blackboard.revisions import bump_task_revision, claim_is_active
from synopse.protocol import SessionBinding, Task


def test_bump_task_revision_increments_in_place():
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Test",
        goal="Test revision bump",
    )

    bump_task_revision(task)
    bump_task_revision(task)

    assert task.task_revision == 2


def test_claim_is_active_checks_expiry_timestamp():
    now = datetime.now(UTC)
    active = SessionBinding(
        task_id="task_1",
        execution_session_id="sess_1",
        session_id="agent_1",
        claim_expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    expired = SessionBinding(
        task_id="task_1",
        execution_session_id="sess_1",
        session_id="agent_1",
        claim_expires_at=(now - timedelta(minutes=5)).isoformat(),
    )

    assert claim_is_active(active, now=now) is True
    assert claim_is_active(expired, now=now) is False
