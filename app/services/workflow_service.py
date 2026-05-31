from dataclasses import dataclass

from app.domain.models import ExecutionResult, WorkflowDefinition
from app.services.executor import WorkflowExecutor
from app.services.validator import WorkflowValidator


@dataclass
class WorkflowService:
    validator: WorkflowValidator
    executor: WorkflowExecutor

    async def run(self, workflow: WorkflowDefinition) -> ExecutionResult:
        validation = self.validator.validate(workflow)
        if not validation.ok:
            return ExecutionResult.failure_from_validation(validation.errors)
        return await self.executor.execute(workflow)
