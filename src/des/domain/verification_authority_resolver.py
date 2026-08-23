"""Resolve one `Verification authority locator:` DELEGATION to the literal
script block the cited authority document owns (SF friction 2026-08-21).

The sister's real Slice brief declares no per-line `Verification command:`
labels -- it delegates: prose naming an ADR order, a typed
``Verification authority locator: `<repo-relative-doc>#<heading-anchor>```
line (same declarative family as ``Oracle target locator:``), and in the
cited document a heading followed by the marker sentence ("The exact
clean-checkout verification order is:") and ONE fenced block carrying the
LITERAL sequence -- an authority SCRIPT (assignments, command substitution,
``!`` negations, pipes), never argv-splittable. The marker sentence is a
prose convention for the human reader; the machine anchor is the FIRST
fenced block after the heading, within that heading's own section.

This resolver extracts the block VERBATIM and pairs it with a content
digest (sha256 over the lines joined with ``\\n``, UTF-8, no trailing
newline) so the consumer can verify fidelity against the owning document
before faithful execution. Nothing here interprets, splits, or executes a
line. Every failure to resolve is typed --
:class:`UnresolvedAuthorityReference` naming its reason, or
:class:`AmbiguousAuthorityReference` naming every colliding heading when
the normalized anchor key matches MORE THAN ONE heading (first-match
would silently bind a DIFFERENT authority's order than the one the brief
meant) -- never a silent fallback (the caller refuses loudly, GDP-6).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class LiteralScriptBlock:
    """The resolved delegation, carried BY-REFERENCE into the contract.

    The contract's carried copy of ``lines`` is a display-only projection:
    executors and verifiers bind exclusively to a FRESH resolution of the
    locator (this class, produced at their own read time), digest-checked
    against the contract's declared ``content-digest`` -- never to the
    lines the contract JSON happens to carry."""

    locator: str
    content_digest: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnresolvedAuthorityReference:
    """A declared delegation this resolver could not ground -- typed, so
    the caller's refusal names the exact precondition that failed."""

    locator: str
    reason: str


@dataclass(frozen=True, slots=True)
class AmbiguousAuthorityReference:
    """A declared delegation whose normalized anchor key matches MORE THAN
    ONE heading in the cited document (sister counterexample 2026-08-21:
    ``D-112.14 -- A-B`` and ``D-11214 AB`` normalize identically). Typed
    and candidate-naming, so the caller's refusal shows the operator the
    exact colliding headings -- never a silent first-match bind."""

    locator: str
    candidates: tuple[str, ...]
    reason: str


_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*$")
_NON_SLUG_RUN_RE = re.compile(r"[^a-z0-9]+")


def _anchor_key(text: str) -> str:
    """Normalized anchor identity: lowercase with every non-alphanumeric
    DROPPED. The hand-written spelling of an anchor (``d-112.14-...``,
    dot kept), the GitHub-generated one (``d-11214--...``, dot dropped and
    the removed em dash leaving a double hyphen) and the heading itself
    all normalize to the same key -- matching is a law about the heading's
    identity, never about how an author or a generator spelled the
    punctuation."""
    return _NON_SLUG_RUN_RE.sub("", text.lower())


def resolve_verification_authority(
    repo_root: Path, locator: str
) -> LiteralScriptBlock | UnresolvedAuthorityReference | AmbiguousAuthorityReference:
    """The literal script block ``locator`` (``<repo-relative-doc>#
    <heading-anchor>``) delegates to, or a typed unresolved/ambiguous
    reference."""
    doc_part, separator, anchor = locator.partition("#")
    doc_part, anchor = doc_part.strip(), anchor.strip()
    if not separator or not doc_part or not anchor:
        return UnresolvedAuthorityReference(
            locator,
            "malformed locator: expected '<repo-relative-doc>#<heading-anchor>'",
        )
    doc_reference = PurePosixPath(doc_part)
    if doc_reference.is_absolute() or ".." in doc_reference.parts:
        return UnresolvedAuthorityReference(
            locator,
            f"the document reference {doc_part!r} escapes the repository "
            "(absolute or parent-traversal path) -- an authority must be a "
            "repo-relative document",
        )
    document = repo_root / doc_reference
    if not document.is_file():
        return UnresolvedAuthorityReference(
            locator, f"no document exists at {doc_part!r} under the repository root"
        )
    # The lexical check above cannot see a SYMLINK: a link that lives
    # under the repository but points outside it satisfies both the
    # no-`..` rule and `is_file()`. Decide on the PROPERTY (the real
    # physical path), never the designation (the link's own spelling).
    try:
        resolved_document = document.resolve(strict=True)
        resolved_root = repo_root.resolve()
    except OSError as exc:
        return UnresolvedAuthorityReference(
            locator, f"the document at {doc_part!r} cannot be resolved ({exc})"
        )
    if not resolved_document.is_relative_to(resolved_root):
        return UnresolvedAuthorityReference(
            locator,
            f"the document at {doc_part!r} resolves to "
            f"{resolved_document} outside the repository root (a symlink "
            "escaping the repository is not a repo-relative authority)",
        )
    try:
        text = document.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return UnresolvedAuthorityReference(
            locator, f"the document at {doc_part!r} cannot be read ({exc})"
        )

    lines = text.splitlines()
    target_key = _anchor_key(anchor)
    matches: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        heading = _HEADING_RE.match(line)
        if heading and _anchor_key(heading.group("text")) == target_key:
            matches.append((index, len(heading.group("hashes")), heading.group("text")))
    if not matches:
        return UnresolvedAuthorityReference(
            locator, f"no heading in {doc_part!r} matches the anchor {anchor!r}"
        )
    if len(matches) > 1:
        # Anchor identity is a normalized key, so DISTINCT headings can
        # collide (``D-112.14 -- A-B`` vs ``D-11214 AB``). Binding the
        # first match would silently execute a different authority's
        # order than the brief meant -- refuse, naming every candidate.
        candidates = tuple(text for _, _, text in matches)
        listed = ", ".join(f"{text!r} (line {index + 1})" for index, _, text in matches)
        return AmbiguousAuthorityReference(
            locator,
            candidates,
            f"the anchor {anchor!r} matches {len(matches)} headings in "
            f"{doc_part!r}: {listed} -- they normalize to the same anchor "
            "key, so the reference does not name exactly one section",
        )
    heading_index, heading_level, _ = matches[0]

    section_end = len(lines)
    for index in range(heading_index + 1, len(lines)):
        heading = _HEADING_RE.match(lines[index])
        if heading and len(heading.group("hashes")) <= heading_level:
            section_end = index
            break

    fence_open: int | None = None
    block: list[str] | None = None
    for index in range(heading_index + 1, section_end):
        if not lines[index].strip().startswith("```"):
            continue
        if fence_open is None:
            fence_open = index
        else:
            block = lines[fence_open + 1 : index]
            break
    if block is None:
        return UnresolvedAuthorityReference(
            locator,
            f"no complete fenced code block follows the heading {anchor!r} "
            f"within its own section of {doc_part!r}",
        )
    if not any(line.strip() for line in block):
        return UnresolvedAuthorityReference(
            locator,
            f"the fenced block under the heading {anchor!r} in {doc_part!r} "
            "is empty -- it carries no verification order",
        )

    digest = hashlib.sha256("\n".join(block).encode("utf-8")).hexdigest()
    return LiteralScriptBlock(
        locator=locator,
        content_digest=f"sha256:{digest}",
        lines=tuple(block),
    )
