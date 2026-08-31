import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SnapshotRefusalReason(Enum):
    """Closed set of reasons one regular-file snapshot cannot be acquired."""

    NO_FOLLOW_UNAVAILABLE = "no-follow-unavailable"
    UNOPENABLE = "unopenable"
    IDENTITY_CHANGED = "identity-changed"
    BYTES_CHANGED = "bytes-changed"
    UNREADABLE = "unreadable"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RegularFileSnapshot:
    """Opaque success value: bytes read from one validated no-follow open.

    The bytes are held by the snapshot precisely so no consumer reopens the
    path to obtain them again.  A reopen is a different observation of a
    different file, whatever the locator still says.
    """

    path: Path
    content: bytes
    mode: int


@dataclass(frozen=True)
class SnapshotRefusal:
    """Opaque failure value carrying its own WHAT / WHY / HOW.

    A refusal never carries success bytes, so no caller can mistake a refused
    acquisition for a degraded read.
    """

    reason: SnapshotRefusalReason
    what: str
    why: str
    how: str


class FileSystemPort(ABC):
    """Port for file system operations."""

    def acquire_regular_snapshot(
        self, path: Path, *, role: str
    ) -> RegularFileSnapshot | SnapshotRefusal:
        """Acquire one byte-stable snapshot of a regular file, or refuse.

        The default implementation deliberately REFUSES rather than reading:
        acquisition requires a validated no-follow open capability that only
        the real filesystem adapter owns.  A permissive default would let an
        adapter copy share the very defect this operation exists to exclude.
        """
        return SnapshotRefusal(
            reason=SnapshotRefusalReason.UNSUPPORTED,
            what=f"this filesystem cannot acquire a {role} snapshot",
            why="only the real filesystem adapter owns no-follow acquisition",
            how="inject des.adapters.driven.filesystem.RealFileSystem",
        )

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
