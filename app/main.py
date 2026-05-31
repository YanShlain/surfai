import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware.logging import LoggingMiddleware
from app.api.routes.workflow import router, unhandled_exception_handler
from app.dependencies import AppContainer, build_container

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure root logging for structured single-line messages."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan hook: bootstrap logging and the dependency container.

    Args:
        app: FastAPI application instance receiving wired state.

    Yields:
        Control back to the server after startup completes.
    """
    # --- Bootstrap logging and DI container ---
    configure_logging()
    app.state.container = build_container()
    logger.info("Application started")
    yield


def create_app(container: AppContainer | None = None) -> FastAPI:
    """Build the FastAPI application with middleware, routes, and error handling.

    Args:
        container: Optional pre-built container for tests; production uses lifespan.

    Returns:
        FastAPI: Configured application ready to serve requests.
    """
    # --- Register core app wiring ---
    app = FastAPI(title="Workflow Evaluator", lifespan=lifespan)
    app.add_middleware(LoggingMiddleware)
    app.include_router(router)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # --- Override DI when a test container is supplied ---
    if container is not None:
        app.state.container = container

        def _override() -> AppContainer:
            """Return the injected test container for dependency overrides."""
            return container

        from app.api.routes.workflow import get_container

        app.dependency_overrides[get_container] = _override

    return app
