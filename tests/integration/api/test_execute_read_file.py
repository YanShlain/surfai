import pytest

from tests.conftest import assert_execute_response


@pytest.mark.asyncio
async def test_read_file_success(client, load_fixture, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.json").write_text('{"ok": true}', encoding="utf-8")

    payload = load_fixture("read_file")
    expected = load_fixture("read_file", kind="responses")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert_execute_response(response.json(), expected)


@pytest.mark.asyncio
async def test_path_traversal_rejected(client, load_fixture):
    payload = load_fixture("read_file_traversal")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failure"
    assert body["error"]["code"] == "PATH_NOT_ALLOWED"
