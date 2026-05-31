from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PrintPartTextDTO(BaseModel):
    type: Literal["text"]
    value: str | int | float


class PrintPartVariableDTO(BaseModel):
    type: Literal["variable"]
    name: str


PrintPartDTO = PrintPartTextDTO | PrintPartVariableDTO


class OperandLiteralDTO(BaseModel):
    type: Literal["literal"]
    value: str | int | float


class OperandVariableDTO(BaseModel):
    type: Literal["variable"]
    name: str


OperandDTO = OperandLiteralDTO | OperandVariableDTO


class SetVariableNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: Literal["set_variable"]
    name: str
    value: str | int | float
    next: str
    on_true: str | None = None
    on_false: str | None = None


class CallServiceNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: Literal["call_service"]
    url: str
    body: dict[str, Any] = Field(default_factory=dict)
    result_variable: str
    next: str
    timeout_seconds: float | None = None
    max_retries: int | None = None


class ReadFileNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: Literal["read_file"]
    path: str
    result_variable: str
    next: str


class PrintNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: Literal["print"]
    parts: list[PrintPartDTO]
    next: str


class IfEqualsNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: Literal["if_equals"]
    left: OperandDTO
    right: OperandDTO
    on_true: str
    on_false: str


class IfFileExistsNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: Literal["if_file_exists"]
    path: str
    on_true: str
    on_false: str


class ExitNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: Literal["exit"]
    status: Literal["success", "failure"]


NodeDTO = (
    SetVariableNodeDTO
    | CallServiceNodeDTO
    | ReadFileNodeDTO
    | PrintNodeDTO
    | IfEqualsNodeDTO
    | IfFileExistsNodeDTO
    | ExitNodeDTO
)


class WorkflowDTO(BaseModel):
    schema_version: int
    entry: str
    nodes: list[NodeDTO]


class ExecuteRequest(BaseModel):
    workflow: WorkflowDTO


class WorkflowErrorDTO(BaseModel):
    code: str
    message: str
    step_id: str | None = None
    action: str | None = None
    cause: str | None = None


class ExecuteResponse(BaseModel):
    status: Literal["success", "failure"]
    variables: dict[str, str | int | float] = Field(default_factory=dict)
    prints: list[str] = Field(default_factory=list)
    error: WorkflowErrorDTO | None = None
