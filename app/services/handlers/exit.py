from app.domain.models import ExitNode
from app.services.handlers.base import ExecutionContext, HandlerOutcome


async def handle_exit(node: ExitNode, context: ExecutionContext) -> HandlerOutcome:
    """Terminate workflow execution with the node’s configured status.

    Args:
        node: Exit node declaring success or failure.
        context: Execution state (unused; present for handler signature uniformity).

    Returns:
        HandlerOutcome: Exit outcome carrying the node status.
    """
    return HandlerOutcome(kind="exit", exit_status=node.status)
