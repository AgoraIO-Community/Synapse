import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.runtime import Settings


@pytest.mark.anyio
async def test_app_adds_cors_headers_for_configured_origins():
    app = create_app(
        settings=Settings(
            cors_allowed_origins=("https://synapse-ui.vercel.app",),
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.options(
            "/sessions",
            headers={
                "Origin": "https://synapse-ui.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://synapse-ui.vercel.app"


@pytest.mark.anyio
async def test_app_does_not_serve_frontend_routes():
    app = create_app(settings=Settings())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        root_response = await client.get("/")
        asset_response = await client.get("/assets/app.js")
        gateway_response = await client.get("/gateway/agora-convoai/config")

    assert root_response.status_code == 404
    assert asset_response.status_code == 404
    assert gateway_response.status_code == 404
