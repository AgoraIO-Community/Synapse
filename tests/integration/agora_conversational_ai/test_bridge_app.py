import asyncio

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from examples.agora_conversational_ai import settings as example_settings_module
from examples.agora_conversational_ai.app import create_app
from examples.agora_conversational_ai.bridge import BridgeRegistry
from examples.agora_conversational_ai.convoai_service import (
    ActivatedConvoAISession,
    AgoraSDKConvoAIService,
    ConvoAIRuntimeError,
    PreparedConvoAISession,
)
from examples.agora_conversational_ai.frontend_adapter import FrontendSessionService
from examples.agora_conversational_ai.models import FrontendSessionDiagnostics
from examples.agora_conversational_ai.settings import AgoraBridgeSettings
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan
from synopse.protocol import Task, TaskStatus, TaskSummary
from synopse.runtime import RuntimeContainer, Settings
from synopse.runtime import config as runtime_config_module


class FakeConvoAIService:
    def __init__(self) -> None:
        self.prepare_calls: list[dict[str, object]] = []
        self.activate_calls: list[str] = []
        self.stop_calls: list[str] = []
        self.speak_calls: list[dict[str, object]] = []
        self.prepared = PreparedConvoAISession(
            prepared_session_id="prepared-1234",
            app_id="agora-app",
            channel_name="demo-room",
            token="combined-token",
            uid=101,
            user_rtm_uid="101-demo-room",
            agent_uid="9001",
            agent_rtm_uid="9001-demo-room",
            enable_string_uid=False,
            profile="VOICE",
            display_name="Synopse Tester",
            diagnostics=FrontendSessionDiagnostics(
                convoai_area="CN",
                selected_url="https://api-cn-test.agora.io/api/conversational-ai-agent",
                runtime_agent_id=None,
                agent_uid="9001",
                agent_rtm_uid="9001-demo-room",
                rtc_uid=101,
                rtm_user_id="101-demo-room",
                enable_string_uid=False,
                enable_rtm=True,
                data_channel="rtm",
                enable_metrics=True,
                enable_error_message=True,
            ),
        )
        self.activated = ActivatedConvoAISession(
            prepared_session_id="prepared-1234",
            runtime_agent_id="runtime-agent-1",
            app_id="agora-app",
            channel_name="demo-room",
            token="combined-token",
            uid=101,
            user_rtm_uid="101-demo-room",
            agent_uid="9001",
            agent_rtm_uid="9001-demo-room",
            enable_string_uid=False,
            profile="VOICE",
            display_name="Synopse Tester",
            diagnostics=FrontendSessionDiagnostics(
                convoai_area="CN",
                selected_url="https://api-cn-test.agora.io/api/conversational-ai-agent",
                runtime_agent_id="runtime-agent-1",
                agent_uid="9001",
                agent_rtm_uid="9001-demo-room",
                rtc_uid=101,
                rtm_user_id="101-demo-room",
                enable_string_uid=False,
                enable_rtm=True,
                data_channel="rtm",
                enable_metrics=True,
                enable_error_message=True,
            ),
        )
        self.stop_error: ConvoAIRuntimeError | None = None

    async def prepare_session(
        self,
        *,
        profile: str,
        channel_name: str,
        display_name: str | None,
        user_id: str | None,
    ) -> PreparedConvoAISession:
        self.prepare_calls.append(
            {
                "profile": profile,
                "channel_name": channel_name,
                "display_name": display_name,
                "user_id": user_id,
            }
        )
        return self.prepared

    async def activate_session(self, prepared_session_id: str) -> ActivatedConvoAISession:
        self.activate_calls.append(prepared_session_id)
        return self.activated

    async def stop_session(self, runtime_agent_id: str) -> None:
        self.stop_calls.append(runtime_agent_id)
        if self.stop_error is not None:
            raise self.stop_error

    async def speak(self, runtime_agent_id: str, text: str) -> None:
        self.speak_calls.append(
            {
                "runtime_agent_id": runtime_agent_id,
                "text": text,
            }
        )


