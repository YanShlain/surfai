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
    return request.app.state.container


def get_workflow_service(
    container: AppContainer = Depends(get_container),
) -> WorkflowService:
    return container.workflow_service


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/v1/workflows/execute", response_model=ExecuteResponse)
async def execute(
    body: ExecuteRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> ExecuteResponse:
    workflow = to_domain(body)
    result = await workflow_service.run(workflow)
    return to_response(result)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception",
        extra={"request_id": request_id, "path": request.url.path},
    )
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
