import logging
import os
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class SandboxFileReader:
    """Reads files relative to a configured root, blocking path traversal."""

    settings: Settings

    def _resolve(self, relative_path: str) -> Path:
        """Resolve a workflow-relative path inside the sandbox root.

        Args:
            relative_path: Path relative to ``workflow_fs_root``.

        Returns:
            Path: Absolute path guaranteed to stay under the sandbox root.

        Raises:
            PermissionError: When the resolved path escapes the sandbox.
        """
        root = Path(self.settings.workflow_fs_root).resolve()
        target = (root / relative_path).resolve()
        if not str(target).startswith(str(root)):
            raise PermissionError("Path escapes sandbox root")
        return target

    def read_text(self, relative_path: str) -> str:
        """Read UTF-8 text from a sandboxed relative path.

        Args:
            relative_path: File path relative to the configured filesystem root.

        Returns:
            str: File contents decoded as UTF-8.
        """
        path = self._resolve(relative_path)
        logger.info("Reading file", extra={"path": relative_path})
        return path.read_text(encoding="utf-8")

    def exists(self, relative_path: str) -> bool:
        """Check whether a sandboxed relative path refers to an existing file.

        Args:
            relative_path: File path relative to the configured filesystem root.

        Returns:
            bool: True when the path resolves to a regular file.
        """
        path = self._resolve(relative_path)
        return path.is_file()
