"""Persist one deterministic feature-evolution authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.application.handover import Blocked
from des.application.whole_file_document_publisher import publish_whole_file


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.evolution_document import EvolutionDocument


@dataclass(frozen=True, slots=True)
class PublishedEvolutionDocument:
    locator: str
    digest: str


def publish_evolution_document(
    root: Path, destination: str, document: EvolutionDocument
) -> PublishedEvolutionDocument | Blocked:
    published = publish_whole_file(
        root,
        destination,
        document.markdown().encode(),
        unsafe="UnsafeEvolutionDestination",
        drift="EvolutionAuthorityDrift",
        unavailable="EvolutionAuthorityUnavailable",
        unsafe_why="documents.evolution.destination must be a safe repository-relative Markdown file",
        unsafe_how="set documents.evolution.destination to a repository-relative .md file",
        regular_why="an existing evolution destination must be a regular file",
        regular_how="choose a regular evolution authority path",
        drift_why="the existing evolution document has divergent content",
        drift_how="use a distinct explicit feature identity or reconcile the authority",
    )
    if isinstance(published, Blocked):
        return published
    return PublishedEvolutionDocument(published.locator, published.digest)
