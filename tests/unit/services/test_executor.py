import json
from dataclasses import dataclass

import pytest

from app.config import Settings
from app.domain.errors import CallServiceError
from app.domain.models import (
    CallServiceNode,
    ExitNode,
    IfEqualsNode,
    IfFileExistsNode,
    OperandLiteral,
    OperandVariable,
    PrintNode,
    PrintPartText,
    PrintPartVariable,
    ReadFileNode,
    SetVariableNode,
    WorkflowDefinition,
    WorkflowError,
)
from app.services.executor import WorkflowExecutor


@dataclass
class FakeFileReader:
    files: dict[str, str]

    def read_text(self, relative_path: str) -> str:
        if relative_path not in self.files:
            raise FileNotFoundError(relative_path)
        return self.files[relative_path]

    def exists(self, relative_path: str) -> bool:
        return relative_path in self.files


@dataclass
class FakeHttpClient:
    responses: dict[str, dict] | None = None
    error: CallServiceError | None = None

    async def post_json(self, url, body, *, timeout_seconds=None, max_retries=None):
        if self.error:
            raise self.error
        return self.responses[url]


@pytest.fixture
def executor():
    def _make(file_reader=None, http_client=None):
        return WorkflowExecutor(
            file_reader=file_reader or FakeFileReader({}),
            http_client=http_client or FakeHttpClient(responses={}),
        )

    return _make


async def test_linear_happy_path(executor):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="set",
        nodes=(
            SetVariableNode("set", "set_variable", "x", 1, "print"),
            PrintNode(
                "print",
                "print",
                (PrintPartVariable("variable", "x"),),
                "done",
            ),
            ExitNode("done", "exit", "success"),
        ),
    )
    result = await executor(wf).execute(wf)
    assert result.status == "success"
    assert result.variables == {"x": 1}
    assert result.prints == ["1"]


async def test_undefined_variable_aborts(executor):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="print",
        nodes=(
            PrintNode(
                "print",
                "print",
                (PrintPartVariable("variable", "missing"),),
                "done",
            ),
            ExitNode("done", "exit", "success"),
        ),
    )
    result = await executor(wf).execute(wf)
    assert result.status == "failure"
    assert result.error.code == "UNDEFINED_VARIABLE"


async def test_if_equals_branch(executor):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="check",
        nodes=(
            IfEqualsNode(
                "check",
                "if_equals",
                OperandLiteral("literal", 42),
                OperandLiteral("literal", "42"),
                "yes",
                "no",
            ),
            ExitNode("yes", "exit", "success"),
            ExitNode("no", "exit", "failure"),
        ),
    )
    result = await executor(wf).execute(wf)
    assert result.status == "success"


async def test_if_file_exists(executor):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="check",
        nodes=(
            IfFileExistsNode("check", "if_file_exists", "data.txt", "yes", "no"),
            ExitNode("yes", "exit", "success"),
            ExitNode("no", "exit", "failure"),
        ),
    )
    fr = FakeFileReader({"data.txt": "content"})
    result = await executor(fr).execute(wf)
    assert result.status == "success"


async def test_read_file(executor):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="read",
        nodes=(
            ReadFileNode("read", "read_file", "cfg.json", "content", "done"),
            ExitNode("done", "exit", "success"),
        ),
    )
    fr = FakeFileReader({"cfg.json": '{"ok": true}'})
    result = await executor(fr).execute(wf)
    assert result.variables["content"] == '{"ok": true}'


async def test_call_service(executor):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="call",
        nodes=(
            CallServiceNode(
                "call",
                "call_service",
                "https://api.example.com",
                {"k": "v"},
                "result",
                "done",
            ),
            ExitNode("done", "exit", "success"),
        ),
    )
    http = FakeHttpClient(responses={"https://api.example.com": {"ok": True}})
    result = await executor(http_client=http).execute(wf)
    assert result.status == "success"
    assert json.loads(result.variables["result"]) == {"ok": True}


async def test_exit_failure(executor):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="fail",
        nodes=(ExitNode("fail", "exit", "failure"),),
    )
    result = await executor(wf).execute(wf)
    assert result.status == "failure"


async def test_partial_state_on_failure(executor):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="set",
        nodes=(
            SetVariableNode("set", "set_variable", "x", 1, "call"),
            CallServiceNode(
                "call",
                "call_service",
                "https://api.example.com",
                {},
                "r",
                "done",
            ),
            ExitNode("done", "exit", "success"),
        ),
    )
    http = FakeHttpClient(
        error=CallServiceError(
            WorkflowError(code="CALL_SERVICE_HTTP_ERROR", message="503")
        )
    )
    result = await executor(http_client=http).execute(wf)
    assert result.status == "failure"
    assert result.variables == {"x": 1}
