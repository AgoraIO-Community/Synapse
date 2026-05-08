import pytest
from httpx import ASGITransport, AsyncClient

from newbro.api.app import create_app
from newbro.api.auth import StaticCloudflareAccessVerifier, encode_test_access_token
from newbro.runtime import Settings
from tests.helpers.asgi_websocket import ASGIWebSocketSession


@pytest.mark.anyio
async def test_api_rejects_unauthenticated_requests_when_auth_required():
    app = create_app(
        settings=Settings(
            api_auth_required=True,
            api_bearer_token="test-token",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/sessions")

    assert response.status_code == 401


@pytest.mark.anyio
async def test_api_accepts_bearer_token_when_auth_required():
    app = create_app(
        settings=Settings(
            api_auth_required=True,
            api_bearer_token="test-token",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/sessions",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.json()["session_id"]


@pytest.mark.anyio
async def test_api_accepts_cloudflare_access_jwt():
    audience = "aud-123"
    app = create_app(
        settings=Settings(
            api_auth_required=True,
            cloudflare_access_team_domain="example.cloudflareaccess.com",
            cloudflare_access_audience=audience,
        )
    )
    app.state.cloudflare_access_verifier = StaticCloudflareAccessVerifier(audience=audience)
    token = encode_test_access_token(audience=audience, subject="user-1", email="user@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/sessions",
            headers={"Cf-Access-Jwt-Assertion": token},
        )

    assert response.status_code == 200
    assert response.json()["session_id"]


@pytest.mark.anyio
async def test_session_stream_rejects_unauthenticated_websocket_when_auth_required():
    app = create_app(
        settings=Settings(
            api_auth_required=True,
            api_bearer_token="test-token",
        )
    )
    app.state.runtime_container.create_session()
    session_id = next(iter(app.state.runtime_container._sessions.keys()))

    with pytest.raises(RuntimeError, match="4401"):
        async with ASGIWebSocketSession(app, f"/api/sessions/{session_id}/stream"):
            pass
