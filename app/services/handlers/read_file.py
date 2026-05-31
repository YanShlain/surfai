from app.domain.models import ReadFileNode, WorkflowError
from app.services.handlers.base import ExecutionContext, HandlerOutcome


def _validate_path(path: str, step_id: str) -> WorkflowError | None:
    """Reject absolute paths and path traversal segments.

    Args:
        path: Relative file path from the workflow node.
        step_id: Node id attached to validation errors.

    Returns:
        WorkflowError | None: Error when the path is disallowed, otherwise None.
    """
    if path.startswith("/") or path.startswith("\\"):
        return WorkflowError(
            code="PATH_NOT_ALLOWED",
            message="Absolute paths are not allowed",
            step_id=step_id,
            action="read_file",
        )
    if ".." in path.split("/") or ".." in path.split("\\"):
        return WorkflowError(
            code="PATH_NOT_ALLOWED",
            message="Path traversal is not allowed",
            step_id=step_id,
            action="read_file",
        )
    return None


async def handle_read_file(
    node: ReadFileNode, context: ExecutionContext
) -> HandlerOutcome:
    """Read a sandboxed file into the configured result variable.

    Args:
        node: read_file node with path, result variable, and next node id.
        context: Execution state including the sandboxed file reader.

    Returns:
        HandlerOutcome: Next node id on success, or error for invalid path or I/O failure.
    """
    path_error = _validate_path(node.path, node.id)
    if path_error:
        return HandlerOutcome(kind="error", error=path_error)

    try:
        content = context.file_reader.read_text(node.path)
    except FileNotFoundError:
        return HandlerOutcome(
            kind="error",
            error=WorkflowError(
                code="FILE_NOT_FOUND",
                message=f"File not found: {node.path}",
                step_id=node.id,
                action="read_file",
            ),
        )
    except OSError as exc:
        return HandlerOutcome(
            kind="error",
            error=WorkflowError(
                code="FILE_READ_ERROR",
                message=f"Could not read file: {node.path}",
                step_id=node.id,
                action="read_file",
                cause=str(exc),
            ),
        )

    context.variables[node.result_variable] = content
    return HandlerOutcome(kind="next", next_node_id=node.next)
