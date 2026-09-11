"""Persist the constructed DISCUSS authority through the shared whole-file seam."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from des.application.whole_file_document_publisher import (
    PublishedWholeFile,
    publish_whole_file,
    publish_whole_file_revision,
)


if TYPE_CHECKING:
    from des.application.handover import Blocked
    from des.domain.discuss_document import DiscussDocument


def publish_discuss_document(
    root: Path,
    destination: str,
    document: DiscussDocument,
    *,
    replace_current: bool = False,
) -> PublishedWholeFile | Blocked:
    """Publish the owned brief, replacing the current projection when asked.

    Without ``replace_current`` the brief is create-or-exact-retry: a divergent
    existing projection is drift, never an implicit overwrite.  With it, the
    caller has already proved this authority's identity against the persisted
    canonical facts, so the current bytes are the revision being superseded.
    """
    content = document.markdown().encode()
    if not replace_current:
        return publish_whole_file(
            root,
            destination,
            content,
            unsafe="UnsafeDiscussDestination",
            drift="DiscussAuthorityDrift",
            unavailable="DiscussAuthorityUnavailable",
        )
    candidate = Path(destination)
    expected: bytes | None = None
    if not candidate.is_absolute() and ".." not in candidate.parts:
        try:
            expected = (root / candidate).read_bytes()
        except OSError:
            expected = None
    return publish_whole_file_revision(
        root,
        destination,
        expected,
        content,
        unsafe="UnsafeDiscussDestination",
        drift="DiscussAuthorityDrift",
        unavailable="DiscussAuthorityUnavailable",
    )
