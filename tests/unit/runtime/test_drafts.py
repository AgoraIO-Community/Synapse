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
async def test_chinese_draft_rewrite_uses_chinese_display_text():
    manager = DraftSessionManager()
    session = await manager.append_asr_turn(raw_text="好像在一场大型音乐演唱会上面南美人在美国超级碗上面唱了一首西班牙语的歌")

    draft = session.current_draft
    assert draft is not None
    assert draft.goal == "好像在一场大型音乐演唱会上面南美人在美国超级碗上面唱了一首西班牙语的歌。"
    assert draft.title == "好像在一场大型音乐演唱会上面南美人在美国超级碗上面唱了一首西班牙语的歌"
    assert draft.acceptance_criteria == ["任务按照草稿目标完成。"]
    assert draft.canonical_instruction.startswith("目标:\n")
    assert "验收标准:\n- 任务按照草稿目标完成。" in draft.canonical_instruction
    assert draft.last_update_summary == "已根据最新语音创建第一个可执行草稿。"


@pytest.mark.anyio
async def test_chinese_draft_constraints_use_chinese_text():
    manager = DraftSessionManager()
    session = await manager.append_asr_turn(raw_text="改一下首页，但是不要动后端，不要新增依赖，保留现有流程")

    draft = session.current_draft
    assert draft is not None
    assert "不要修改后端代码。" in draft.constraints
    assert "不要新增依赖。" in draft.constraints
    assert "保留现有行为和流程。" in draft.constraints
    assert "后端代码没有被修改。" in draft.acceptance_criteria
    assert "没有新增依赖。" in draft.acceptance_criteria
    assert "现有行为和流程保持可用。" in draft.acceptance_criteria
    assert "约束:\n- 不要修改后端代码。" in draft.canonical_instruction


@pytest.mark.anyio
async def test_send_freezes_and_next_turn_creates_new_session():
    manager = DraftSessionManager()
    first = await manager.append_asr_turn(raw_text="Improve the homepage.")
    sent = manager.mark_sent()
    second = await manager.append_asr_turn(raw_text="Actually use YouMind style.")

    assert sent.id == first.id
    assert second.id != sent.id
    assert manager.active_session is second
