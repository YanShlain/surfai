import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    workflow_fs_root: str
    call_service_timeout_seconds: float
    call_service_max_timeout_seconds: float
    call_service_max_retries: int
    call_service_retry_base_seconds: float
    call_service_retry_max_seconds: float
    call_service_max_retries_cap: int


def load_settings() -> Settings:
    return Settings(
        workflow_fs_root=os.environ.get("WORKFLOW_FS_ROOT", "."),
        call_service_timeout_seconds=float(
            os.environ.get("CALL_SERVICE_TIMEOUT_SECONDS", "10")
        ),
        call_service_max_timeout_seconds=float(
            os.environ.get("CALL_SERVICE_MAX_TIMEOUT_SECONDS", "60")
        ),
        call_service_max_retries=int(
            os.environ.get("CALL_SERVICE_MAX_RETRIES", "3")
        ),
        call_service_retry_base_seconds=float(
            os.environ.get("CALL_SERVICE_RETRY_BASE_SECONDS", "0.5")
        ),
        call_service_retry_max_seconds=float(
            os.environ.get("CALL_SERVICE_RETRY_MAX_SECONDS", "30")
        ),
        call_service_max_retries_cap=int(
            os.environ.get("CALL_SERVICE_MAX_RETRIES_CAP", "5")
        ),
    )
