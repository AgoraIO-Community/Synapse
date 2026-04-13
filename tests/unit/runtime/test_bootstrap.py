from synapse.communication.models import OpenAICommunicationModel, ScriptedCommunicationModel
from synapse.runtime import Settings, build_runtime_container
from synapse.runtime import bootstrap as bootstrap_module


class FakeProvider:
    async def run_tool_calling(self, **kwargs):
        raise AssertionError("Should not be called in bootstrap test")


def test_bootstrap_uses_scripted_fallback_without_openai():
    container = build_runtime_container(
        settings=Settings(communication_backend="auto", openai_api_key=None)
    )
    assert isinstance(container.communication_model, ScriptedCommunicationModel)


def test_bootstrap_uses_openai_model_when_key_present():
    container = build_runtime_container(
        settings=Settings(communication_backend="auto", openai_api_key="test-key"),
        provider=FakeProvider(),
    )
    assert isinstance(container.communication_model, OpenAICommunicationModel)


def test_bootstrap_fails_when_codex_is_enabled_but_missing(monkeypatch):
    monkeypatch.setattr(bootstrap_module, "_codex_command_available", lambda command: False)

    try:
        build_runtime_container(
            settings=Settings(codex_executor_enabled=True, codex_command="missing-codex"),
        )
    except RuntimeError as exc:
        assert "missing-codex" in str(exc)
    else:
        raise AssertionError("Expected bootstrap to fail for missing codex command.")
