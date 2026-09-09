"""Persist the constructed DISCUSS authority through the shared whole-file seam."""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.application.whole_file_document_publisher import (
    PublishedWholeFile,
    publish_whole_file,
)


if TYPE_CHECKING:
    from pathlib import Path

    from des.application.handover import Blocked
    from des.domain.discuss_document import DiscussDocument


def publish_discuss_document(
    root: Path, destination: str, document: DiscussDocument
) -> PublishedWholeFile | Blocked:
    return publish_whole_file(
        root,
        destination,
        document.markdown().encode(),
        unsafe="UnsafeDiscussDestination",
        drift="DiscussAuthorityDrift",
        unavailable="DiscussAuthorityUnavailable",
    )
