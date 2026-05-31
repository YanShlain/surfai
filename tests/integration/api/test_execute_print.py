import pytest

from tests.conftest import assert_execute_response


@pytest.mark.asyncio
async def test_multipart_print(client, load_fixture):
    payload = load_fixture("print_multipart")
    expected = load_fixture("print_multipart", kind="responses")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert_execute_response(response.json(), expected)
