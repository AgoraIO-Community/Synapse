import pytest

from synapse.runtime.drafts import DraftSessionManager


@pytest.mark.anyio
async def test_draft_rewrite_prefers_later_style_and_keeps_constraints():
    manager = DraftSessionManager()
    await manager.append_asr_turn(raw_text="Make it like ElevenLabs, dark and futuristic.")
    session = await manager.append_asr_turn(raw_text="No, make it like YouMind. Do not touch backend. Do not add dependencies.")

    draft = session.current_draft
    assert draft is not None
    assert "YouMind" in draft.goal
    assert "ElevenLabs" not in draft.goal
    assert "Do not modify backend code." in draft.constraints
    assert "Do not add dependencies." in draft.constraints
    assert len(session.asr_turns) == 2
    assert len(session.snapshots) == 2


@pytest.mark.anyio
async def test_draft_missing_reference_does_not_guess():
    manager = DraftSessionManager()
    session = await manager.append_asr_turn(raw_text="Make it like that style.")

    draft = session.current_draft
    assert draft is not None
    assert draft.missing_info == ['Which reference does "that style" refer to?']
    assert draft.confidence < 0.5


@pytest.mark.anyio
async def test_send_freezes_and_next_turn_creates_new_session():
    manager = DraftSessionManager()
    first = await manager.append_asr_turn(raw_text="Improve the homepage.")
    sent = manager.mark_sent()
    second = await manager.append_asr_turn(raw_text="Actually use YouMind style.")

    assert sent.id == first.id
    assert second.id != sent.id
    assert manager.active_session is second
