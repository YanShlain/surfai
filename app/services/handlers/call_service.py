import json

from app.domain.errors import CallServiceError
from app.domain.models import CallServiceNode, WorkflowError
from app.services.handlers.base import ExecutionContext, HandlerOutcome


async def handle_call_service(
    node: CallServiceNode, context: ExecutionContext
) -> HandlerOutcome:
    try:
        response = await context.http_client.post_json(
            node.url,
            node.body,
            timeout_seconds=node.timeout_seconds,
            max_retries=node.max_retries,
        )
    except CallServiceError as exc:
        err = exc.error
        return HandlerOutcome(
            kind="error",
            error=WorkflowError(
                code=err.code,
                message=err.message,
                step_id=node.id,
                action="call_service",
                cause=err.cause,
            ),
        )

    context.variables[node.result_variable] = json.dumps(response)
    return HandlerOutcome(kind="next", next_node_id=node.next)
