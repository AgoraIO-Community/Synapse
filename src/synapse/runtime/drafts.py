from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from synapse.protocol import (
    AsrTurn,
    Draft,
    DraftRiskLevel,
    DraftSession,
    DraftSessionStatus,
    DraftSnapshot,
)

DEFAULT_BRO_ID = "codex"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class DraftRewriteInput:
    previous_draft: Draft | None
    asr_turns: list[AsrTurn]
    new_turn: AsrTurn
    assigned_bro_id: str


class DraftRewriter:
    async def rewrite(self, payload: DraftRewriteInput) -> Draft:
        raise NotImplementedError


class DeterministicDraftRewriter(DraftRewriter):
    async def rewrite(self, payload: DraftRewriteInput) -> Draft:
        text = _turn_text(payload.new_turn)
        previous = payload.previous_draft
        locale = _draft_locale(text)
        if previous is None or _is_reset(text):
            goal = _clean_goal(text, locale)
            constraints: list[str] = []
            acceptance: list[str] = []
            assumptions: list[str] = []
            missing: list[str] = []
        else:
            goal = previous.goal
            constraints = list(previous.constraints)
            acceptance = list(previous.acceptance_criteria)
            assumptions = list(previous.assumptions)
            missing = list(previous.missing_info)

        lowered = text.lower()
        if _is_ambiguous_reference(lowered):
            missing = _append_unique(missing, _missing_reference_question(locale))
        if _negates_previous(lowered):
            goal = _clean_goal(text, locale)
            constraints = []
            acceptance = []
            assumptions = []
            missing = []
        if _mentions_youmind(lowered):
            goal = "Redesign the target in a YouMind-like clean minimal style."
            missing = [item for item in missing if "that style" not in item]
        elif _mentions_elevenlabs(lowered):
            goal = "Redesign the target in an ElevenLabs-like dark futuristic style."
            missing = [item for item in missing if "that style" not in item]
        elif previous is None or _is_reset(text):
            goal = _clean_goal(text, locale)

        if _contains_any(lowered, ["don't touch backend", "do not touch backend", "不要动后端", "不动后端"]):
            constraints = _append_unique(constraints, _constraint_text("no_backend", locale))
        if _contains_any(lowered, ["don't modify backend", "do not modify backend"]):
            constraints = _append_unique(constraints, _constraint_text("no_backend", locale))
        if _contains_any(lowered, ["don't add dependencies", "do not add dependencies", "不要新增依赖", "不新增依赖"]):
            constraints = _append_unique(constraints, _constraint_text("no_dependencies", locale))
        if _contains_any(lowered, ["keep existing", "preserve existing", "保留现有"]):
            constraints = _append_unique(constraints, _constraint_text("preserve_existing", locale))
        if "backend" in lowered and _constraint_text("no_backend", locale) not in constraints and _contains_any(lowered, ["不要", "不", "don't", "do not"]):
            constraints = _append_unique(constraints, _constraint_text("no_backend", locale))
        if "依赖" in text and _constraint_text("no_dependencies", locale) not in constraints and _contains_any(lowered, ["不要", "不"]):
            constraints = _append_unique(constraints, _constraint_text("no_dependencies", locale))

        if not acceptance:
            acceptance = _default_acceptance(goal, constraints, locale)
        else:
            acceptance = _merge_acceptance(acceptance, constraints, locale)

        if not goal.strip():
            goal = "执行前先澄清要完成的任务。" if locale == "zh" else "Clarify the requested task before execution."
            missing = _append_unique(missing, "Bro 需要做什么？" if locale == "zh" else "What should Bro do?")

        confidence = 0.45 if missing else 0.72
        risk = DraftRiskLevel.MEDIUM if missing else DraftRiskLevel.LOW
        title = _title_from_goal(goal)
        canonical = _canonical_instruction(goal, constraints, acceptance, assumptions, missing, locale)
        return Draft(
            title=title,
            goal=goal,
            constraints=constraints,
            acceptance_criteria=acceptance,
            canonical_instruction=canonical,
            assumptions=assumptions,
            missing_info=missing,
            last_update_summary=_last_update_summary(previous, goal, constraints, missing, locale),
            confidence=confidence,
            risk_level=risk,
        )


