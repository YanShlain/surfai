import logging
from dataclasses import dataclass

from app.domain.models import ExecutionResult, Node, WorkflowDefinition, WorkflowError
from app.domain.ports import IFileReader
from app.services.handlers.base import ExecutionContext
from app.services.handlers.registry import HANDLERS

logger = logging.getLogger(__name__)


@dataclass
class WorkflowExecutor:
    file_reader: IFileReader
    http_client: object

    async def execute(self, workflow: WorkflowDefinition) -> ExecutionResult:
        node_map: dict[str, Node] = {n.id: n for n in workflow.nodes}
        context = ExecutionContext(
            variables={},
            prints=[],
            file_reader=self.file_reader,
            http_client=self.http_client,
        )

        current_id = workflow.entry
        while True:
            node = node_map.get(current_id)
            if node is None:
                return ExecutionResult.failure_from_error(
                    WorkflowError(
                        code="INVALID_NODE_REFERENCE",
                        message=f"Unknown node '{current_id}' during execution",
                        step_id=current_id,
                    ),
                    variables=dict(context.variables),
                    prints=list(context.prints),
                )

            handler = HANDLERS.get(node.action)
            if handler is None:
                return ExecutionResult.failure_from_error(
                    WorkflowError(
                        code="UNKNOWN_ACTION",
                        message=f"Unknown action '{node.action}'",
                        step_id=node.id,
                        action=node.action,
                    ),
                    variables=dict(context.variables),
                    prints=list(context.prints),
                )

            outcome = await handler(node, context)

            if outcome.kind == "error":
                assert outcome.error is not None
                logger.warning(
                    "Workflow step failed",
                    extra={"error_code": outcome.error.code, "step_id": outcome.error.step_id},
                )
                return ExecutionResult.failure_from_error(
                    outcome.error,
                    variables=dict(context.variables),
                    prints=list(context.prints),
                )

            if outcome.kind == "exit":
                status = outcome.exit_status or "success"
                return ExecutionResult(
                    status=status,
                    variables=dict(context.variables),
                    prints=list(context.prints),
                )

            assert outcome.next_node_id is not None
            current_id = outcome.next_node_id
