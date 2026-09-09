from pathlib import Path

from des.application.handover import Blocked
from des.application.whole_file_document_publisher import (
    PublishedWholeFile,
    publish_whole_file,
)
from des.domain.distill_document import DistillDocument


def publish_distill_document(
    root: Path, destination: str, document: DistillDocument, request: str
) -> PublishedWholeFile | Blocked:
    return publish_whole_file(
        root,
        destination,
        document.markdown(request).encode(),
        unsafe="UnsafeDistillDestination",
        drift="DistillAuthorityDrift",
        unavailable="DistillAuthorityUnavailable",
    )