async def _wait_for(predicate, timeout: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for expected condition.")
        await asyncio.sleep(0.01)


def test_example_env_configuration_points_runtime_loader_at_example_env(tmp_path, monkeypatch):
    example_env = tmp_path / ".env.local"
    example_env.write_text("OPENAI_API_KEY=example-key\n", encoding="utf-8")
    monkeypatch.setattr(example_settings_module, "EXAMPLE_LOCAL_ENV_FILE", example_env)
    monkeypatch.setattr(runtime_config_module, "LOCAL_ENV_FILE", tmp_path / "repo.env.local")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    example_settings_module.configure_example_env()
    runtime_config_module.load_local_env()

    assert runtime_config_module.LOCAL_ENV_FILE == example_env


def test_real_agora_sdk_vendor_constructors_accept_current_option_names():
    from agora_agent.agentkit import DeepgramSTT, ElevenLabsTTS, OpenAI

    DeepgramSTT(api_key="deepgram-key", language="en-US")
    OpenAI(api_key="openai-key", model="gpt-4o-mini")
    ElevenLabsTTS(
        key="elevenlabs-key",
        voice_id="voice-id",
        model_id="eleven_flash_v2_5",
        sample_rate=24000,
    )


def test_convoai_area_defaults_to_cn():
    settings = AgoraBridgeSettings()
    assert settings.convoai_area == "CN"


@pytest.mark.anyio
async def test_local_convoai_service_prepare_uses_official_identity_model(monkeypatch):
    created: dict[str, object] = {}

    class FakeAsyncAgora:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.selected_best_domain = False

        async def select_best_domain(self):
            self.selected_best_domain = True

        def get_current_url(self):
            return "https://fake-convoai.local/api"

    class FakeArea:
        CN = "CN"

    class FakeAgent:
        def __init__(self, **kwargs):
            created["agent_kwargs"] = kwargs

        def with_stt(self, vendor):
            self.stt = vendor
            return self

        def with_llm(self, vendor):
            self.llm = vendor
            return self

        def with_tts(self, vendor):
            self.tts = vendor
            return self

    class FakeDeepgramSTT:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeElevenLabsTTS:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeAdvancedFeatures:
        def __init__(self, **kwargs):
            self.enable_rtm = kwargs.get("enable_rtm")

    class FakeSessionParams:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.data_channel = kwargs.get("data_channel")
            self.enable_metrics = kwargs.get("enable_metrics")
            self.enable_error_message = kwargs.get("enable_error_message")

    settings = _build_settings()
    service = AgoraSDKConvoAIService(settings)
    monkeypatch.setattr(
        service,
        "_load_sdk_types",
        lambda: (
            FakeAsyncAgora,
            FakeArea,
            FakeAgent,
            object,
            FakeDeepgramSTT,
            FakeOpenAI,
            FakeElevenLabsTTS,
            FakeAdvancedFeatures,
            FakeSessionParams,
        ),
    )

    prepared = await service.prepare_session(
        profile="VOICE",
        channel_name="demo-room",
        display_name="Tester",
        user_id="101",
    )

    assert prepared.uid == 101
    assert prepared.user_rtm_uid == "101-demo-room"
    assert prepared.agent_uid == "9001"
    assert prepared.agent_rtm_uid == "9001-demo-room"
    assert prepared.enable_string_uid is False
    assert prepared.diagnostics is not None
    assert prepared.diagnostics.agent_rtm_uid == "9001-demo-room"
    assert created["agent_kwargs"]["advanced_features"].enable_rtm is True
    assert created["agent_kwargs"]["parameters"].data_channel == "rtm"
    assert created["agent_kwargs"]["parameters"].enable_metrics is True
    assert created["agent_kwargs"]["parameters"].enable_error_message is True
    assert created["agent_kwargs"]["parameters"].kwargs["transcript"]["enable"] is True
    assert created["agent_kwargs"]["parameters"].kwargs["enable_dump"] is True


@pytest.mark.anyio
async def test_local_convoai_service_activate_wraps_connect_error(monkeypatch):
    class FakeAsyncAgora:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def select_best_domain(self):
            return None

        def get_current_url(self):
            return "https://api-cn-test.agora.io/api/conversational-ai-agent"

        class agents:
            @staticmethod
            async def start(*args, **kwargs):
                raise httpx.ConnectError("connect failed")

    class FakeArea:
        CN = "CN"

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

        def with_stt(self, vendor):
            return self

        def with_llm(self, vendor):
            return self

        def with_tts(self, vendor):
            return self

    class FakeAsyncAgentSession:
        def __init__(self, **kwargs):
            pass

        async def start(self):
            raise httpx.ConnectError("connect failed")

    settings = _build_settings(convoai_area="CN")
    service = AgoraSDKConvoAIService(settings)
    monkeypatch.setattr(
        service,
        "_load_sdk_types",
        lambda: (
            FakeAsyncAgora,
            FakeArea,
            FakeAgent,
            FakeAsyncAgentSession,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
        ),
    )
    prepared = await service.prepare_session(
        profile="VOICE",
        channel_name="demo-room",
        display_name="Tester",
        user_id="101",
    )

    with pytest.raises(ConvoAIRuntimeError) as exc_info:
        await service.activate_session(prepared.prepared_session_id)

    message = str(exc_info.value)
    assert "api-cn-test.agora.io" in message
    assert "CN" in message


def _build_settings(**overrides) -> AgoraBridgeSettings:
    base = AgoraBridgeSettings(
        service_base_url="http://testserver",
        default_app_id="agora-app",
        app_certificate="app-certificate",
        openai_api_key="openai-key",
        deepgram_api_key="deepgram-key",
        elevenlabs_api_key="elevenlabs-key",
        elevenlabs_voice_id="voice-id",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _build_app(
    reply_text: str = "Bridge reply.",
    *,
    bridge_settings: AgoraBridgeSettings | None = None,
    convoai_service: FakeConvoAIService | None = None,
):
    runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="model_reply",
                    reply_override=reply_text,
                )
            }
        ),
        settings=Settings(),
    )
    bridge_settings = bridge_settings or _build_settings()
    convoai_service = convoai_service or FakeConvoAIService()
    bridge_registry = BridgeRegistry(runtime_container, speaker=convoai_service)
    frontend_service = FrontendSessionService(
        bridge_registry,
        bridge_settings,
        convoai_service=convoai_service,
    )
    app = create_app(
        runtime_container=runtime_container,
        bridge_settings=bridge_settings,
        bridge_registry=bridge_registry,
        frontend_service=frontend_service,
    )
    return app, convoai_service


