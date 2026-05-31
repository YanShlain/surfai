from dataclasses import dataclass, field
from typing import Any, Literal

VariableValue = str | int | float


@dataclass(frozen=True)
class PrintPartText:
    type: Literal["text"]
    value: str | int | float


@dataclass(frozen=True)
class PrintPartVariable:
    type: Literal["variable"]
    name: str


PrintPart = PrintPartText | PrintPartVariable


@dataclass(frozen=True)
class OperandLiteral:
    type: Literal["literal"]
    value: str | int | float


@dataclass(frozen=True)
class OperandVariable:
    type: Literal["variable"]
    name: str


Operand = OperandLiteral | OperandVariable


@dataclass(frozen=True)
class SetVariableNode:
    id: str
    action: Literal["set_variable"]
    name: str
    value: VariableValue
    next: str
    on_true: str | None = None
    on_false: str | None = None


@dataclass(frozen=True)
class CallServiceNode:
    id: str
    action: Literal["call_service"]
    url: str
    body: dict[str, Any]
    result_variable: str
    next: str
    timeout_seconds: float | None = None
    max_retries: int | None = None
    on_true: str | None = None
    on_false: str | None = None


@dataclass(frozen=True)
class ReadFileNode:
    id: str
    action: Literal["read_file"]
    path: str
    result_variable: str
    next: str
    on_true: str | None = None
    on_false: str | None = None


@dataclass(frozen=True)
class PrintNode:
    id: str
    action: Literal["print"]
    parts: tuple[PrintPart, ...]
    next: str
    on_true: str | None = None
    on_false: str | None = None


@dataclass(frozen=True)
class IfEqualsNode:
    id: str
    action: Literal["if_equals"]
    left: Operand
    right: Operand
    on_true: str
    on_false: str
    next: str | None = None


@dataclass(frozen=True)
class IfFileExistsNode:
    id: str
    action: Literal["if_file_exists"]
    path: str
    on_true: str
    on_false: str
    next: str | None = None


@dataclass(frozen=True)
class ExitNode:
    id: str
    action: Literal["exit"]
    status: Literal["success", "failure"]


Node = (
    SetVariableNode
    | CallServiceNode
    | ReadFileNode
    | PrintNode
    | IfEqualsNode
    | IfFileExistsNode
    | ExitNode
)


@dataclass(frozen=True)
class WorkflowDefinition:
    schema_version: int
    entry: str
    nodes: tuple[Node, ...]


@dataclass(frozen=True)
class WorkflowError:
    code: str
    message: str
    step_id: str | None = None
    action: str | None = None
    cause: str | None = None


@dataclass
class ExecutionResult:
    status: Literal["success", "failure"]
    variables: dict[str, VariableValue] = field(default_factory=dict)
    prints: list[str] = field(default_factory=list)
    error: WorkflowError | None = None

    @classmethod
    def failure_from_validation(cls, errors: list[WorkflowError]) -> "ExecutionResult":
        """Build a failure result from the first validation error.

        Args:
            errors: Non-empty list of structural validation errors.

        Returns:
            ExecutionResult: Failure with the first error and empty runtime state.
        """
        first = errors[0]
        return cls(status="failure", error=first)

    @classmethod
    def failure_from_error(
        cls,
        error: WorkflowError,
        *,
        variables: dict[str, VariableValue] | None = None,
        prints: list[str] | None = None,
    ) -> "ExecutionResult":
        """Build a failure result preserving partial execution state.

        Args:
            error: Runtime error that stopped the workflow.
            variables: Variables collected before the failing step.
            prints: Print output collected before the failing step.

        Returns:
            ExecutionResult: Failure with optional partial variables and prints.
        """
        return cls(
            status="failure",
            variables=variables or {},
            prints=prints or [],
            error=error,
        )

    @classmethod
    def success_result(
        cls,
        *,
        variables: dict[str, VariableValue],
        prints: list[str],
    ) -> "ExecutionResult":
        """Build a successful execution result.

        Args:
            variables: Final workflow variable bindings.
            prints: Collected print node output lines.

        Returns:
            ExecutionResult: Success with final state and no error.
        """
        return cls(status="success", variables=variables, prints=prints)
