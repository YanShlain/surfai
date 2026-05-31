from app.domain.models import IfFileExistsNode, WorkflowError
from app.services.handlers.base import ExecutionContext, HandlerOutcome
from app.services.handlers.read_file import _validate_path


async def handle_if_file_exists(
    node: IfFileExistsNode, context: ExecutionContext
) -> HandlerOutcome:
    path_error = _validate_path(node.path, node.id)
    if path_error:
        return HandlerOutcome(kind="error", error=path_error)

    exists = context.file_reader.exists(node.path)
    next_id = node.on_true if exists else node.on_false
    return HandlerOutcome(kind="next", next_node_id=next_id)
