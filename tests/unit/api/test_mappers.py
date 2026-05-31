import pytest

from app.api.mappers import to_domain, to_response
from app.api.schemas.execute import ExecuteRequest
from app.domain.models import ExecutionResult, WorkflowError


def test_to_domain_happy_path(load_fixture):
    payload = load_fixture("happy_path")
    request = ExecuteRequest.model_validate(payload)
    workflow = to_domain(request)
    assert workflow.schema_version == 1
    assert workflow.entry == "set"
    assert len(workflow.nodes) == 3


def test_to_response_success():
    result = ExecutionResult.success_result(
        variables={"x": 1},
        prints=["1"],
    )
    response = to_response(result)
    assert response.status == "success"
    assert response.variables == {"x": 1}
    assert response.prints == ["1"]
    assert response.error is None


def test_to_response_failure():
    result = ExecutionResult.failure_from_error(
        WorkflowError(code="TEST", message="boom", step_id="n1", action="print")
    )
    response = to_response(result)
    assert response.status == "failure"
    assert response.error is not None
    assert response.error.code == "TEST"
