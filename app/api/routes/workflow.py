import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.mappers import to_domain, to_response
from app.api.schemas.execute import ExecuteRequest, ExecuteResponse, WorkflowErrorDTO
from app.dependencies import AppContainer
from app.services.workflow_service import WorkflowService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_container(request: Request) -> AppContainer:
    """FastAPI dependency that returns the wired application container.

    Args:
        request: Current request carrying ``app.state.container``.

    Returns:
        AppContainer: Dependency graph built at startup or injected in tests.
    """
    return request.app.state.container


def get_workflow_service(
    container: AppContainer = Depends(get_container),
) -> WorkflowService:
    """FastAPI dependency that exposes the workflow use-case service.

    Args:
        container: Application container resolved per request.

    Returns:
        WorkflowService: Validates and executes submitted workflows.
    """
    return container.workflow_service


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe confirming the API process is running."""
    return {"status": "ok"}


@router.post("/v1/workflows/execute", response_model=ExecuteResponse)
async def execute(
    body: ExecuteRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> ExecuteResponse:
    """Validate and run a workflow graph submitted in the request body.

    Args:
        body: Workflow definition and entry node id.
        workflow_service: Injected service performing validation then execution.

    Returns:
        ExecuteResponse: Variables, prints, status, and optional error details.
    """
    # --- Map API payload to domain and run ---
    workflow = to_domain(body)
    result = await workflow_service.run(workflow)
    return to_response(result)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch uncaught exceptions and return a safe failure response.

    Args:
        request: Request that triggered the exception.
        exc: Unhandled exception raised by a route or dependency.

    Returns:
        JSONResponse: HTTP 200 with ``status=failure`` and a generic error payload.
    """
    # --- Log with correlation id ---
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception",
        extra={"request_id": request_id, "path": request.url.path},
    )

    # --- Build stable client-facing error body ---
    body = ExecuteResponse(
        status="failure",
        error=WorkflowErrorDTO(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            cause=type(exc).__name__,
        ),
    )
    headers = {"X-Request-ID": request_id} if request_id else {}
    return JSONResponse(status_code=200, content=body.model_dump(), headers=headers)
