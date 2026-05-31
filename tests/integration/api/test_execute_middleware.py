import json
import logging

import pytest

from tests.conftest import assert_execute_response


@pytest.mark.asyncio
async def test_request_id_echoed(client, load_fixture):
    payload = load_fixture("happy_path")
    response = await client.post(
        "/v1/workflows/execute",
        json=payload,
        headers={"X-Request-ID": "test-req-123"},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "test-req-123"


@pytest.mark.asyncio
async def test_request_id_generated(client, load_fixture):
    payload = load_fixture("happy_path")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_middleware_logs_request_response(client, load_fixture, caplog):
    caplog.set_level(logging.INFO)
    payload = load_fixture("happy_path")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    messages = [r.message for r in caplog.records]
    assert any("HTTP request" in m for m in messages)
    assert any("HTTP response" in m for m in messages)
