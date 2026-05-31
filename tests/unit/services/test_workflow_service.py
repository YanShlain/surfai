import pytest

from app.config import Settings
from app.domain.models import ExitNode, SetVariableNode, WorkflowDefinition
from app.services.executor import WorkflowExecutor
from app.services.validator import WorkflowValidator
from app.services.workflow_service import WorkflowService


class FakeFileReader:
    def read_text(self, relative_path: str) -> str:
        return ""

    def exists(self, relative_path: str) -> bool:
        return False


class FakeHttpClient:
    async def post_json(self, url, body, *, timeout_seconds=None, max_retries=None):
        return {}


@pytest.fixture
def service():
    settings = Settings(
        workflow_fs_root=".",
        call_service_timeout_seconds=10,
        call_service_max_timeout_seconds=60,
        call_service_max_retries=3,
        call_service_retry_base_seconds=0.5,
        call_service_retry_max_seconds=30,
        call_service_max_retries_cap=5,
    )
    validator = WorkflowValidator(settings=settings)
    executor = WorkflowExecutor(
        file_reader=FakeFileReader(),
        http_client=FakeHttpClient(),
    )
    return WorkflowService(validator=validator, executor=executor)


async def test_validation_failure_short_circuits(service):
    wf = WorkflowDefinition(
        schema_version=2,
        entry="a",
        nodes=(ExitNode("a", "exit", "success"),),
    )
    result = await service.run(wf)
    assert result.status == "failure"
    assert result.error.code == "INVALID_SCHEMA_VERSION"


async def test_valid_workflow_executes(service):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            SetVariableNode("a", "set_variable", "x", 1, "b"),
            ExitNode("b", "exit", "success"),
        ),
    )
    result = await service.run(wf)
    assert result.status == "success"
    assert result.variables == {"x": 1}
