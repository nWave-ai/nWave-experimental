"""Persist the DESIGN-owned section of a configured architecture authority."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.application.handover import Blocked
from des.runtime.spawn import GIT_TIMEOUT_ENV, git_timeout_seconds, spawn


if TYPE_CHECKING:
    from des.domain.design_document import DesignDocument


@dataclass(frozen=True, slots=True)
class PublishedDesignDocument:
    """The authority projection and whether this invocation persisted it."""

    locator: str
    digest: str
    authority_persisted: bool


def _tracked(root: Path, path: Path) -> bool | Blocked:
    """Return Git tracking state, or an indeterminate no-write outcome."""
    try:
        result = spawn(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--error-unmatch",
                "--",
                str(path.relative_to(root)),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=git_timeout_seconds(),
            timeout_env=GIT_TIMEOUT_ENV,
        )
    except subprocess.TimeoutExpired as error:
        return Blocked(
            "DesignAuthorityUnavailable",
            f"Git did not answer the authority tracking probe: {error}",
            "restore Git responsiveness and retry before publishing authority bytes",
        )
    return result.returncode == 0


def publish_design_document(
    root: Path,
    destination: str,
    document: DesignDocument,
    *,
    allow_untracked_recovery: bool = False,
) -> PublishedDesignDocument | Blocked:
    candidate = Path(destination)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        return Blocked(
            "UnsafeDesignDestination",
            "documents.design.destination must be a safe repository-relative file",
            "set documents.design.destination to a repository-relative authority file",
            refusal=True,
        )
    path = root / candidate
    try:
        resolved = path.resolve(strict=False)
        resolved.relative_to(root.resolve())
    except ValueError:
        return Blocked(
            "UnsafeDesignDestination",
            "documents.design.destination resolves outside the repository",
            "set documents.design.destination to a repository-relative authority file",
            refusal=True,
        )
    section = document.markdown().encode()
    try:
        if path.is_symlink():
            return Blocked(
                "UnsafeDesignDestination",
                "an existing DESIGN destination must be a tracked regular file",
                "choose a tracked regular authority file",
                refusal=True,
            )
        exists = path.exists()
        if exists and not path.is_file():
            return Blocked(
                "UnsafeDesignDestination",
                "an existing DESIGN destination must be a tracked regular file",
                "choose a tracked regular authority file",
                refusal=True,
            )
        existing = path.read_bytes() if exists else None
        tracked = _tracked(root, path) if exists else True
        if isinstance(tracked, Blocked):
            return tracked
        if (
            exists
            and not tracked
            and not (allow_untracked_recovery and existing == section)
        ):
            return Blocked(
                "UnsafeDesignDestination",
                "an existing DESIGN destination must be a tracked regular file",
                "choose a tracked regular authority file",
                refusal=True,
            )
        snapshot = existing or b""
        marker = f"## {document.heading}".encode()
        lines = snapshot.splitlines(keepends=True)
        offsets: list[int] = []
        cursor = 0
        for line in lines:
            if line.rstrip(b"\r\n") == marker:
                offsets.append(cursor)
            cursor += len(line)
        if len(offsets) > 1:
            return Blocked(
                "DesignAuthorityAmbiguous",
                "the existing DESIGN heading occurs more than once",
                "supply explicit supersession evidence before replacing an owned authority section",
                refusal=True,
            )
        if offsets:
            start = offsets[0]
            next_h2 = len(snapshot)
            cursor = 0
            for line in lines:
                if cursor > start and line.rstrip(b"\r\n").startswith(b"## "):
                    next_h2 = cursor
                    break
                cursor += len(line)
            owned = snapshot[start:next_h2]
            # Separators belong to the surrounding document.  The canonical
            # section must be the complete owned content before those bytes.
            if not owned.startswith(section) or owned[len(section) :].strip(b"\r\n"):
                return Blocked(
                    "DesignAuthorityDrift",
                    "the existing DESIGN heading has divergent content",
                    "supply explicit supersession evidence before replacing an owned authority section",
                    refusal=True,
                )
            rendered = snapshot
        else:
            rendered = snapshot + section
        if rendered != snapshot:
            current = path.read_bytes() if path.exists() else None
            if current != existing:
                return Blocked(
                    "DesignAuthorityDrift",
                    "authority changed before compare-and-swap",
                    "inspect authority before restart",
                    refusal=True,
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(rendered)
        return PublishedDesignDocument(
            f"{candidate}#{document.heading}",
            hashlib.sha256(rendered).hexdigest(),
            rendered != snapshot,
        )
    except OSError as error:
        return Blocked(
            "DesignAuthorityUnavailable", str(error), "restore authority storage"
        )
