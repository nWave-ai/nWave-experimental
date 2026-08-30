"""Detect a subject workspace's own declared whole-suite test command.

K4 Run 12 debrief: `verification-scope.commands` only ever named the new
oracle's own narrow test (`hc.api.tests.test_maintenance_windows`), never
the subject's whole-suite command its own root `CLAUDE.md` already states
(`Run the subject's own tests: k4-fixture-venv/bin/python manage.py test
hc.api --noinput`). Regressions outside the narrow oracle (an N+1 query, two
stale pinned assertions, a crash on unsaved `Check` instances) were invisible
to BASELINE/GREEN and only surfaced through 3 reviewer rounds.

There is no dedicated schema field for this (`nWave/schemas/
thin-delivery-contract.schema.json`'s `verificationScope` only has
`commands`, `additionalProperties: false`) -- detection reads the workspace's
own root `CLAUDE.md`, declaratively, the same document DISTILL/ATD already
read for project facts. Python-only, no shell, no `git`.

Matching is deliberately narrow to avoid a false trigger on unrelated prose
that merely contains a keyword (e.g. this repo's own CLAUDE.md says "Never
run the whole suite" as a swarm-safety rule, with no command attached): a
line must carry a whole-suite keyword AND a `label: `command`` shape AND the
command text itself must mention "test". No match at all means nothing to
check -- silence is not treated as evidence of a missing command (`Missing
facts return to their owner; DISTILL never guesses them`).
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from des.domain.verification_authority_resolver import (
    LiteralScriptBlock,
    resolve_verification_authority,
)


_WHOLE_SUITE_KEYWORDS = (
    "own tests",
    "full suite",
    "whole suite",
    "all tests",
    "test suite",
    "entire suite",
)
_LABELED_COMMAND = re.compile(r":\s*`([^`]+)`")


@dataclass(frozen=True, slots=True)
class PreservationVector:
    """Base-owned argv plus the exact source bytes that authorized it."""

    argv: tuple[tuple[str, ...], ...]
    sources: tuple[tuple[str, str], ...]


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _introduced(argv: tuple[str, ...], excluded: set[str]) -> bool:
    normalized = {path.removeprefix("./") for path in excluded}
    return any(token.removeprefix("./") in normalized for token in argv)


def _command_argv(command: dict) -> list[str]:
    executable = command.get("executable", {})
    path = executable.get("path")
    head = str(executable.get("name") or path or "")
    # The schema names a repository executable as a repository-relative path;
    # subprocess does not search the current directory for that form.  Project
    # it to an explicit relative argv here, once, rather than making every
    # constructor accidentally depend on the ambient PATH.
    if (
        executable.get("kind") == "repository"
        and isinstance(path, str)
        and path
        and not path.startswith("./")
    ):
        head = f"./{path}"
    return [head, *command.get("arguments", [])]


def _argv_sources(
    repo_root: Path, argv: tuple[str, ...]
) -> tuple[tuple[str, str], ...]:
    """B-owned repository files explicitly named by an argv.

    Contract JSON may be new C bytes, so it cannot be the preserved source.
    A command is nevertheless reconstructible when its direct script/test
    operands resolve to regular B files.  Pure ambient commands (for example
    ``git diff --check``) have no byte owner and are honestly an EvidenceGap.
    """
    sources: list[tuple[str, str]] = []
    for token in argv:
        if not token or token.startswith("-") or Path(token).is_absolute():
            continue
        relative = Path(token.removeprefix("./"))
        if not relative.parts or any(part == ".." for part in relative.parts):
            continue
        file = repo_root / relative
        if file.is_file() and not file.is_symlink():
            sources.append((relative.as_posix(), _digest(file.read_bytes())))
    if not sources:
        raise ValueError("EvidenceGap: command has no repository-native base source")
    return tuple(sources)


def _literal_vector(repo_root: Path, literal: object) -> PreservationVector:
    """Admit only the one non-opaque literal form the ADR permits.

    The normal delegated script is intentionally opaque.  It can become a
    preservation vector solely when its freshly-resolved one-line authority is
    a direct, executable, repository-relative script at B.  Both the owning
    document and the script become source blobs, so a later candidate cannot
    silently swap either.
    """
    if not isinstance(literal, dict):
        raise ValueError("EvidenceGap: malformed literal preservation authority")
    locator = literal.get("locator")
    digest = literal.get("content-digest")
    carried = literal.get("lines")
    if (
        not isinstance(locator, str)
        or not isinstance(digest, str)
        or not isinstance(carried, list)
        or not all(isinstance(line, str) for line in carried)
    ):
        raise ValueError("EvidenceGap: malformed literal preservation authority")
    resolved = resolve_verification_authority(repo_root, locator)
    if (
        not isinstance(resolved, LiteralScriptBlock)
        or resolved.content_digest != digest
        or tuple(carried) != resolved.lines
    ):
        raise ValueError(
            "EvidenceGap: literal authority does not agree with base bytes"
        )
    # A script block remains opaque unless exactly one direct argv invocation
    # names exactly one in-repository executable.  Shell syntax, interpreters,
    # pipelines and multiple lines all retain their existing feature-authority
    # meaning and cannot masquerade as preservation.
    if len(resolved.lines) != 1:
        raise ValueError("EvidenceGap: literal preservation script is ambiguous")
    try:
        argv = tuple(shlex.split(resolved.lines[0]))
    except ValueError as exc:
        raise ValueError(
            "EvidenceGap: literal preservation script is not argv-shaped"
        ) from exc
    if len(argv) != 1 or not argv[0] or Path(argv[0]).is_absolute():
        raise ValueError(
            "EvidenceGap: literal preservation script is not a direct repository script"
        )
    script_rel = Path(argv[0])
    if any(part == ".." for part in script_rel.parts):
        raise ValueError("EvidenceGap: literal preservation script escapes repository")
    script = repo_root / script_rel
    document = repo_root / locator.split("#", 1)[0]
    if not document.is_file() or not script.is_file() or not os.access(script, os.X_OK):
        raise ValueError(
            "EvidenceGap: literal preservation script is not executable at B"
        )
    return PreservationVector(
        (argv,),
        (
            (locator.split("#", 1)[0], _digest(document.read_bytes())),
            (script_rel.as_posix(), _digest(script.read_bytes())),
        ),
    )


def resolve_preservation_vector(
    repo_root: Path,
    contract: dict,
    *,
    excluded: set[str] = frozenset(),
    contract_locator: str = "",
) -> PreservationVector:
    """Resolve ordered B-owned argv plus their exact B source blobs.

    Green/executable qualification is intentionally performed by the caller in
    the pristine worktree before any closure commit exists.  This resolver
    makes the authority and path exclusion deterministic; construction makes
    the environment claim observable.
    """
    claude = repo_root / "CLAUDE.md"
    commands: list[tuple[str, ...]] = []
    sources: list[tuple[str, str]] = []
    literal = contract.get("verification-scope", {}).get("literal-script-block")
    if literal:
        return _literal_vector(repo_root, literal)
    declared = declared_whole_suite_command(repo_root)
    if declared is not None and claude.is_file():
        commands.append(tuple(declared))
        sources.append(("CLAUDE.md", hashlib.sha256(claude.read_bytes()).hexdigest()))
    else:
        for command in contract.get("verification-scope", {}).get("commands", []):
            argv = tuple(_command_argv(command))
            if not argv or not argv[0] or _introduced(argv, excluded):
                continue
            try:
                command_sources = _argv_sources(repo_root, argv)
            except ValueError:
                # This entry is not B-reconstructible.  Other ordered,
                # qualifying entries remain useful; only an empty resulting
                # vector is an EvidenceGap.
                continue
            commands.append(argv)
            sources.extend(command_sources)
    if not commands:
        raise ValueError("EvidenceGap: no base-owned preservation command")
    return PreservationVector(tuple(commands), tuple(sources))


def declared_whole_suite_command(repo_root: Path) -> list[str] | None:
    """The shell-split tokens of the subject's own declared whole-suite
    command, or `None` when its root `CLAUDE.md` is absent or states no such
    command in the narrow labeled shape this resolver recognizes."""
    claude_md = repo_root / "CLAUDE.md"
    if not claude_md.is_file():
        return None
    try:
        text = claude_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for line in text.splitlines():
        lowered = line.lower()
        if not any(keyword in lowered for keyword in _WHOLE_SUITE_KEYWORDS):
            continue
        match = _LABELED_COMMAND.search(line)
        if match is None:
            continue
        command_text = match.group(1)
        if "test" not in command_text.lower():
            continue
        try:
            tokens = shlex.split(command_text)
        except ValueError:
            continue
        if tokens:
            return tokens
    return None
