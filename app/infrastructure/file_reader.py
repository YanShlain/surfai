import logging
import os
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class SandboxFileReader:
    settings: Settings

    def _resolve(self, relative_path: str) -> Path:
        root = Path(self.settings.workflow_fs_root).resolve()
        target = (root / relative_path).resolve()
        if not str(target).startswith(str(root)):
            raise PermissionError("Path escapes sandbox root")
        return target

    def read_text(self, relative_path: str) -> str:
        path = self._resolve(relative_path)
        logger.info("Reading file", extra={"path": relative_path})
        return path.read_text(encoding="utf-8")

    def exists(self, relative_path: str) -> bool:
        path = self._resolve(relative_path)
        return path.is_file()
