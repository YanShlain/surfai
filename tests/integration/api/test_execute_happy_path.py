import pytest

from tests.conftest import assert_execute_response


@pytest.mark.asyncio
async def test_happy_path(client, load_fixture):
    payload = load_fixture("happy_path")
    expected = load_fixture("happy_path", kind="responses")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert_execute_response(response.json(), expected)


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
