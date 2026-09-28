"""Persist the DEVOPS-owned Markdown authority and its canonical facts sidecar."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from des.application.handover import AtomicReplaceWords, Blocked, replace_exact_bytes
from des.domain.operational_document import (
    OperationalDocument,
    OperationalDocumentInvalid,
    operational_facts_from_json,
)


@dataclass(frozen=True, slots=True)
class PublishedOperationalDocument:
    locator: str
    digest: str
    facts_path: str
    sidecar_failure: Blocked | None = None


#: TWO vocabularies, because this producer writes TWO files and they fail
#: differently: the Markdown authority and the canonical facts sidecar name
#: distinct drifts and distinct repairs, and the terminal must send an operator
#: to the file that actually moved.  That distinction is the whole reason this
#: producer reports a mixed outcome rather than one transaction.
_AUTHORITY_WORDS = AtomicReplaceWords(
    unavailable="OperationalAuthorityUnavailable",
    repair="restore authority storage; the complete replacement may already be visible",
    drift="OperationalAuthorityDrift",
    drift_subject="authority",
)
_SIDECAR_WORDS = AtomicReplaceWords(
    unavailable="OperationalAuthorityUnavailable",
    repair="restore OperationalFacts storage; the complete replacement may already be visible",
    drift="OperationalFactsDrift",
    drift_subject="OperationalFacts sidecar",
)


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


def _prior_owned_section(raw: bytes, destination: str, heading: str) -> bytes | Blocked:
    """Prove that the sole sidecar owns this configured authority section."""
    try:
        facts = operational_facts_from_json(raw.decode("utf-8"))
        authority = facts["authority"]
        if authority != {"destination": destination, "heading": heading}:
            return Blocked(
                "OperationalAuthorityIdentityMismatch",
                "the existing OperationalFacts sidecar does not name the configured "
                "DEVOPS destination and supplied authority heading",
                "use the current destination and heading with its matching sidecar",
                refusal=True,
            )
        prior_input = dict(facts)
        prior_input["authority"] = {"heading": heading}
        return (
            OperationalDocument.from_json(json.dumps(prior_input)).markdown().encode()
        )
    except (OperationalDocumentInvalid, UnicodeDecodeError) as error:
        return Blocked(
            "OperationalAuthorityIdentityMismatch",
            "the existing OperationalFacts sidecar is not canonical authority "
            f"identity evidence: {error}",
            "restore the matching canonical OperationalFacts sidecar before replacing",
            refusal=True,
        )


def publish_operational_document(
    root: Path,
    destination: str,
    document: OperationalDocument,
    *,
    replace_current: bool = False,
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
        authority_expected = path.read_bytes() if path.exists() else None
        existing, existing_facts = (
            authority_expected or b"",
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
            owned_lines = owned.splitlines(keepends=True)
            last_content = next(
                (
                    index
                    for index in range(len(owned_lines) - 1, -1, -1)
                    if owned_lines[index].rstrip(b"\r\n")
                ),
                None,
            )
            owned_section = (
                b"".join(owned_lines[: last_content + 1])
                if last_content is not None
                else owned
            )
            delimiter = owned[len(owned_section) :]
            if replace_current:
                # The canonical sidecar proves WHICH authority section may be
                # replaced. That proof is owed whenever a replacement is asked
                # for, not only when the current section already diverges: an
                # identical section with a foreign or absent sidecar is exactly
                # the case where a silent write would adopt someone else's
                # canonical facts.
                if existing_facts is None:
                    return Blocked(
                        "OperationalAuthorityIdentityMismatch",
                        "--replace-current requires the existing canonical "
                        "OperationalFacts sidecar",
                        "restore the matching sidecar before replacing this authority",
                        refusal=True,
                    )
                prior_owned = _prior_owned_section(
                    existing_facts, str(candidate), document.heading
                )
                if isinstance(prior_owned, Blocked):
                    return prior_owned
                if owned_section not in (prior_owned, section):
                    # Two shapes are replaceable: the coherent prior state the
                    # sidecar still owns, and this very section, which is what a
                    # write interrupted between the two files leaves behind.
                    # Anything else is a third party's authority.
                    return Blocked(
                        "OperationalAuthorityIdentityMismatch",
                        "the current DEVOPS section does not equal the canonical "
                        "section owned by its OperationalFacts sidecar",
                        "restore matching authority and sidecar bytes before replacing",
                        refusal=True,
                    )
                rendered = existing[:start] + section + delimiter + existing[end:]
            elif owned_section != section:
                return Blocked(
                    "OperationalAuthorityDrift",
                    "the existing DEVOPS heading has divergent content",
                    "supply --replace-current to replace this owned authority section",
                    refusal=True,
                )
            else:
                rendered = existing
        elif replace_current:
            return Blocked(
                "OperationalAuthorityIdentityMismatch",
                "--replace-current requires the configured DEVOPS destination to "
                "already contain the supplied authority heading",
                "use the current destination and heading, or publish without --replace-current",
                refusal=True,
            )
        else:
            rendered = existing + section
        if (
            existing_facts is not None
            and existing_facts != facts
            and not replace_current
        ):
            return Blocked(
                "OperationalFactsDrift",
                "the existing OperationalFacts sidecar has divergent content",
                "supply --replace-current to replace the canonical facts sidecar",
                refusal=True,
            )
        if rendered != existing:
            operation = "replacing DEVOPS Markdown authority"
            replaced = replace_exact_bytes(
                path, authority_expected, rendered, words=_AUTHORITY_WORDS
            )
            if replaced is not None:
                return replaced
        if existing_facts != facts:
            operation = "replacing OperationalFacts sidecar"
            replaced = replace_exact_bytes(
                sidecar, existing_facts, facts, words=_SIDECAR_WORDS
            )
            if replaced is not None:
                if rendered != existing:
                    return PublishedOperationalDocument(
                        f"{candidate}#{document.heading}",
                        hashlib.sha256(rendered).hexdigest(),
                        str(sidecar_candidate),
                        replaced,
                    )
                return replaced
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
