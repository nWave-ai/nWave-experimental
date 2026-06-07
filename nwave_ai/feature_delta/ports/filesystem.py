"""FileSystem driven ports — RED scaffold."""

from __future__ import annotations

from typing import Protocol


__SCAFFOLD__ = True


class FileSystemReadPort(Protocol):
    def read_text(self, path) -> str: ...
    def probe(self) -> None: ...


class FileSystemWritePort(Protocol):
    def write_text(self, path, content: str) -> None: ...
    def probe(self) -> None: ...
