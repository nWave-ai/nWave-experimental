"""Persist the DESIGN-owned section of a configured architecture authority."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from des.application.handover import (
    AtomicReplaceWords,
    Blocked,
    StoredHandover,
    replace_exact_bytes,
)
from des.domain.verification_authority_resolver import (
    AmbiguousAuthorityReference,
    UnresolvedAuthorityReference,
    resolve_authority_section,
)
from des.runtime.spawn import GIT_TIMEOUT_ENV, git_timeout_seconds, spawn


class DesignAuthoritySection(Protocol):
    """What this producer needs of the value it publishes, and nothing else.

    TYPE-ONLY and structural: the closed-document `DesignDocument` and the
    typed-facts `DesignFactsSection` are two renderings of one architecture
    decision, and both are published by THIS producer so that one law decides
    what `<document>#<heading>` names.  Widening the parameter rather than
    adding a second publisher is what keeps the two paths from drifting apart
    on ownership, ambiguity, drift and read-back resolution.
    """

    @property
    def heading(self) -> str: ...

    def markdown(self) -> str: ...


@dataclass(frozen=True, slots=True)
class PublishedDesignDocument:
    """The authority projection and whether this invocation persisted it."""

    locator: str
    digest: str
    authority_persisted: bool


#: What a failed replacement of the DESIGN authority calls itself.  The words
#: are this producer's own, not the handover's: the file being replaced is a
#: tracked architecture document, so naming its drift `HandoverDrift` would send
#: an operator to inspect the wrong artifact.
_AUTHORITY_WORDS = AtomicReplaceWords(
    unavailable="DesignAuthorityUnavailable",
    repair="restore authority storage; the complete replacement may already be visible",
    drift="DesignAuthorityDrift",
    drift_subject="authority",
)


def _tracked(root: Path, path: Path) -> bool | Blocked:
    """Return Git tracking state, or an indeterminate no-write outcome."""
    try:
        result = spawn(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--error-unmatch",
                "--",
                str(path.relative_to(root)),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=git_timeout_seconds(),
            timeout_env=GIT_TIMEOUT_ENV,
        )
    except subprocess.TimeoutExpired as error:
        return Blocked(
            "DesignAuthorityUnavailable",
            f"Git did not answer the authority tracking probe: {error}",
            "restore Git responsiveness and retry before publishing authority bytes",
        )
    return result.returncode == 0


def _unsafe_relative() -> Blocked:
    return Blocked(
        "UnsafeDesignDestination",
        "documents.design.destination must be a safe repository-relative file",
        "set documents.design.destination to a repository-relative authority file",
        refusal=True,
    )


def _unsafe_regular() -> Blocked:
    """The SHAPE refusal alone, now that tracking is no longer a precondition.

    This used to answer for a symlink or non-regular destination AND for an
    untracked one.  Being tracked stopped being required, so a HOW telling an
    operator to «choose a tracked regular authority file» when the real defect
    is a SYMLINK would name a repair that does not work.  The untracked arm
    answers through :func:`_unbound_section` instead.
    """
    return Blocked(
        "UnsafeDesignDestination",
        "an existing DESIGN destination must be a regular file",
        "choose a regular authority file",
        refusal=True,
    )


#: The ONE WHY both untracked arms share.  They differ only in HOW, because the
#: honest repair differs: one has an offending heading to quote, the other has
#: only bytes, and inventing a heading to name there would be a refusal that
#: lies about what it read.
_UNTRACKED_WHY = (
    "an untracked DESIGN destination may hold only sections this Request bound"
)


def _unbound_section(existing: bytes, headings: frozenset[str]) -> Blocked | None:
    """Whether these untracked bytes hold anything this Request did not bind.

    A line owns a section exactly as :func:`publish_design_document` already
    recognizes its own -- `line.rstrip(b'\\r\\n')` against `f'## {heading}'` --
    so the two halves of ONE publisher cannot disagree about what owns a
    section.  Markers are matched by EQUALITY with a bound heading, never by the
    consumer resolver's normalized anchor key: that key exists to make a
    CITATION resolve, and using it here would admit a section whose spelling
    merely collides with one this Request bound.

    Zero or whitespace-only bytes own no section and are admitted -- there is
    nothing of anyone else's to destroy and the append is the whole write.
    Non-empty bytes holding no `## ` line at all are refused: the step has no
    evidence it wrote them.
    """
    if not existing.strip():
        return None
    bound = {f"## {heading}".encode() for heading in headings}
    owned = False
    for line in existing.splitlines():
        marker = line.rstrip(b"\r\n")
        if not marker.startswith(b"## "):
            continue
        owned = True
        if marker not in bound:
            heading = marker[3:].decode(errors="replace")
            return Blocked(
                "UnsafeDesignDestination",
                _UNTRACKED_WHY,
                f'the untracked destination holds the section "## {heading}", '
                "which no value of this Request bound; track it with Git, or "
                "move that section out before re-invoking this step",
                refusal=True,
            )
    if not owned:
        return Blocked(
            "UnsafeDesignDestination",
            _UNTRACKED_WHY,
            "the untracked destination holds bytes no DESIGN section owns; "
            "track it with Git, or move those bytes out before re-invoking "
            "this step",
            refusal=True,
        )
    return None


def bound_authority_headings(
    stored: StoredHandover, destination: str
) -> frozenset[str]:
    """Every heading this Request has published INTO `destination`.

    The value headings plus the shared feature heading: one collision set for
    the value path and the shared path.
    """
    shared = stored.shared_design
    if shared is None:
        return bound_value_headings(stored, destination)
    document, _, heading = shared.authority_locator.partition("#")
    return bound_value_headings(stored, destination) | (
        frozenset({heading}) if document == destination else frozenset()
    )


def bound_value_headings(stored: StoredHandover, destination: str) -> frozenset[str]:
    """The headings this Request's VALUES have published INTO `destination`.

    Derived once, from the handover, and filtered by this destination: a
    heading bound into a DIFFERENT document is no evidence at all about this
    file, and an unbound value contributes nothing.  Both the legacy bare
    locator string and the typed-facts form are read, because a restored older
    handover must weigh the same as a current one.
    """
    headings: set[str] = set()
    for value in stored.values:
        authority = value.authority
        if isinstance(authority, str):
            locator = authority
        elif authority is None:
            continue
        else:
            locator = authority.authority_locator
        document, separator, heading = locator.partition("#")
        if separator and heading and document == destination:
            headings.add(heading)
    return frozenset(headings)


def _destination_path(root: Path, destination: str) -> Path | Blocked:
    """The destination as a path inside `root`, or why it is not one."""
    candidate = Path(destination)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        return _unsafe_relative()
    path = root / candidate
    try:
        path.resolve(strict=False).relative_to(root.resolve())
    except ValueError:
        return Blocked(
            "UnsafeDesignDestination",
            "documents.design.destination resolves outside the repository",
            "set documents.design.destination to a repository-relative authority file",
            refusal=True,
        )
    return path


def _unsafe_shape(path: Path) -> Blocked | None:
    """Refuse a destination that exists as anything but a regular file."""
    if path.is_symlink():
        return _unsafe_regular()
    if path.exists() and not path.is_file():
        return _unsafe_regular()
    return None


def judge_design_destination(
    root: Path,
    destination: str,
    published_headings: frozenset[str] = frozenset(),
) -> Blocked | None:
    """Judge the DESTINATION ALONE, with no rendered section in hand.

    This is the part of `publish_design_document`'s rule that depends on
    nothing a turn produces: path shape, resolution inside the repository,
    regular-file shape, and -- for an untracked destination -- whether every
    section it holds is one `published_headings` names, which the caller derives
    from the handover through :func:`bound_authority_headings`.  The default
    empty set is the conservative rule: nothing was published, so an untracked
    destination carrying anything at all is refused.  Because it is decidable
    BEFORE an architect turn is bought, a caller that would otherwise pay for a
    turn and then be refused can ask here first and refuse at zero cost, printing the
    very same refusal bytes, because both callers compose the same private
    steps rather than two spellings of one rule.

    It deliberately does NOT know about the byte-identity recovery widening:
    that widening compares the destination against a section that only exists
    once the turn has answered, so it stays where the section is, inside
    `publish_design_document`.

    A destination judged safe here can still be moved or replaced by another
    process before the turn ends.  This is a COST gate, never a lock, and the
    post-turn judgement is kept precisely because of that window.
    """
    path = _destination_path(root, destination)
    if isinstance(path, Blocked):
        return path
    try:
        shape = _unsafe_shape(path)
        if shape is not None:
            return shape
        if not path.exists():
            return None
        tracked = _tracked(root, path)
        if isinstance(tracked, Blocked):
            return tracked
        if tracked:
            return None
        # A destination THIS Request wrote is safe to extend: the append writes
        # only past the end, and every section already there is one of ours.
        return _unbound_section(path.read_bytes(), published_headings)
    except OSError as error:
        return Blocked(
            "DesignAuthorityUnavailable", str(error), "restore authority storage"
        )


def _blank_line_separator(snapshot: bytes) -> bytes:
    """Return only the separator needed before appending an owned H2 section."""
    if not snapshot:
        return b""
    last = snapshot.splitlines(keepends=True)[-1]
    if not last.endswith((b"\n", b"\r")):
        return (b"\r\n" if b"\r\n" in snapshot else b"\n") * 2
    if not last.rstrip(b"\r\n"):
        return b""
    return last[len(last.rstrip(b"\r\n")) :]


#: The empty heading set, bound once so the default is a named value rather than
#: a `frozenset()` call in a signature, which is RUF009.
_NO_PUBLISHED_HEADINGS: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True, kw_only=True)
class DesignPublicationWidenings:
    """The explicit widenings ONE invocation is authorized to apply.

    Every field admits a write this publisher refuses by default, so the four
    together are the whole of what a caller may loosen. Keyword-only, and that is
    load-bearing rather than decorative: all four are `bool`, so a positional
    permutation constructs cleanly and silently authorizes a different write.
    Nothing here would catch it, because `typecheck` is executed by no workflow.
    """

    allow_untracked_recovery: bool = False
    replace_current: bool = False
    migrate_legacy_rendering: bool = False
    replace_unbound: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class DesignAuthorityBinding:
    """What this Request has ALREADY bound in the destination document.

    Keyword-only for the same reason, though the swap here fails rather than
    lies: a `str | None` and a `frozenset[str]` transposed would compare a set
    against a locator and iterate a string as headings.
    """

    authority_locator: str | None = None
    published_headings: frozenset[str] = _NO_PUBLISHED_HEADINGS


#: The invocation that widens nothing and claims no prior binding.
_NO_WIDENINGS = DesignPublicationWidenings()
_UNBOUND_AUTHORITY = DesignAuthorityBinding()


def publish_design_document(
    root: Path,
    destination: str,
    document: DesignAuthoritySection,
    *,
    widenings: DesignPublicationWidenings = _NO_WIDENINGS,
    binding: DesignAuthorityBinding = _UNBOUND_AUTHORITY,
) -> PublishedDesignDocument | Blocked:
    allow_untracked_recovery = widenings.allow_untracked_recovery
    replace_current = widenings.replace_current
    migrate_legacy_rendering = widenings.migrate_legacy_rendering
    replace_unbound = widenings.replace_unbound
    authority_locator = binding.authority_locator
    published_headings = binding.published_headings
    candidate = Path(destination)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        return _unsafe_relative()
    expected_locator = f"{candidate}#{document.heading}"
    if authority_locator is not None and authority_locator != expected_locator:
        return Blocked(
            "DesignAuthorityIdentityMismatch",
            "the configured destination and manifest heading do not equal the "
            "selected value's persisted authority locator",
            "keep the original configured path and heading when replacing this value",
            refusal=True,
        )
    path = _destination_path(root, destination)
    if isinstance(path, Blocked):
        return path
    section = document.markdown().encode()
    try:
        shape = _unsafe_shape(path)
        if shape is not None:
            return shape
        exists = path.exists()
        existing = path.read_bytes() if exists else None
        tracked = _tracked(root, path) if exists else True
        if isinstance(tracked, Blocked):
            return tracked
        if (migrate_legacy_rendering or replace_unbound) and (
            not exists or not tracked
        ):
            return Blocked(
                "DesignUnboundRecoveryUnavailable",
                "unbound DESIGN recovery requires an existing tracked authority",
                "restore the tracked authority, then rerun the explicit recovery",
                refusal=True,
            )
        if exists and not tracked:
            # TWO widenings, and the arm refuses only when BOTH decline.  The
            # byte-identity recovery admits an authority-first interruption
            # whose section is not yet bound in the handover, so it is not
            # subsumed by the bound-heading rule and must not be replaced by it.
            if not (allow_untracked_recovery and existing == section):
                unbound = _unbound_section(existing or b"", published_headings)
                if unbound is not None:
                    return unbound
        snapshot = existing or b""
        marker = f"## {document.heading}".encode()
        lines = snapshot.splitlines(keepends=True)
        offsets: list[int] = []
        cursor = 0
        for line in lines:
            if line.rstrip(b"\r\n") == marker:
                offsets.append(cursor)
            cursor += len(line)
        if len(offsets) > 1:
            return Blocked(
                "DesignAuthorityAmbiguous",
                "the existing DESIGN heading occurs more than once",
                "supply explicit supersession evidence before replacing an owned authority section",
                refusal=True,
            )
        if offsets:
            start = offsets[0]
            next_h2 = len(snapshot)
            cursor = 0
            for line in lines:
                if cursor > start and line.rstrip(b"\r\n").startswith(b"## "):
                    next_h2 = cursor
                    break
                cursor += len(line)
            owned = snapshot[start:next_h2]
            # The section owns its final content-line terminator.  Blank lines
            # between it and a following H2 are the surrounding document's
            # delimiter, so a correction must splice them back byte-for-byte.
            # ``splitlines(keepends=True)`` lets this work for either newline
            # convention without normalizing any human-owned bytes.
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
            # Separators belong to the surrounding document.  The canonical
            # section must be the complete owned content before those bytes.
            if owned_section != section:
                legacy_render = getattr(document, "legacy_markdown_v1", None)
                is_exact_legacy_render = (
                    callable(legacy_render)
                    and owned_section == legacy_render().encode()
                )
                if (
                    replace_current
                    or replace_unbound
                    or (migrate_legacy_rendering and is_exact_legacy_render)
                ):
                    rendered = (
                        snapshot[:start] + section + delimiter + snapshot[next_h2:]
                    )
                else:
                    return Blocked(
                        "DesignAuthorityDrift",
                        "the existing DESIGN heading has divergent content",
                        "supply --replace-current to replace this owned authority section",
                        refusal=True,
                    )
            else:
                rendered = snapshot
        else:
            rendered = snapshot + _blank_line_separator(snapshot) + section
        if rendered != snapshot:
            replaced = replace_exact_bytes(
                path, existing, rendered, words=_AUTHORITY_WORDS
            )
            if replaced is not None:
                return replaced
        # A value may bind only to a section the DOCUMENT ON DISK resolves.
        # The rendered buffer is what this step INTENDED; the bytes now
        # present are what a consumer will actually read, and the producer
        # never repairs the document to make an unreachable heading
        # reachable.  Resolution is judged with the consumer's own resolver
        # so one law decides what `<doc>#<heading>` names.
        on_disk = path.read_bytes()
        locator = f"{candidate}#{document.heading}"
        try:
            text = on_disk.decode()
        except UnicodeDecodeError as error:
            return Blocked(
                "DesignAuthorityUnavailable",
                f"the DESIGN authority could not be decoded as UTF-8: {error}",
                "restore authority storage; the written section may already be visible",
            )
        resolved = resolve_authority_section(
            text, document.heading, locator=locator, doc_part=str(candidate)
        )
        if isinstance(
            resolved, (UnresolvedAuthorityReference, AmbiguousAuthorityReference)
        ):
            return Blocked(
                "DesignAuthorityUnlocatable",
                f"the DESIGN authority document {candidate} does not resolve the "
                f"declared section {locator}: {resolved.reason}",
                "repair the document so the declared heading begins its own line, "
                "then re-invoke this step",
                refusal=True,
            )
        # The digest measures the file, never the buffer: a concurrent edit
        # elsewhere in the document is reported truthfully rather than refused.
        return PublishedDesignDocument(
            locator,
            hashlib.sha256(on_disk).hexdigest(),
            rendered != snapshot,
        )
    except OSError as error:
        return Blocked(
            "DesignAuthorityUnavailable", str(error), "restore authority storage"
        )
