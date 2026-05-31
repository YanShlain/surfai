import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import Settings
from app.domain.errors import CallServiceError
from app.infrastructure.http_client import ExternalRestHttpClient


@pytest.fixture
def settings():
    return Settings(
        workflow_fs_root=".",
        call_service_timeout_seconds=1.0,
        call_service_max_timeout_seconds=60,
        call_service_max_retries=2,
        call_service_retry_base_seconds=0.01,
        call_service_retry_max_seconds=0.05,
        call_service_max_retries_cap=5,
    )


async def test_success_no_retry(settings):
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})
    ))
    http = ExternalRestHttpClient(settings=settings, client=client)
    result = await http.post_json("https://example.com", {})
    assert result == {"ok": True}
    await client.aclose()


async def test_http_error_not_retried(settings):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, json={"err": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    http = ExternalRestHttpClient(settings=settings, client=client)
    with pytest.raises(CallServiceError) as exc:
        await http.post_json("https://example.com", {})
    assert exc.value.error.code == "CALL_SERVICE_HTTP_ERROR"
    assert calls["n"] == 1
    await client.aclose()


async def test_timeout_retried_then_fails(settings):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ReadTimeout("timeout")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    http = ExternalRestHttpClient(settings=settings, client=client)
    with patch("app.infrastructure.http_client.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(CallServiceError) as exc:
            await http.post_json("https://example.com", {}, max_retries=2)
    assert exc.value.error.code == "CALL_SERVICE_TIMEOUT"
    assert calls["n"] == 3
    await client.aclose()


async def test_timeout_then_success(settings):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    http = ExternalRestHttpClient(settings=settings, client=client)
    with patch("app.infrastructure.http_client.asyncio.sleep", new_callable=AsyncMock):
        result = await http.post_json("https://example.com", {}, max_retries=3)
    assert result == {"ok": True}
    assert calls["n"] == 3
    await client.aclose()


async def test_connection_error(settings):
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: (_ for _ in ()).throw(httpx.ConnectError("refused"))
    ))
    http = ExternalRestHttpClient(settings=settings, client=client)
    with pytest.raises(CallServiceError) as exc:
        await http.post_json("https://example.com", {})
    assert exc.value.error.code == "CALL_SERVICE_CONNECTION_ERROR"
    await client.aclose()
