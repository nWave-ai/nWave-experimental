"""One safe exact-retry publisher for whole-file authorities."""

from __future__ import annotations

import hashlib
import os
import tempfile
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


def publish_whole_file_revision(
    root: Path,
    destination: str,
    expected_content: bytes | None,
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
    """Publish ``content`` only as an exact revision of a known projection.

    ``expected_content`` is ``None`` only for a first publication.  Existing
    whole-file callers keep their create-or-exact-retry behavior through
    :func:`publish_whole_file`; this narrow primitive is for a DES-owned
    projection that must retain its already-persisted typed facts.
    """
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
        return Blocked(unsafe, unsafe_why, unsafe_how, refusal=True)
    path = root / candidate
    try:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            return Blocked(unsafe, regular_why, regular_how, refusal=True)
        try:
            actual = path.read_bytes()
        except FileNotFoundError:
            actual = None
        if actual == content:
            return PublishedWholeFile(
                str(candidate), hashlib.sha256(content).hexdigest()
            )
        if actual is None and expected_content is not None:
            return Blocked(
                drift, "the existing authority is missing", drift_how, refusal=True
            )
        if actual is not None and actual != expected_content:
            return Blocked(drift, drift_why, drift_how, refusal=True)

        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".authority-", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if actual is None:
                try:
                    path.hardlink_to(temporary)
                except FileExistsError:
                    return Blocked(drift, drift_why, drift_how, refusal=True)
            else:
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or path.read_bytes() != expected_content
                ):
                    return Blocked(drift, drift_why, drift_how, refusal=True)
                temporary.replace(path)
            directory = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if descriptor != -1:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return PublishedWholeFile(str(candidate), hashlib.sha256(content).hexdigest())
    except OSError as error:
        return Blocked(
            unavailable,
            f"writing authority failed; authority may already have changed: {error}",
            "restore authority storage, then retry",
        )
