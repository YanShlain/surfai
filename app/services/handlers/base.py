from dataclasses import dataclass
from typing import Literal

from app.domain.models import Node, VariableValue, WorkflowError
from app.domain.ports import IFileReader


@dataclass
class HandlerOutcome:
    """Result of executing a single workflow node handler."""

    kind: Literal["next", "exit", "error"]
    next_node_id: str | None = None
    exit_status: Literal["success", "failure"] | None = None
    error: WorkflowError | None = None


@dataclass
class ExecutionContext:
    """Mutable runtime state shared across workflow node handlers."""

    variables: dict[str, VariableValue]
    prints: list[str]
    file_reader: IFileReader
    http_client: object


def _resolve_operand(
    operand, context: ExecutionContext, step_id: str, action: str
) -> str | HandlerOutcome:
    """Resolve a literal or variable operand to its string value.

    Args:
        operand: Domain operand (literal or variable reference).
        context: Current execution state with variable bindings.
        step_id: Node id for error reporting.
        action: Node action name for error reporting.

    Returns:
        str | HandlerOutcome: Resolved string value, or an error outcome when
            the referenced variable is undefined.
    """
    if operand.type == "literal":
        return str(operand.value)
    if operand.name not in context.variables:
        return HandlerOutcome(
            kind="error",
            error=WorkflowError(
                code="UNDEFINED_VARIABLE",
                message=f"Variable '{operand.name}' is not defined",
                step_id=step_id,
                action=action,
            ),
        )
    return str(context.variables[operand.name])
