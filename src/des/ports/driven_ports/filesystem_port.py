import json
import os
from abc import ABC, abstractmethod
from pathlib import Path


class FileSystemPort(ABC):
    """Port for file system operations."""

    @abstractmethod
    def read_json(self, path: Path) -> dict:
        """Read and parse JSON file.

        Args:
            path: Absolute path to JSON file

        Returns:
            Parsed JSON data as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            JSONDecodeError: If file is not valid JSON
        """
        pass

    @abstractmethod
    def write_json(self, path: Path, data: dict) -> None:
        """Write data as formatted JSON file.

        Args:
            path: Absolute path to target JSON file
            data: Dictionary to write as JSON
        """
        pass

    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Check if path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists
        """
        pass

    def read_bytes(self, path: Path) -> bytes:
        """Read exact bytes at a path for persistence and recovery checks."""
        return path.read_bytes()

    def replace_text_atomically(self, path: Path, text: bytes) -> None:
        """Publish complete canonical bytes with one same-directory replace."""
        temporary = path.with_name(f".{path.name}.tmp")
        mode = path.stat().st_mode
        created = False
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(temporary, flags, mode & 0o777)
            created = True
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)  # noqa: PTH101 - preserve os-level port seam
            os.replace(temporary, path)  # noqa: PTH105 - replace is the injected port seam
        finally:
            if created and temporary.exists():
                temporary.unlink()

    def snapshot_and_replace(self, path: Path, data: dict) -> Path:
        """Back up ``path`` then atomically replace it with JSON ``data``.

        The default implementation deliberately lives on the driven port so
        application services do not acquire a second, direct filesystem
        capability.  The backup is created before the temporary file can be
        published and is retained if replacement fails.
        """
        backup = self._next_backup_path(path)
        backup.write_bytes(self.read_bytes(path))
        temporary = path.with_name(f".{path.name}.nwave-tmp")
        try:
            payload = json.dumps(data, indent=2).encode("utf-8")
            with temporary.open("wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            if temporary.exists():
                temporary.unlink()
            raise
        return backup

    @staticmethod
    def _next_backup_path(path: Path) -> Path:
        candidate = path.with_name(f"{path.name}.bak")
        suffix = 0
        while candidate.exists():
            suffix += 1
            candidate = path.with_name(f"{path.name}.bak.{suffix}")
        return candidate
