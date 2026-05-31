from dataclasses import dataclass

from app.config import Settings, load_settings
from app.infrastructure.file_reader import SandboxFileReader
from app.infrastructure.http_client import ExternalRestHttpClient
from app.services.executor import WorkflowExecutor
from app.services.validator import WorkflowValidator
from app.services.workflow_service import WorkflowService


@dataclass
class AppContainer:
    settings: Settings
    workflow_service: WorkflowService
    file_reader: SandboxFileReader
    http_client: ExternalRestHttpClient


def build_container(settings: Settings | None = None) -> AppContainer:
    settings = settings or load_settings()
    file_reader = SandboxFileReader(settings=settings)
    http_client = ExternalRestHttpClient(settings=settings)
    validator = WorkflowValidator(settings=settings)
    executor = WorkflowExecutor(file_reader=file_reader, http_client=http_client)
    workflow_service = WorkflowService(validator=validator, executor=executor)
    return AppContainer(
        settings=settings,
        workflow_service=workflow_service,
        file_reader=file_reader,
        http_client=http_client,
    )
