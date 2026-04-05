import pytest
from httpx import ASGITransport, AsyncClient

from synopse.api.app import create_app


@pytest.mark.anyio
async def test_sessions_v2_create_and_get_snapshot():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/sessions")
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        snapshot = await client.get(f"/sessions/{session_id}")
        assert snapshot.status_code == 200
        body = snapshot.json()
        assert body["session_id"] == session_id
        assert body["tasks"] == []
