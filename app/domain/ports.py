from typing import Protocol


class IFileReader(Protocol):
    """Port for sandboxed filesystem reads used by workflow handlers."""

    def read_text(self, relative_path: str) -> str:
        """Read UTF-8 text from a path relative to the configured sandbox root."""

    def exists(self, relative_path: str) -> bool:
        """Return whether a sandboxed relative path refers to an existing file."""
