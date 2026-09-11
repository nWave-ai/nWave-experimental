from pathlib import Path

from des.application.handover import Blocked
from des.application.whole_file_document_publisher import (
    PublishedWholeFile,
    publish_whole_file_revision,
)
from des.domain.distill_document import DistillDocument


def publish_distill_document(
    root: Path,
    destination: str,
    document: DistillDocument,
    request: str,
    prior_document: DistillDocument | None,
) -> PublishedWholeFile | Blocked:
    return publish_whole_file_revision(
        root,
        destination,
        prior_document.markdown(request).encode()
        if prior_document is not None
        else None,
        document.markdown(request).encode(),
        unsafe="UnsafeDistillDestination",
        drift="DistillAuthorityDrift",
        unavailable="DistillAuthorityUnavailable",
    )
