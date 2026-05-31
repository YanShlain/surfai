from app.api.schemas.execute import (
    CallServiceNodeDTO,
    ExecuteRequest,
    ExecuteResponse,
    ExitNodeDTO,
    IfEqualsNodeDTO,
    IfFileExistsNodeDTO,
    OperandLiteralDTO,
    OperandVariableDTO,
    PrintNodeDTO,
    PrintPartTextDTO,
    PrintPartVariableDTO,
    ReadFileNodeDTO,
    SetVariableNodeDTO,
    WorkflowDTO,
    WorkflowErrorDTO,
)
from app.domain.models import (
    CallServiceNode,
    ExecutionResult,
    ExitNode,
    IfEqualsNode,
    IfFileExistsNode,
    Node,
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


def _map_operand(dto):
    if dto.type == "literal":
        return OperandLiteral(type="literal", value=dto.value)
    return OperandVariable(type="variable", name=dto.name)


def _map_print_part(dto):
    if dto.type == "text":
        return PrintPartText(type="text", value=dto.value)
    return PrintPartVariable(type="variable", name=dto.name)


def _map_node(dto) -> Node:
    if dto.action == "set_variable":
        return SetVariableNode(
            id=dto.id,
            action="set_variable",
            name=dto.name,
            value=dto.value,
            next=dto.next,
            on_true=getattr(dto, "on_true", None),
            on_false=getattr(dto, "on_false", None),
        )
    if dto.action == "call_service":
        return CallServiceNode(
            id=dto.id,
            action="call_service",
            url=dto.url,
            body=dto.body,
            result_variable=dto.result_variable,
            next=dto.next,
            timeout_seconds=dto.timeout_seconds,
            max_retries=dto.max_retries,
        )
    if dto.action == "read_file":
        return ReadFileNode(
            id=dto.id,
            action="read_file",
            path=dto.path,
            result_variable=dto.result_variable,
            next=dto.next,
        )
    if dto.action == "print":
        return PrintNode(
            id=dto.id,
            action="print",
            parts=tuple(_map_print_part(p) for p in dto.parts),
            next=dto.next,
        )
    if dto.action == "if_equals":
        return IfEqualsNode(
            id=dto.id,
            action="if_equals",
            left=_map_operand(dto.left),
            right=_map_operand(dto.right),
            on_true=dto.on_true,
            on_false=dto.on_false,
        )
    if dto.action == "if_file_exists":
        return IfFileExistsNode(
            id=dto.id,
            action="if_file_exists",
            path=dto.path,
            on_true=dto.on_true,
            on_false=dto.on_false,
        )
    return ExitNode(id=dto.id, action="exit", status=dto.status)


def to_domain(request: ExecuteRequest) -> WorkflowDefinition:
    wf = request.workflow
    return WorkflowDefinition(
        schema_version=wf.schema_version,
        entry=wf.entry,
        nodes=tuple(_map_node(n) for n in wf.nodes),
    )


def _error_to_dto(error: WorkflowError) -> WorkflowErrorDTO:
    return WorkflowErrorDTO(
        code=error.code,
        message=error.message,
        step_id=error.step_id,
        action=error.action,
        cause=error.cause,
    )


def to_response(result: ExecutionResult) -> ExecuteResponse:
    return ExecuteResponse(
        status=result.status,
        variables=result.variables,
        prints=result.prints,
        error=_error_to_dto(result.error) if result.error else None,
    )
