from dataclasses import dataclass

from app.domain.models import WorkflowError


@dataclass
class CallServiceError(Exception):
    error: WorkflowError

    def __str__(self) -> str:
        return self.error.message