@pytest.mark.anyio
async def test_frontend_config_reports_ready_defaults():
    app, _ = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/frontend/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["defaults"]["profile"] == "VOICE"
    assert payload["defaults"]["channel_name"] == "synopse-voice-demo"
    assert payload["service_base_url"] == "http://testserver"


@pytest.mark.anyio
async def test_prepare_returns_official_sample_like_bootstrap():
    app, convoai_service = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/frontend/session/prepare",
            json={
                "profile": "VOICE",
                "channel_name": "demo-room",
                "display_name": "Tester",
                "user_id": "101",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["prepared_session_id"] == "prepared-1234"
    assert payload["app_id"] == "agora-app"
    assert payload["channel_name"] == "demo-room"
    assert payload["token"] == "combined-token"
    assert payload["uid"] == 101
    assert payload["user_rtm_uid"] == "101-demo-room"
    assert payload["agent"]["uid"] == "9001"
    assert payload["agent_rtm_uid"] == "9001-demo-room"
    assert payload["enable_string_uid"] is False
    assert convoai_service.prepare_calls == [
        {
            "profile": "VOICE",
            "channel_name": "demo-room",
            "display_name": "Tester",
            "user_id": "101",
        }
    ]


@pytest.mark.anyio
async def test_activate_returns_bridge_payload_and_chat_completion_works():
    app, convoai_service = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        prepared = await client.post(
            "/frontend/session/prepare",
            json={"channel_name": "demo-room", "user_id": "101"},
        )
        activated = await client.post(
            "/frontend/session/activate",
            json={"prepared_session_id": prepared.json()["prepared_session_id"]},
        )
        payload = activated.json()
        response = await client.post(
            f"/chat/completions?bridge_session_id={payload['bridge_session_id']}",
            json={
                "model": "synopse-agora-bridge",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert activated.status_code == 200
    assert payload["runtime_agent_id"] == "runtime-agent-1"
    assert payload["bridge_session_id"].startswith("bridge-")
    assert payload["synopse_session_id"].startswith("session-")
    assert payload["agent"]["uid"] == "9001"
    assert payload["agent_rtm_uid"] == "9001-demo-room"
    assert payload["user_rtm_uid"] == "101-demo-room"
    assert convoai_service.activate_calls == ["prepared-1234"]
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Bridge reply."


@pytest.mark.anyio
async def test_notification_events_trigger_local_speak():
    app, convoai_service = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        prepared = await client.post(
            "/frontend/session/prepare",
            json={"channel_name": "demo-room", "user_id": "101"},
        )
        activated = await client.post(
            "/frontend/session/activate",
            json={"prepared_session_id": prepared.json()["prepared_session_id"]},
        )
        session_id = activated.json()["synopse_session_id"]

        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-input",
                root_task_id="task-input",
                title="Input task",
                goal="Input task",
                status=TaskStatus.CREATED,
            )
        )
        await session.blackboard.put_summary(
            TaskSummary(
                task_id="task-input",
                conversational_summary="I need one more detail from you.",
                latest_user_visible_status="waiting_user_input",
                needs_user_input=True,
            )
        )

        await _wait_for(lambda: len(convoai_service.speak_calls) == 1)

    assert convoai_service.speak_calls == [
        {
            "runtime_agent_id": "runtime-agent-1",
            "text": "I need one more detail from you.",
        }
    ]


@pytest.mark.anyio
async def test_frontend_stop_unregisters_bridge_and_stops_local_session():
    app, convoai_service = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        prepared = await client.post(
            "/frontend/session/prepare",
            json={"channel_name": "demo-room", "user_id": "101"},
        )
        activated = await client.post(
            "/frontend/session/activate",
            json={"prepared_session_id": prepared.json()["prepared_session_id"]},
        )
        bridge_session_id = activated.json()["bridge_session_id"]

        stopped = await client.post(
            "/frontend/session/stop",
            json={"bridge_session_id": bridge_session_id},
        )
        lookup = await client.post(
            f"/chat/completions?bridge_session_id={bridge_session_id}",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

    assert stopped.status_code == 200
    assert convoai_service.stop_calls == ["runtime-agent-1"]
    assert lookup.status_code == 404
