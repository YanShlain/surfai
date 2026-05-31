import json
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from app.config import Settings
from app.dependencies import AppContainer, build_container
from app.main import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        workflow_fs_root=str(tmp_path),
        call_service_timeout_seconds=0.1,
        call_service_max_timeout_seconds=60.0,
        call_service_max_retries=3,
        call_service_retry_base_seconds=0.01,
        call_service_retry_max_seconds=0.05,
        call_service_max_retries_cap=5,
    )


@pytest.fixture
def container(settings: Settings) -> AppContainer:
    return build_container(settings)


@pytest.fixture
def app(container: AppContainer):
    return create_app(container=container)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def load_fixture():
    def _load(name: str, kind: str = "workflows") -> dict:
        path = FIXTURES_DIR / kind / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return _load


def assert_execute_response(actual: dict, expected: dict) -> None:
    assert actual["status"] == expected["status"]
    if "variables" in expected:
        assert actual["variables"] == expected["variables"]
    if "prints" in expected:
        assert actual["prints"] == expected["prints"]
    if "error" in expected:
        if expected["error"] is None:
            assert actual["error"] is None
        else:
            assert actual["error"] is not None
            for key in ("code", "message", "step_id", "action"):
                if key in expected["error"]:
                    assert actual["error"][key] == expected["error"][key]
