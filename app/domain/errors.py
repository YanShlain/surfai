from dataclasses import dataclass

from app.domain.models import WorkflowError


@dataclass
class CallServiceError(Exception):
    """Raised when an outbound call_service HTTP request fails."""

    error: WorkflowError

    def __str__(self) -> str:
        """Return the human-readable error message for logging and display."""
        return self.error.message
