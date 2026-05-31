import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.domain.errors import CallServiceError
from app.domain.models import WorkflowError
from app.infrastructure.retry_policy import compute_backoff_sleep

logger = logging.getLogger(__name__)


@dataclass
class ExternalRestHttpClient:
    settings: Settings
    client: httpx.AsyncClient | None = None

    async def post_json(
        self,
        url: str,
        body: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        per_attempt_timeout = timeout_seconds or self.settings.call_service_timeout_seconds
        extra_retries = (
            max_retries
            if max_retries is not None
            else self.settings.call_service_max_retries
        )
        max_attempts = 1 + extra_retries

        own_client = self.client is None
        client = self.client or httpx.AsyncClient()

        try:
            for attempt in range(1, max_attempts + 1):
                try:
                    response = await client.post(
                        url,
                        json=body,
                        timeout=per_attempt_timeout,
                    )
                except httpx.TimeoutException as exc:
                    if attempt >= max_attempts:
                        raise CallServiceError(
                            WorkflowError(
                                code="CALL_SERVICE_TIMEOUT",
                                message=(
                                    f"External call timed out after {max_attempts} "
                                    f"attempts ({per_attempt_timeout}s per attempt)"
                                ),
                                action="call_service",
                                cause=f"{type(exc).__name__}; retries exhausted",
                            )
                        ) from exc
                    sleep_seconds = compute_backoff_sleep(
                        attempt,
                        base_seconds=self.settings.call_service_retry_base_seconds,
                        max_seconds=self.settings.call_service_retry_max_seconds,
                    )
                    logger.warning(
                        "call_service retry after timeout",
                        extra={
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "sleep_seconds": sleep_seconds,
                            "url": url,
                        },
                    )
                    await asyncio.sleep(sleep_seconds)
                    continue
                except httpx.RequestError as exc:
                    raise CallServiceError(
                        WorkflowError(
                            code="CALL_SERVICE_CONNECTION_ERROR",
                            message=f"Could not connect to {url}",
                            action="call_service",
                            cause=str(exc),
                        )
                    ) from exc

                if not (200 <= response.status_code < 300):
                    raise CallServiceError(
                        WorkflowError(
                            code="CALL_SERVICE_HTTP_ERROR",
                            message=f"External API returned {response.status_code}",
                            action="call_service",
                            cause=f"HTTP {response.status_code}",
                        )
                    )

                content_type = response.headers.get("content-type", "")
                if "application/json" not in content_type:
                    try:
                        return response.json()
                    except json.JSONDecodeError as exc:
                        raise CallServiceError(
                            WorkflowError(
                                code="CALL_SERVICE_INVALID_RESPONSE",
                                message="Response is not valid JSON",
                                action="call_service",
                                cause=str(exc),
                            )
                        ) from exc

                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    raise CallServiceError(
                        WorkflowError(
                            code="CALL_SERVICE_INVALID_RESPONSE",
                            message="Response is not valid JSON",
                            action="call_service",
                            cause=str(exc),
                        )
                    ) from exc

                if not isinstance(data, dict):
                    raise CallServiceError(
                        WorkflowError(
                            code="CALL_SERVICE_INVALID_RESPONSE",
                            message="Response is not valid JSON",
                            action="call_service",
                            cause="expected JSON object",
                        )
                    )
                return data

            raise RuntimeError("unreachable")
        finally:
            if own_client:
                await client.aclose()
