import pytest

from tests.conftest import assert_execute_response


@pytest.mark.asyncio
async def test_undefined_variable(client, load_fixture):
    payload = load_fixture("undefined_variable")
    expected = load_fixture("undefined_variable", kind="responses")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert_execute_response(response.json(), expected)


@pytest.mark.asyncio
async def test_exit_failure(client, load_fixture):
    payload = load_fixture("exit_failure")
    expected = load_fixture("exit_failure", kind="responses")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected["status"]
    assert body["error"] is None
