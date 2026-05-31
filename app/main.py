import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware.logging import LoggingMiddleware
from app.api.routes.workflow import router, unhandled_exception_handler
from app.dependencies import AppContainer, build_container

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.container = build_container()
    logger.info("Application started")
    yield


def create_app(container: AppContainer | None = None) -> FastAPI:
    app = FastAPI(title="Workflow Evaluator", lifespan=lifespan)
    app.add_middleware(LoggingMiddleware)
    app.include_router(router)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    if container is not None:
        app.state.container = container

        def _override() -> AppContainer:
            return container

        from app.api.routes.workflow import get_container

        app.dependency_overrides[get_container] = _override

    return app
