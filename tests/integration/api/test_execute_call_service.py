from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from tests.conftest import assert_execute_response


@pytest.mark.asyncio
@respx.mock
async def test_call_service_success(client, load_fixture):
    respx.post("https://api.example.com/v1/foo").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    payload = load_fixture("call_service_success")
    expected = load_fixture("call_service_success", kind="responses")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert_execute_response(response.json(), expected)


@pytest.mark.asyncio
@respx.mock
async def test_call_service_http_error_no_retry(client):
    route = respx.post("https://api.example.com/v1/foo").mock(
        return_value=httpx.Response(503, json={"err": True})
    )
    payload = {
        "workflow": {
            "schema_version": 1,
            "entry": "fetch",
            "nodes": [
                {
                    "id": "fetch",
                    "action": "call_service",
                    "url": "https://api.example.com/v1/foo",
                    "body": {},
                    "result_variable": "apiResult",
                    "next": "done",
                },
                {"id": "done", "action": "exit", "status": "success"},
            ],
        }
    }
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failure"
    assert body["error"]["code"] == "CALL_SERVICE_HTTP_ERROR"
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_call_service_timeout_retries(client):
    calls = {"n": 0}

    def side_effect(request):
        calls["n"] += 1
        raise httpx.ReadTimeout("timeout")

    respx.post("https://api.example.com/v1/foo").mock(side_effect=side_effect)
    payload = {
        "workflow": {
            "schema_version": 1,
            "entry": "fetch",
            "nodes": [
                {
                    "id": "fetch",
                    "action": "call_service",
                    "url": "https://api.example.com/v1/foo",
                    "body": {},
                    "result_variable": "apiResult",
                    "max_retries": 2,
                    "next": "done",
                },
                {"id": "done", "action": "exit", "status": "success"},
            ],
        }
    }
    with patch("app.infrastructure.http_client.asyncio.sleep", new_callable=AsyncMock):
        response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failure"
    assert body["error"]["code"] == "CALL_SERVICE_TIMEOUT"
    assert calls["n"] == 3
