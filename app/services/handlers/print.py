from app.domain.models import PrintNode, PrintPartText, PrintPartVariable, WorkflowError
from app.services.handlers.base import ExecutionContext, HandlerOutcome, _resolve_operand


async def handle_print(node: PrintNode, context: ExecutionContext) -> HandlerOutcome:
    """Concatenate print parts and append the line to the execution print log.

    Args:
        node: Print node with text and variable parts.
        context: Execution state receiving the appended print line.

    Returns:
        HandlerOutcome: Next node id, or error when a referenced variable is undefined.
    """
    parts: list[str] = []
    for part in node.parts:
        if isinstance(part, PrintPartText):
            parts.append(str(part.value))
        elif isinstance(part, PrintPartVariable):
            if part.name not in context.variables:
                return HandlerOutcome(
                    kind="error",
                    error=WorkflowError(
                        code="UNDEFINED_VARIABLE",
                        message=f"Variable '{part.name}' is not defined",
                        step_id=node.id,
                        action="print",
                    ),
                )
            parts.append(str(context.variables[part.name]))
    context.prints.append("".join(parts))
    return HandlerOutcome(kind="next", next_node_id=node.next)
