from types import SimpleNamespace

import pytest

from synapse.protocol import Draft
from synapse.runtime.drafts import (
    DRAFT_CLEANER_SYSTEM_PROMPT,
    DraftRewriteInput,
    DraftRewriteInvalidOutput,
    DraftRewriteUpstreamError,
    DraftRewriter,
    DraftSessionManager,
    OpenAIDraftRewriter,
)


def _text_completion(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text),
                finish_reason="stop",
            )
        ]
    )


class FakeCompletionProvider:
    def __init__(self, responses: list[SimpleNamespace | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def create_completion(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _stream_chunk(text: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


class FakeStream:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return _stream_chunk(self._chunks.pop(0))


class EchoDraftRewriter(DraftRewriter):
    async def rewrite(self, payload: DraftRewriteInput) -> Draft:
        text = (payload.new_turn.normalized_text or payload.new_turn.raw_text).strip()
        return Draft(
            text=text,
        )


@pytest.mark.anyio
async def test_openai_draft_rewriter_uses_cleaner_prompt_and_asr_context():
    provider = FakeCompletionProvider(
        [
            _text_completion("Make it like ElevenLabs."),
            _text_completion("Make it like YouMind. Do not add dependencies."),
        ]
    )
    manager = DraftSessionManager(rewriter=OpenAIDraftRewriter(provider, model="gpt-test"))
    await manager.append_asr_turn(raw_text="Make it like ElevenLabs.")
    session = await manager.append_asr_turn(
        raw_text="No, make it like YouMind. Do not add dependencies.",
        assigned_bro_id="persona-forge",
    )

    draft = session.current_draft
    assert draft is not None
    assert draft.text == "Make it like YouMind. Do not add dependencies."

    second_call = provider.calls[1]
    assert second_call["model"] == "gpt-test"
    assert "response_format" not in second_call
    messages = second_call["messages"]
    assert messages[0] == {"role": "system", "content": DRAFT_CLEANER_SYSTEM_PROMPT}
    user_content = messages[1]["content"]
    assert user_content.startswith("Return only the clean sendable task text.")
    assert "Do not return JSON" in user_content
    assert "code fences" in user_content
    assert "Assigned bro id:\npersona-forge" in user_content
    assert "Previous draft:\nMake it like ElevenLabs." in user_content
    assert "1. [" in user_content
    assert "Make it like ElevenLabs." in user_content
    assert "2. [" in user_content
    assert "No, make it like YouMind. Do not add dependencies." in user_content


@pytest.mark.anyio
async def test_openai_draft_rewriter_streams_plain_text_chunks_in_order():
    provider = FakeCompletionProvider([FakeStream(["Improve ", "the homepage."])])
    manager = DraftSessionManager(rewriter=OpenAIDraftRewriter(provider, model="gpt-test"))
    deltas: list[str] = []

    session = await manager.append_asr_turn(
        raw_text="Improve the homepage.",
        on_text_delta=deltas.append,
    )

    assert provider.calls[0]["stream"] is True
    assert "response_format" not in provider.calls[0]
    assert deltas == ["Improve ", "the homepage."]
    assert session.current_draft is not None
    assert session.current_draft.text == "Improve the homepage."


@pytest.mark.anyio
async def test_openai_draft_rewriter_rejects_empty_model_text():
    provider = FakeCompletionProvider([_text_completion("  \n ")])
    manager = DraftSessionManager(rewriter=OpenAIDraftRewriter(provider, model="gpt-test"))

    with pytest.raises(DraftRewriteInvalidOutput):
        await manager.append_asr_turn(raw_text="Improve the homepage.")


@pytest.mark.anyio
async def test_openai_draft_rewriter_wraps_provider_request_failure():
    provider = FakeCompletionProvider([RuntimeError("provider rejected request")])
    manager = DraftSessionManager(rewriter=OpenAIDraftRewriter(provider, model="gpt-test"))

    with pytest.raises(DraftRewriteUpstreamError, match="Draft cleaner request failed"):
        await manager.append_asr_turn(raw_text="Improve the homepage.")


@pytest.mark.anyio
async def test_default_draft_rewriter_requires_configured_llm():
    manager = DraftSessionManager()

    with pytest.raises(RuntimeError, match="configured LLM provider"):
        await manager.append_asr_turn(raw_text="Improve the homepage.")


@pytest.mark.anyio
async def test_send_freezes_and_next_turn_creates_new_session():
    manager = DraftSessionManager(rewriter=EchoDraftRewriter())
    first = await manager.append_asr_turn(raw_text="Improve the homepage.")
    sent = manager.mark_sent()
    second = await manager.append_asr_turn(raw_text="Actually use YouMind style.")

    assert sent.id == first.id
    assert second.id != sent.id
    assert manager.active_session is second
