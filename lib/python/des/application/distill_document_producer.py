from pathlib import Path

from des.application.handover import Blocked
from des.application.whole_file_document_publisher import (
    PublishedWholeFile,
    PublishRefusalVocabulary,
    publish_whole_file_revision,
)
from des.domain.distill_document import AcceptanceBrief


def publish_distill_document(
    root: Path,
    destination: str,
    document: AcceptanceBrief,
    request: str,
    prior_document: AcceptanceBrief | None,
) -> PublishedWholeFile | Blocked:
    refusals = PublishRefusalVocabulary(
        unsafe="UnsafeDistillDestination",
        drift="DistillAuthorityDrift",
        unavailable="DistillAuthorityUnavailable",
    )
    return publish_whole_file_revision(
        root,
        destination,
        prior_document.markdown(request).encode()
        if prior_document is not None
        else None,
        document.markdown(request).encode(),
        refusals=refusals,
    )