@dataclass(slots=True)
class DraftSessionManager:
    rewriter: DraftRewriter = field(default_factory=DeterministicDraftRewriter)
    _active_session: DraftSession | None = None

    @property
    def active_session(self) -> DraftSession | None:
        return self._active_session

    async def append_asr_turn(
        self,
        *,
        raw_text: str,
        normalized_text: str | None = None,
        confidence: float | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
        assigned_bro_id: str | None = None,
    ) -> DraftSession:
        text = raw_text.strip()
        if not text:
            raise ValueError("ASR turn text must not be empty.")
        now = utc_now_iso()
        session = self._active_session
        if session is None or session.status in {DraftSessionStatus.SENT, DraftSessionStatus.CLEARED}:
            session = DraftSession(
                id=f"draft-{uuid4().hex[:8]}",
                assigned_bro_id=assigned_bro_id or DEFAULT_BRO_ID,
                status=DraftSessionStatus.EMPTY,
                created_at=now,
                updated_at=now,
            )
        elif assigned_bro_id:
            session.assigned_bro_id = assigned_bro_id

        turn = AsrTurn(
            id=f"asr-{uuid4().hex[:8]}",
            raw_text=text,
            normalized_text=normalized_text.strip() if normalized_text and normalized_text.strip() else None,
            confidence=confidence,
            started_at=started_at or now,
            ended_at=ended_at or now,
        )
        session.status = DraftSessionStatus.DRAFTING
        session.asr_turns.append(turn)
        draft = await self.rewriter.rewrite(
            DraftRewriteInput(
                previous_draft=session.current_draft,
                asr_turns=list(session.asr_turns),
                new_turn=turn,
                assigned_bro_id=session.assigned_bro_id,
            )
        )
        snapshot = DraftSnapshot(
            id=f"draft-snap-{uuid4().hex[:8]}",
            draft=draft,
            source_asr_turn_ids=[item.id for item in session.asr_turns],
            created_at=utc_now_iso(),
        )
        session.current_draft = draft
        session.snapshots.append(snapshot)
        session.status = DraftSessionStatus.READY
        session.updated_at = snapshot.created_at
        self._active_session = session
        return session

    def clear(self) -> DraftSession | None:
        session = self._active_session
        if session is None:
            return None
        session.status = DraftSessionStatus.CLEARED
        session.updated_at = utc_now_iso()
        self._active_session = None
        return session

    def mark_sent(self, draft_session_id: str | None = None) -> DraftSession:
        session = self._active_session
        if session is None or session.current_draft is None or not session.snapshots:
            raise ValueError("No draft is ready to send.")
        if draft_session_id is not None and session.id != draft_session_id:
            raise ValueError("Draft session does not match the active draft.")
        session.status = DraftSessionStatus.SENT
        session.updated_at = utc_now_iso()
        self._active_session = None
        return session


def _turn_text(turn: AsrTurn) -> str:
    return (turn.normalized_text or turn.raw_text).strip()


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _draft_locale(text: str) -> str:
    return "zh" if any("\u4e00" <= character <= "\u9fff" for character in text) else "en"


def _mentions_youmind(text: str) -> bool:
    return "youmind" in text or "you mind" in text


def _mentions_elevenlabs(text: str) -> bool:
    return "elevenlabs" in text or "eleven labs" in text


def _is_reset(text: str) -> bool:
    lowered = text.lower()
    return _contains_any(lowered, ["start over", "new draft", "重新", "重来", "重新起草"])


def _negates_previous(text: str) -> bool:
    return _contains_any(
        text,
        ["no,", "actually", "not that", "don't use that", "do not use that", "不要刚才", "刚才那个不要", "不对"],
    )


def _is_ambiguous_reference(text: str) -> bool:
    return _contains_any(text, ["that style", "那个风格", "那种风格", "像那个"])


def _clean_goal(text: str, locale: str = "en") -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    if not cleaned.endswith(('.', '。', '!', '！', '?', '？')):
        cleaned += "。" if locale == "zh" else "."
    if locale == "zh":
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def _append_unique(items: list[str], item: str) -> list[str]:
    if item not in items:
        items.append(item)
    return items


