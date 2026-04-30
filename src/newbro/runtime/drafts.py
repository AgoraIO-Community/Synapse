from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from newbro.protocol import (
    AsrTurn,
    Draft,
    DraftSession,
    DraftSessionStatus,
    DraftSnapshot,
)

DEFAULT_BRO_ID = "codex"
DRAFT_CLEANER_SYSTEM_PROMPT = """You are the Draft Cleaner for newbro.

The user is speaking across multiple ASR turns to prepare a task for a coding bro.
Your job is to produce a clean, faithful draft of what the user wants to send.

Do not turn the user's words into a full product spec.
Do not invent details the user did not express.
Only preserve what the user actually expressed.
You may lightly clean ASR errors, remove filler words, and merge corrections.
If the latest turn contradicts earlier turns, prefer the latest turn.
If the user explicitly rejects a previous idea, remove that idea from the draft.
Keep the draft concise and sendable."""


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class DraftRewriteInput:
    previous_draft: Draft | None
    asr_turns: list[AsrTurn]
    new_turn: AsrTurn
    assigned_bro_id: str


TextDeltaCallback = Callable[[str], Awaitable[None] | None]


class DraftRewriter:
    async def rewrite(
        self,
        payload: DraftRewriteInput,
        *,
        on_text_delta: TextDeltaCallback | None = None,
    ) -> Draft:
        raise NotImplementedError


class DraftRewriteError(RuntimeError):
    pass


class DraftRewriteUnavailable(DraftRewriteError):
    pass


class DraftRewriteInvalidOutput(DraftRewriteError):
    pass


class DraftRewriteUpstreamError(DraftRewriteError):
    pass


class UnavailableDraftRewriter(DraftRewriter):
    async def rewrite(
        self,
        payload: DraftRewriteInput,
        *,
        on_text_delta: TextDeltaCallback | None = None,
    ) -> Draft:
        raise DraftRewriteUnavailable("Draft generation requires a configured LLM provider.")


class OpenAIDraftRewriter(DraftRewriter):
    def __init__(self, provider: Any, *, model: str) -> None:
        self._provider = provider
        self._model = model

    async def rewrite(
        self,
        payload: DraftRewriteInput,
        *,
        on_text_delta: TextDeltaCallback | None = None,
    ) -> Draft:
        try:
            request = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": DRAFT_CLEANER_SYSTEM_PROMPT},
                    {"role": "user", "content": _draft_rewrite_user_message(payload)},
                ],
            }
            if on_text_delta is None:
                response = await self._provider.create_completion(**request)
                content = _completion_text(response)
            else:
                stream = await self._provider.create_completion(**request, stream=True)
                content = await _completion_stream_text(stream, on_text_delta)
        except DraftRewriteError:
            raise
        except Exception as exc:
            raise DraftRewriteUpstreamError("Draft cleaner request failed.") from exc
        return _draft_from_plain_text(
            content,
            previous=payload.previous_draft,
            locale=_draft_locale(_turn_text(payload.new_turn)),
        )


class DeterministicDraftRewriter(DraftRewriter):
    async def rewrite(
        self,
        payload: DraftRewriteInput,
        *,
        on_text_delta: TextDeltaCallback | None = None,
    ) -> Draft:
        text = _turn_text(payload.new_turn)
        previous = payload.previous_draft
        locale = _draft_locale(text)
        draft_text = _clean_goal(text, locale)
        if not draft_text.strip():
            draft_text = "执行前先澄清要完成的任务。" if locale == "zh" else "Clarify the requested task before execution."
        return Draft(
            text=draft_text,
            last_update_summary=_last_update_summary(previous, draft_text, locale),
        )


@dataclass(slots=True)
class DraftSessionManager:
    rewriter: DraftRewriter = field(default_factory=UnavailableDraftRewriter)
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
        on_text_delta: TextDeltaCallback | None = None,
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
        next_turns = [*session.asr_turns, turn]
        rewrite_input = DraftRewriteInput(
            previous_draft=session.current_draft,
            asr_turns=next_turns,
            new_turn=turn,
            assigned_bro_id=session.assigned_bro_id,
        )
        if on_text_delta is None:
            draft = await self.rewriter.rewrite(rewrite_input)
        else:
            draft = await self.rewriter.rewrite(rewrite_input, on_text_delta=on_text_delta)
        session.status = DraftSessionStatus.DRAFTING
        session.asr_turns.append(turn)
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


