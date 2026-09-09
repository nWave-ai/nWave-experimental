"""One safe exact-retry publisher for whole-file authorities."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from des.application.handover import Blocked


@dataclass(frozen=True, slots=True)
class PublishedWholeFile:
    locator: str
    digest: str


def publish_whole_file(
    root: Path,
    destination: str,
    content: bytes,
    *,
    unsafe: str,
    drift: str,
    unavailable: str,
    unsafe_why: str = "destination must be a safe repository-relative Markdown file",
    unsafe_how: str = "set the destination to a repository-relative .md file",
    regular_why: str = "an existing destination must be a regular file",
    regular_how: str = "choose a regular authority path",
    drift_why: str = "the existing authority has divergent content",
    drift_how: str = "reconcile the authority before retrying",
) -> PublishedWholeFile | Blocked:
    candidate = Path(destination)
    try:
        safe = (
            not candidate.is_absolute()
            and ".." not in candidate.parts
            and bool(candidate.parts)
            and (root / candidate).resolve(strict=False).is_relative_to(root.resolve())
        )
    except OSError:
        safe = False
    if not safe or candidate.suffix != ".md":
        return Blocked(
            unsafe,
            unsafe_why,
            unsafe_how,
            refusal=True,
        )
    path = root / candidate
    try:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            return Blocked(
                unsafe,
                regular_why,
                regular_how,
                refusal=True,
            )
        if path.exists() and path.read_bytes() != content:
            return Blocked(
                drift,
                drift_why,
                drift_how,
                refusal=True,
            )
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return PublishedWholeFile(str(candidate), hashlib.sha256(content).hexdigest())
    except OSError as error:
        return Blocked(
            unavailable,
            f"writing authority failed; authority may already have changed: {error}",
            "restore authority storage, then retry",
        )
