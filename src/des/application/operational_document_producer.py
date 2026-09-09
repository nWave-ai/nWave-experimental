"""Persist the DEVOPS-owned Markdown authority and its canonical facts sidecar."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.application.handover import Blocked


if TYPE_CHECKING:
    from des.domain.operational_document import OperationalDocument


@dataclass(frozen=True, slots=True)
class PublishedOperationalDocument:
    locator: str
    digest: str
    facts_path: str


def _safe(root: Path, candidate: Path) -> bool:
    try:
        return (
            not candidate.is_absolute()
            and ".." not in candidate.parts
            and bool(candidate.parts)
            and (root / candidate).resolve(strict=False).is_relative_to(root.resolve())
        )
    except OSError:
        return False


def publish_operational_document(
    root: Path, destination: str, document: OperationalDocument
) -> PublishedOperationalDocument | Blocked:
    candidate = Path(destination)
    if not _safe(root, candidate) or candidate.suffix != ".md":
        return Blocked(
            "UnsafeOperationalDestination",
            "documents.devops.destination must be a safe repository-relative Markdown file",
            "set documents.devops.destination to a repository-relative .md file",
            refusal=True,
        )
    sidecar_candidate = candidate.with_suffix(".operational-facts.json")
    path, sidecar = root / candidate, root / sidecar_candidate
    section, facts = document.markdown().encode(), document.facts_bytes(str(candidate))
    operation = "preparing DEVOPS artifacts"
    try:
        for target in (path, sidecar):
            if target.is_symlink() or (target.exists() and not target.is_file()):
                return Blocked(
                    "UnsafeOperationalDestination",
                    "an existing DEVOPS artifact must be a regular file",
                    "choose regular authority and sidecar paths",
                    refusal=True,
                )
        existing, existing_facts = (
            (path.read_bytes() if path.exists() else b""),
            (sidecar.read_bytes() if sidecar.exists() else None),
        )
        marker = f"## {document.heading}".encode()
        offsets: list[int] = []
        cursor = 0
        for line in existing.splitlines(keepends=True):
            if line.rstrip(b"\r\n") == marker:
                offsets.append(cursor)
            cursor += len(line)
        if len(offsets) > 1:
            return Blocked(
                "OperationalAuthorityAmbiguous",
                "the existing DEVOPS heading occurs more than once",
                "remove the ambiguity before publishing",
                refusal=True,
            )
        if offsets:
            start = offsets[0]
            following = existing.find(b"\n## ", start + len(marker))
            end = len(existing) if following < 0 else following + 1
            owned = existing[start:end]
            if not owned.startswith(section) or owned[len(section) :].strip(b"\r\n"):
                return Blocked(
                    "OperationalAuthorityDrift",
                    "the existing DEVOPS heading has divergent content",
                    "supply explicit supersession evidence before replacing the owned section",
                    refusal=True,
                )
            rendered = existing
        else:
            rendered = existing + section
        if existing_facts is not None and existing_facts != facts:
            return Blocked(
                "OperationalFactsDrift",
                "the existing OperationalFacts sidecar has divergent content",
                "supply explicit supersession evidence before replacing the sidecar",
                refusal=True,
            )
        if rendered != existing:
            path.parent.mkdir(parents=True, exist_ok=True)
            operation = "writing DEVOPS Markdown authority"
            path.write_bytes(rendered)
        if existing_facts != facts:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            operation = "writing OperationalFacts sidecar"
            sidecar.write_bytes(facts)
        return PublishedOperationalDocument(
            f"{candidate}#{document.heading}",
            hashlib.sha256(rendered).hexdigest(),
            str(sidecar_candidate),
        )
    except OSError as error:
        partial_change = (
            "the Markdown authority and/or OperationalFacts sidecar may already have changed"
            if operation == "writing OperationalFacts sidecar"
            else "the Markdown authority may already have changed"
            if operation == "writing DEVOPS Markdown authority"
            else "no artifact change was confirmed"
        )
        return Blocked(
            "OperationalAuthorityUnavailable",
            f"{operation} failed; {partial_change}: {error}",
            "inspect and reconcile the DEVOPS Markdown authority and OperationalFacts sidecar, "
            "restore authority storage, then retry",
        )
