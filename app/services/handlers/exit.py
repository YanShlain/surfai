from app.domain.models import ExitNode
from app.services.handlers.base import ExecutionContext, HandlerOutcome


async def handle_exit(node: ExitNode, context: ExecutionContext) -> HandlerOutcome:
    return HandlerOutcome(kind="exit", exit_status=node.status)
