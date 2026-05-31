from app.domain.models import IfEqualsNode
from app.services.handlers.base import ExecutionContext, HandlerOutcome, _resolve_operand


async def handle_if_equals(
    node: IfEqualsNode, context: ExecutionContext
) -> HandlerOutcome:
    left = _resolve_operand(node.left, context, node.id, "if_equals")
    if isinstance(left, HandlerOutcome):
        return left
    right = _resolve_operand(node.right, context, node.id, "if_equals")
    if isinstance(right, HandlerOutcome):
        return right

    next_id = node.on_true if left == right else node.on_false
    return HandlerOutcome(kind="next", next_node_id=next_id)