def _constraint_text(kind: str, locale: str) -> str:
    if locale == "zh":
        return {
            "no_backend": "不要修改后端代码。",
            "no_dependencies": "不要新增依赖。",
            "preserve_existing": "保留现有行为和流程。",
        }[kind]
    return {
        "no_backend": "Do not modify backend code.",
        "no_dependencies": "Do not add dependencies.",
        "preserve_existing": "Preserve existing behavior and flows.",
    }[kind]


def _missing_reference_question(locale: str) -> str:
    return "“那个风格”具体指哪个参考？" if locale == "zh" else 'Which reference does "that style" refer to?'


def _default_acceptance(goal: str, constraints: list[str], locale: str = "en") -> list[str]:
    acceptance = ["任务按照草稿目标完成。"] if locale == "zh" else ["The requested task is completed according to the draft goal."]
    if locale == "en" and ("style" in goal.lower() or "redesign" in goal.lower()):
        acceptance = ["The target looks cleaner and matches the requested style direction."]
    if _constraint_text("no_backend", locale) in constraints:
        acceptance.append("后端代码没有被修改。" if locale == "zh" else "Backend code is not modified.")
    if _constraint_text("no_dependencies", locale) in constraints:
        acceptance.append("没有新增依赖。" if locale == "zh" else "No new dependency is added.")
    if _constraint_text("preserve_existing", locale) in constraints:
        acceptance.append("现有行为和流程保持可用。" if locale == "zh" else "Existing behavior and flows still work.")
    return acceptance


def _merge_acceptance(acceptance: list[str], constraints: list[str], locale: str = "en") -> list[str]:
    merged = list(acceptance)
    if _constraint_text("no_backend", locale) in constraints:
        merged = _append_unique(merged, "后端代码没有被修改。" if locale == "zh" else "Backend code is not modified.")
    if _constraint_text("no_dependencies", locale) in constraints:
        merged = _append_unique(merged, "没有新增依赖。" if locale == "zh" else "No new dependency is added.")
    if _constraint_text("preserve_existing", locale) in constraints:
        merged = _append_unique(merged, "现有行为和流程保持可用。" if locale == "zh" else "Existing behavior and flows still work.")
    return merged


def _title_from_goal(goal: str) -> str:
    title = goal.strip().rstrip(".。")
    if len(title) > 72:
        title = title[:69].rstrip() + "..."
    return title or "Draft task"


def _canonical_instruction(
    goal: str,
    constraints: list[str],
    acceptance: list[str],
    assumptions: list[str],
    missing: list[str],
    locale: str = "en",
) -> str:
    labels = {
        "goal": "目标" if locale == "zh" else "Goal",
        "constraints": "约束" if locale == "zh" else "Constraints",
        "acceptance": "验收标准" if locale == "zh" else "Acceptance Criteria",
        "assumptions": "假设" if locale == "zh" else "Assumptions",
        "missing": "待确认信息" if locale == "zh" else "Missing Info",
    }
    sections = [f"{labels['goal']}:\n{goal}"]
    if constraints:
        sections.append(f"{labels['constraints']}:\n" + "\n".join(f"- {item}" for item in constraints))
    if acceptance:
        sections.append(f"{labels['acceptance']}:\n" + "\n".join(f"- {item}" for item in acceptance))
    if assumptions:
        sections.append(f"{labels['assumptions']}:\n" + "\n".join(f"- {item}" for item in assumptions))
    if missing:
        sections.append(f"{labels['missing']}:\n" + "\n".join(f"- {item}" for item in missing))
    return "\n\n".join(sections)


def _last_update_summary(
    previous: Draft | None,
    goal: str,
    constraints: list[str],
    missing: list[str],
    locale: str = "en",
) -> str:
    if previous is None:
        if locale == "zh":
            return "已根据最新语音创建第一个可执行草稿。"
        return "Created the first executable draft from the latest voice turn."
    if previous.goal != goal:
        if locale == "zh":
            return "已根据最新语音重写草稿目标。"
        return "Rewrote the draft goal based on the latest voice turn."
    if missing:
        if locale == "zh":
            return "已更新草稿并标出待确认信息。"
        return "Updated the draft and surfaced missing information."
    if constraints != previous.constraints:
        if locale == "zh":
            return "已根据最新语音更新草稿约束。"
        return "Updated the draft constraints based on the latest voice turn."
    if locale == "zh":
        return "已根据最新语音刷新草稿。"
    return "Refreshed the draft from the latest voice turn."
