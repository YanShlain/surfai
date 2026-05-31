from typing import Protocol


class IFileReader(Protocol):
    def read_text(self, relative_path: str) -> str: ...

    def exists(self, relative_path: str) -> bool: ...
