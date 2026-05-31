from app.domain.models import SetVariableNode
from app.services.handlers.base import ExecutionContext, HandlerOutcome


async def handle_set_variable(
    node: SetVariableNode, context: ExecutionContext
) -> HandlerOutcome:
    """Assign a literal value to a workflow variable and continue linearly.

    Args:
        node: set_variable node with name, value, and next node id.
        context: Execution state whose variable map is updated in place.

    Returns:
        HandlerOutcome: Next node id after the assignment.
    """
    context.variables[node.name] = node.value
    return HandlerOutcome(kind="next", next_node_id=node.next)
