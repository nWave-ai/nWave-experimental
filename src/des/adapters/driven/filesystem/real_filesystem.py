"""Production implementation of filesystem adapter."""

import json
import os
import stat
from pathlib import Path

from des.ports.driven_ports.filesystem_port import (
    FileSystemPort,
    RegularFileSnapshot,
    SnapshotRefusal,
    SnapshotRefusalReason,
)


def _same_file_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (
        first.st_dev,
        first.st_ino,
        stat.S_IFMT(first.st_mode),
    ) == (
        second.st_dev,
        second.st_ino,
        stat.S_IFMT(second.st_mode),
    )


def _same_file_snapshot(first: os.stat_result, second: os.stat_result) -> bool:
    """True when identity and byte-relevant metadata stayed stable."""
    return _same_file_identity(first, second) and (
        first.st_size,
        first.st_mtime_ns,
        first.st_ctime_ns,
    ) == (
        second.st_size,
        second.st_mtime_ns,
        second.st_ctime_ns,
    )


class RealFileSystem(FileSystemPort):
    """Production implementation of file system operations.

    Wraps standard Python file I/O operations for JSON files.
    """

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
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, path: Path, data: dict) -> None:
        """Write data as formatted JSON file.

        Args:
            path: Absolute path to target JSON file
            data: Dictionary to write as JSON
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def exists(self, path: Path) -> bool:
        """Check if path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists
        """
        return path.exists()

    def acquire_regular_snapshot(
        self, path: Path, *, role: str
    ) -> RegularFileSnapshot | SnapshotRefusal:
        """Read one byte-stable snapshot from the same no-follow regular FD.

        No-follow is a CAPABILITY, not a flag that may silently degrade to
        ``0``: without it an ordinary open cannot bind the validated path to
        the opened file, so the file is never opened at all.

        Metadata brackets replacement and ordinary writes, but timestamps are
        not a byte oracle on every filesystem.  The last path observation is
        therefore followed by a second read from the still-open FD.  Equality
        with the first read is the linearization check, and the final read is
        the value the snapshot carries.  Mutation after that observation
        belongs to the downstream frozen-digest point-of-use comparison;
        perpetual path immutability is neither possible nor claimed here.
        """
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if no_follow is None:
            return SnapshotRefusal(
                reason=SnapshotRefusalReason.NO_FOLLOW_UNAVAILABLE,
                what=f"this platform has no no-follow open capability for the {role}",
                why=(
                    "an ordinary open cannot bind the validated path to the "
                    "opened file, so no closure member may be opened at all"
                ),
                how=(
                    "run des dispatch on a platform whose os module exposes O_NOFOLLOW"
                ),
            )
        try:
            before = path.lstat()
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | no_follow
            descriptor = os.open(path, flags)
        except OSError as exc:
            return SnapshotRefusal(
                reason=SnapshotRefusalReason.UNOPENABLE,
                what=f"the {role} cannot be opened without following links ({exc})",
                why=f"delivery closure requires stable readable {role} bytes",
                how=f"replace the {role} with a readable regular file and rerun",
            )
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or not _same_file_snapshot(
                before, opened
            ):
                return self._identity_changed(role, "opened")
            stream = os.fdopen(descriptor, "rb", closefd=True)
            descriptor = -1
            return self._stable_snapshot(stream, path, opened=opened, role=role)
        except OSError as exc:
            return SnapshotRefusal(
                reason=SnapshotRefusalReason.UNREADABLE,
                what=f"the {role} cannot be read ({exc})",
                why=f"delivery closure requires readable {role} bytes",
                how="fix the file permissions and rerun des dispatch",
            )
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _stable_snapshot(
        self, stream, path: Path, *, opened: os.stat_result, role: str
    ) -> RegularFileSnapshot | SnapshotRefusal:
        with stream:
            first_content = stream.read()
            after_first_read = os.fstat(stream.fileno())
            after_path = path.lstat()
            if not _same_file_snapshot(
                opened, after_first_read
            ) or not _same_file_snapshot(after_first_read, after_path):
                return self._identity_changed(role, "read")

            stream.seek(0, os.SEEK_SET)
            before_final_read = os.fstat(stream.fileno())
            final_content = stream.read()
            after_final_read = os.fstat(stream.fileno())
            if not _same_file_snapshot(
                after_path, before_final_read
            ) or not _same_file_snapshot(before_final_read, after_final_read):
                return self._identity_changed(role, "read")
            if first_content != final_content:
                return SnapshotRefusal(
                    reason=SnapshotRefusalReason.BYTES_CHANGED,
                    what=f"the {role} bytes changed while it was read",
                    why="delivery closure requires one byte-stable observation",
                    how=f"stop concurrent mutation of the {role} and rerun",
                )
            return RegularFileSnapshot(
                path=path,
                content=final_content,
                mode=after_final_read.st_mode,
            )

    @staticmethod
    def _identity_changed(role: str, phase: str) -> SnapshotRefusal:
        why = (
            "path validation and byte reading must bind the same regular file"
            if phase == "opened"
            else "closure bytes must belong to the declared stable locator"
        )
        return SnapshotRefusal(
            reason=SnapshotRefusalReason.IDENTITY_CHANGED,
            what=f"the {role} identity changed while it was {phase}",
            why=why,
            how="stop concurrent replacement of the file and rerun",
        )
