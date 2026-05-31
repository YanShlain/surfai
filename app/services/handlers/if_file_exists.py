from app.domain.models import IfFileExistsNode, WorkflowError
from app.services.handlers.base import ExecutionContext, HandlerOutcome
from app.services.handlers.read_file import _validate_path


async def handle_if_file_exists(
    node: IfFileExistsNode, context: ExecutionContext
) -> HandlerOutcome:
    """Branch based on whether a sandboxed relative file path exists.

    Args:
        node: Branch node with path and on_true/on_false targets.
        context: Execution state including the sandboxed file reader.

    Returns:
        HandlerOutcome: Next node id, or error when the path is not allowed.
    """
    path_error = _validate_path(node.path, node.id)
    if path_error:
        return HandlerOutcome(kind="error", error=path_error)

    exists = context.file_reader.exists(node.path)
    next_id = node.on_true if exists else node.on_false
    return HandlerOutcome(kind="next", next_node_id=next_id)
