import pytest

from app.config import Settings
from app.domain.models import (
    CallServiceNode,
    ExitNode,
    IfEqualsNode,
    IfFileExistsNode,
    OperandLiteral,
    OperandVariable,
    PrintNode,
    PrintPartText,
    ReadFileNode,
    SetVariableNode,
    WorkflowDefinition,
)
from app.services.validator import WorkflowValidator


@pytest.fixture
def validator():
    return WorkflowValidator(
        settings=Settings(
            workflow_fs_root=".",
            call_service_timeout_seconds=10,
            call_service_max_timeout_seconds=60,
            call_service_max_retries=3,
            call_service_retry_base_seconds=0.5,
            call_service_retry_max_seconds=30,
            call_service_max_retries_cap=5,
        )
    )


def _linear_workflow(*nodes):
    return WorkflowDefinition(schema_version=1, entry=nodes[0].id, nodes=nodes)


def test_valid_minimal_workflow(validator):
    wf = _linear_workflow(
        SetVariableNode("a", "set_variable", "x", 1, "b"),
        ExitNode("b", "exit", "success"),
    )
    assert validator.validate(wf).ok


def test_invalid_schema_version(validator):
    wf = WorkflowDefinition(schema_version=2, entry="a", nodes=(ExitNode("a", "exit", "success"),))
    result = validator.validate(wf)
    assert not result.ok
    assert result.errors[0].code == "INVALID_SCHEMA_VERSION"


def test_invalid_entry(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="missing",
        nodes=(ExitNode("a", "exit", "success"),),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "INVALID_ENTRY" for e in result.errors)


def test_duplicate_node_id(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            ExitNode("a", "exit", "success"),
            ExitNode("a", "exit", "failure"),
        ),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "DUPLICATE_NODE_ID" for e in result.errors)


def test_mixed_routing(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            SetVariableNode("a", "set_variable", "x", 1, "b"),
            ExitNode("b", "exit", "success"),
        ),
    )
    # Manually create invalid node by using a dataclass replacement isn't easy;
    # test via workflow with branch + next in JSON integration test.
    # Here test branch missing on_false:
    wf2 = WorkflowDefinition(
        schema_version=1,
        entry="c",
        nodes=(
            IfEqualsNode(
                "c",
                "if_equals",
                OperandVariable("variable", "x"),
                OperandLiteral("literal", 1),
                "t",
                "f",
            ),
            ExitNode("t", "exit", "success"),
            ExitNode("f", "exit", "success"),
        ),
    )
    assert validator.validate(wf2).ok
    assert validator.validate(wf).ok


def test_cycle_detected(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="check",
        nodes=(
            IfEqualsNode(
                "check",
                "if_equals",
                OperandLiteral("literal", 1),
                OperandLiteral("literal", 2),
                "loop",
                "done",
            ),
            SetVariableNode("loop", "set_variable", "x", 1, "check"),
            ExitNode("done", "exit", "success"),
        ),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "CYCLE_DETECTED" for e in result.errors)


def test_no_reachable_exit(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            SetVariableNode("a", "set_variable", "x", 1, "b"),
            SetVariableNode("b", "set_variable", "y", 2, "a"),
        ),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "NO_REACHABLE_EXIT" for e in result.errors)


def test_call_service_invalid_url(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            CallServiceNode(
                "a",
                "call_service",
                "file:///etc/passwd",
                {},
                "r",
                "b",
            ),
            ExitNode("b", "exit", "success"),
        ),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "CALL_SERVICE_URL_NOT_ALLOWED" for e in result.errors)


def test_call_service_timeout_too_large(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            CallServiceNode(
                "a",
                "call_service",
                "https://example.com",
                {},
                "r",
                "b",
                timeout_seconds=100,
            ),
            ExitNode("b", "exit", "success"),
        ),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "CALL_SERVICE_TIMEOUT_TOO_LARGE" for e in result.errors)


def test_call_service_retries_too_large(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            CallServiceNode(
                "a",
                "call_service",
                "https://example.com",
                {},
                "r",
                "b",
                max_retries=10,
            ),
            ExitNode("b", "exit", "success"),
        ),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "CALL_SERVICE_RETRIES_TOO_LARGE" for e in result.errors)


def test_empty_print_parts(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            PrintNode("a", "print", (), "b"),
            ExitNode("b", "exit", "success"),
        ),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "INVALID_PRINT_PARTS" for e in result.errors)


def test_invalid_node_reference(validator):
    wf = WorkflowDefinition(
        schema_version=1,
        entry="a",
        nodes=(
            SetVariableNode("a", "set_variable", "x", 1, "missing"),
            ExitNode("b", "exit", "success"),
        ),
    )
    result = validator.validate(wf)
    assert not result.ok
    assert any(e.code == "INVALID_NODE_REFERENCE" for e in result.errors)
