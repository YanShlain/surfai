from dataclasses import dataclass

from app.config import Settings, load_settings
from app.infrastructure.file_reader import SandboxFileReader
from app.infrastructure.http_client import ExternalRestHttpClient
from app.services.executor import WorkflowExecutor
from app.services.validator import WorkflowValidator
from app.services.workflow_service import WorkflowService


@dataclass
class AppContainer:
    """Holds wired application dependencies for request-scoped access."""

    settings: Settings
    workflow_service: WorkflowService
    file_reader: SandboxFileReader
    http_client: ExternalRestHttpClient


def build_container(settings: Settings | None = None) -> AppContainer:
    """Construct the full dependency graph for workflow validation and execution.

    Args:
        settings: Optional settings instance; loads from environment when omitted.

    Returns:
        AppContainer: Container with validator, executor, and infrastructure clients.
    """
    # --- Resolve settings ---
    settings = settings or load_settings()

    # --- Wire infrastructure adapters ---
    file_reader = SandboxFileReader(settings=settings)
    http_client = ExternalRestHttpClient(settings=settings)

    # --- Wire domain services ---
    validator = WorkflowValidator(settings=settings)
    executor = WorkflowExecutor(file_reader=file_reader, http_client=http_client)
    workflow_service = WorkflowService(validator=validator, executor=executor)

    return AppContainer(
        settings=settings,
        workflow_service=workflow_service,
        file_reader=file_reader,
        http_client=http_client,
    )