def _draft_rewrite_user_message(payload: DraftRewriteInput) -> str:
    previous = payload.previous_draft.text if payload.previous_draft else "(none)"
    turns = "\n".join(
        f"{index}. [{turn.id}] {_turn_text(turn)}"
        for index, turn in enumerate(payload.asr_turns, start=1)
    )
    return (
        "Return only the clean sendable task text.\n"
        "Do not return JSON, code fences, labels, commentary, or revision history.\n"
        "Write the exact text the user should send to the assigned coding bro.\n\n"
        f"Assigned bro id:\n{payload.assigned_bro_id}\n\n"
        f"Previous draft:\n{previous}\n\n"
        f"Ordered ASR turns:\n{turns}\n\n"
        f"Latest turn:\n{_turn_text(payload.new_turn)}"
    )


def _completion_text(completion: Any) -> str:
    choices = _get_value(completion, "choices") or []
    if not choices:
        raise DraftRewriteInvalidOutput("Draft cleaner returned no choices.")
    message = _get_value(choices[0], "message")
    content = _get_value(message, "content")
    if isinstance(content, str):
        text = content.strip()
        if text:
            return text
    raise DraftRewriteInvalidOutput("Draft cleaner returned empty content.")


async def _completion_stream_text(stream: Any, on_text_delta: TextDeltaCallback) -> str:
    chunks: list[str] = []
    uses_context_manager = hasattr(stream, "__aenter__") and hasattr(stream, "__aexit__")
    try:
        if uses_context_manager:
            async with stream as entered:
                async for chunk in entered:
                    await _append_stream_chunk(chunk, chunks, on_text_delta)
        else:
            async for chunk in stream:
                await _append_stream_chunk(chunk, chunks, on_text_delta)
    finally:
        close = getattr(stream, "aclose", None)
        if not uses_context_manager and callable(close):
            maybe_awaitable = close()
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

    text = "".join(chunks).strip()
    if text:
        return text
    raise DraftRewriteInvalidOutput("Draft cleaner returned empty content.")


async def _append_stream_chunk(
    chunk: Any,
    chunks: list[str],
    on_text_delta: TextDeltaCallback,
) -> None:
    delta = _completion_chunk_text(chunk)
    if not delta:
        return
    chunks.append(delta)
    maybe_awaitable = on_text_delta(delta)
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


def _completion_chunk_text(chunk: Any) -> str:
    choices = _get_value(chunk, "choices") or []
    if not choices:
        return ""
    delta = _get_value(choices[0], "delta")
    content = _get_value(delta, "content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            text = _get_value(part, "text")
            if isinstance(text, str):
                text_parts.append(text)
                continue
            text_value = _get_value(text, "value")
            if isinstance(text_value, str):
                text_parts.append(text_value)
        return "".join(text_parts)
    return str(content)


def _get_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _draft_from_plain_text(text: str, *, previous: Draft | None, locale: str) -> Draft:
    draft_text = text.strip()
    if not draft_text:
        raise DraftRewriteInvalidOutput("Draft cleaner returned empty content.")
    return Draft(
        text=draft_text,
        last_update_summary=_last_update_summary(previous, draft_text, locale),
    )


def _draft_locale(text: str) -> str:
    return "zh" if any("\u4e00" <= character <= "\u9fff" for character in text) else "en"


def _clean_goal(text: str, locale: str = "en") -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    if not cleaned.endswith(('.', '。', '!', '！', '?', '？')):
        cleaned += "。" if locale == "zh" else "."
    if locale == "zh":
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def _title_from_goal(goal: str) -> str:
    title = goal.strip().rstrip(".。")
    if len(title) > 72:
        title = title[:69].rstrip() + "..."
    return title or "Draft task"


def _last_update_summary(
    previous: Draft | None,
    text: str,
    locale: str = "en",
) -> str:
    if previous is None:
        return ""
    if previous.text != text:
        if locale == "zh":
            return "已根据最新语音重写草稿。"
        return "Rewrote the draft based on the latest voice turn."
    if locale == "zh":
        return "已根据最新语音刷新草稿。"
    return "Refreshed the draft from the latest voice turn."
