from dataclasses import dataclass

from app.domain.models import ExecutionResult, WorkflowDefinition
from app.services.executor import WorkflowExecutor
from app.services.validator import WorkflowValidator


@dataclass
class WorkflowService:
    """Application use case: validate then execute submitted workflows."""

    validator: WorkflowValidator
    executor: WorkflowExecutor

    async def run(self, workflow: WorkflowDefinition) -> ExecutionResult:
        """Validate workflow structure and execute it when validation passes.

        Args:
            workflow: Domain workflow graph to validate and run.

        Returns:
            ExecutionResult: Validation failure or executor outcome.
        """
        validation = self.validator.validate(workflow)
        if not validation.ok:
            return ExecutionResult.failure_from_validation(validation.errors)
        return await self.executor.execute(workflow)
