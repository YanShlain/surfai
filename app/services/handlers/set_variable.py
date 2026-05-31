from app.domain.models import SetVariableNode
from app.services.handlers.base import ExecutionContext, HandlerOutcome


async def handle_set_variable(
    node: SetVariableNode, context: ExecutionContext
) -> HandlerOutcome:
    context.variables[node.name] = node.value
    return HandlerOutcome(kind="next", next_node_id=node.next)
