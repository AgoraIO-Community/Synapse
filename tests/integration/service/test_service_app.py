from __future__ import annotations

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

import synapse.connectors.host.app as connector_host_app_module
from synapse.connectors.host.config import ConnectorHostSettings
from synapse.connectors.base import BaseConnectorModule, ConnectorModuleRegistry
from synapse.runtime import Settings
from synapse.service.app import create_app

from tests.helpers.asgi_websocket import ASGIWebSocketSession


class FakeConnectorModule(BaseConnectorModule):
    slug = "agora-convoai"

    def build_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/connectors/agora-convoai/config")
        async def config() -> dict[str, object]:
            return {"ready": True, "service_base_url": "http://127.0.0.1:8000"}

        return router


@pytest.mark.anyio
async def test_service_app_serves_frontend_routes_and_preserves_api_routes(tmp_path):
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><body>Workbench</body></html>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")

    app = create_app(
        settings=Settings(),
        frontend_dist=dist_dir,
        connector_settings=ConnectorHostSettings(enabled=False),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        root_response = await client.get("/")
        asset_response = await client.get("/assets/app.js")
        spa_response = await client.get("/workbench/tasks")
        health_response = await client.get("/health")
        connector_response = await client.get("/connectors/agora-convoai/config")

    assert root_response.status_code == 200
    assert "Workbench" in root_response.text
    assert asset_response.status_code == 200
    assert "console.log('ok');" in asset_response.text
    assert spa_response.status_code == 200
    assert "Workbench" in spa_response.text
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert connector_response.status_code == 404


@pytest.mark.anyio
async def test_service_app_mounts_enabled_connector_routes(monkeypatch, tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    monkeypatch.setattr(
        connector_host_app_module,
        "create_connector_module_registry",
        lambda _enabled_modules: ConnectorModuleRegistry(modules=[FakeConnectorModule()]),
    )

    app = create_app(
        settings=Settings(),
        frontend_dist=dist_dir,
        connector_settings=ConnectorHostSettings(
            enabled=True,
            public_base_url="http://127.0.0.1:8000",
            synapse_base_url="http://127.0.0.1:8000",
            enabled_connectors=["agora-convoai"],
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/connectors/agora-convoai/config")

    assert response.status_code == 200
    assert response.json() == {"ready": True, "service_base_url": "http://127.0.0.1:8000"}


@pytest.mark.anyio
async def test_service_app_keeps_session_stream_and_executor_control_websockets(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    app = create_app(
        settings=Settings(detached_executor_enabled=True),
        frontend_dist=dist_dir,
        connector_settings=ConnectorHostSettings(enabled=False),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]

        async with ASGIWebSocketSession(app, f"/sessions/{session_id}/stream") as websocket:
            initial_event = await websocket.receive_json()
            assert initial_event["type"] == "snapshot"

        async with ASGIWebSocketSession(app, "/executors/control") as websocket:
            await websocket.send_json(
                {
                    "type": "register_node",
                    "node_id": "node-1",
                    "executors": [
                        {
                            "executor_type": "codex",
                            "supports_resume": True,
                            "supports_follow_up": True,
                            "supports_pause": True,
                            "supports_cancel": True,
                        }
                    ],
                }
            )
            ack = await websocket.receive_json()

    assert ack["type"] == "ack"
    assert ack["detail"] == "registered"
