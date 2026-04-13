from __future__ import annotations

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient
import websockets

from synapse.gateway_host.app import create_app
from synapse.gateway_host.config import GatewayHostSettings
from synapse.gateways.base.transport import HttpSynapseGatewayTransport
from synapse.gateways.agora_convoai.module import create_headless_app
from synapse.gateways.agora_convoai.service import AgoraSDKConvoAIService
from synapse.gateways.agora_convoai.settings import AgoraConvoAIGatewaySettings


@pytest.mark.anyio
async def test_gateway_host_mounts_enabled_module_routes():
    app = create_app(
        GatewayHostSettings(
            enabled=True,
            enabled_gateways=["agora-convoai"],
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/gateway/agora-convoai/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["implementation_version"] == "agora-convoai-gateway.v1"
    assert "agora_agent:Agent" in payload["sdk_loader_signature"]
    assert payload["upstream_transport_mode"] == "direct"


@pytest.mark.anyio
async def test_gateway_host_skips_disabled_module_routes():
    app = create_app(
        GatewayHostSettings(
            enabled=False,
            enabled_gateways=["agora-convoai"],
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        health_response = await client.get("/health")
        response = await client.get("/gateway/agora-convoai/health")

    assert health_response.status_code == 200
    assert health_response.json()["enabled"] is False
    assert health_response.json()["gateways"] == ["agora-convoai"]
    assert response.status_code == 404


def test_http_synapse_gateway_transport_disables_proxy_env():
    transport = HttpSynapseGatewayTransport("http://127.0.0.1:8000")
    try:
        assert transport._http._trust_env is False
    finally:
        asyncio.run(transport.close())


@pytest.mark.anyio
async def test_http_synapse_gateway_transport_passes_proxy_none_to_websockets(monkeypatch):
    captured: list[dict[str, object]] = []

    class FakeWebSocket:
        def __init__(self) -> None:
            self._messages = [
                json.dumps({"type": "snapshot"}),
                json.dumps({"type": "assistant_response_started", "request_id": "req-1"}),
                json.dumps(
                    {
                        "type": "assistant_response_completed",
                        "request_id": "req-1",
                        "reply_text": "Done.",
                    }
                ),
            ]

        async def recv(self):
            return self._messages.pop(0)

        async def send(self, _message: str):
            return None

    class FakeConnect:
        async def __aenter__(self):
            return FakeWebSocket()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_connect(uri, **kwargs):
        captured.append({"uri": uri, **kwargs})
        return FakeConnect()

    monkeypatch.setattr(websockets, "connect", fake_connect)

    transport = HttpSynapseGatewayTransport("http://127.0.0.1:8000")
    try:
        events = []
        async for event in transport.stream_message("session-1", "hello", request_id="req-1"):
            events.append(event)
        assert events[-1]["type"] == "assistant_response_completed"

        notifications = transport.watch_notification_texts("session-1")
        await notifications.aclose()
    finally:
        await transport.close()

    assert captured
    assert all(item["proxy"] is None for item in captured)


@pytest.mark.anyio
async def test_agora_gateway_prepare_route_uses_real_loader_path_before_fake_sdk(monkeypatch):
    class FakeAsyncAgora:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def select_best_domain(self):
            return None

        def get_current_url(self):
            return "https://fake-convoai.local/api"

    class FakeArea:
        US = "US"

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def with_stt(self, _vendor):
            return self

        def with_llm(self, _vendor):
            return self

        def with_tts(self, _vendor):
            return self

    class FakeAdvancedFeatures:
        def __init__(self, **kwargs):
            self.enable_rtm = kwargs.get("enable_rtm")

    class FakeSessionParams:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.data_channel = kwargs.get("data_channel")
            self.enable_metrics = kwargs.get("enable_metrics")
            self.enable_error_message = kwargs.get("enable_error_message")

    monkeypatch.setattr(
        AgoraSDKConvoAIService,
        "_load_sdk_types",
        lambda self: (
            FakeAsyncAgora,
            FakeArea,
            FakeAgent,
            object,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
            FakeAdvancedFeatures,
            FakeSessionParams,
        ),
    )

    app = create_headless_app(
        AgoraConvoAIGatewaySettings(
            app_id="agora-app",
            app_certificate="app-certificate",
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/gateway/agora-convoai/sessions/prepare",
            json={
                "profile": "VOICE",
                "channel_name": "demo-room",
                "display_name": "Tester",
                "user_uid": 101,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["prepared_session_id"].startswith("prepared-")
    assert payload["app_id"] == "agora-app"
    assert payload["channel_name"] == "demo-room"


@pytest.mark.anyio
async def test_agora_gateway_activate_ignores_proxy_env_for_synapse_upstream(monkeypatch):
    class FakeTransport:
        def __init__(
            self,
            base_url: str,
            *,
            request_timeout_seconds: float = 10.0,
        ) -> None:
            self.base_url = base_url
            self.request_timeout_seconds = request_timeout_seconds
            self.created = 0

        async def create_session(self) -> str:
            self.created += 1
            return "session-1234"

        async def send_message(self, session_id: str, text: str):
            raise AssertionError("send_message should not be called during activate")

        async def stream_message(self, session_id: str, text: str, *, request_id: str):
            if False:
                yield None

        async def watch_notification_texts(self, session_id: str):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    class FakeAsyncAgora:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def select_best_domain(self):
            return None

        def get_current_url(self):
            return "https://fake-convoai.local/api"

    class FakeArea:
        US = "US"

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def with_stt(self, _vendor):
            return self

        def with_llm(self, _vendor):
            return self

        def with_tts(self, _vendor):
            return self

    class FakeAsyncAgentSession:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def start(self):
            return "runtime-session-1"

    class FakeAdvancedFeatures:
        def __init__(self, **kwargs):
            self.enable_rtm = kwargs.get("enable_rtm")

    class FakeSessionParams:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.data_channel = kwargs.get("data_channel")
            self.enable_metrics = kwargs.get("enable_metrics")
            self.enable_error_message = kwargs.get("enable_error_message")

    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:9999")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:9999")
    monkeypatch.setattr(
        "synapse.gateways.agora_convoai.module.HttpSynapseGatewayTransport",
        FakeTransport,
    )
    monkeypatch.setattr(
        AgoraSDKConvoAIService,
        "_load_sdk_types",
        lambda self: (
            FakeAsyncAgora,
            FakeArea,
            FakeAgent,
            FakeAsyncAgentSession,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
            lambda **kwargs: None,
            FakeAdvancedFeatures,
            FakeSessionParams,
        ),
    )

    app = create_headless_app(
        AgoraConvoAIGatewaySettings(
            synapse_base_url="http://127.0.0.1:8000",
            app_id="agora-app",
            app_certificate="app-certificate",
            convoai_area="US",
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        prepared = await client.post(
            "/gateway/agora-convoai/sessions/prepare",
            json={
                "profile": "VOICE",
                "channel_name": "demo-room",
                "display_name": "Tester",
                "user_uid": 101,
            },
        )
        assert prepared.status_code == 200
        prepared_session_id = prepared.json()["prepared_session_id"]

        activated = await client.post(
            "/gateway/agora-convoai/sessions/activate",
            json={"prepared_session_id": prepared_session_id},
        )

    assert activated.status_code == 200
    payload = activated.json()
    assert payload["binding_id"].startswith("binding-")
    assert payload["synapse_session_id"] == "session-1234"
    assert payload["runtime_session_id"] == "runtime-session-1"
