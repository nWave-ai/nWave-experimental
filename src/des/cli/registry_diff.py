"""Diff `des`'s subcommand registry between an old installed tree and a new
one about to replace it (F-INSTALL-REMOVAL-TRANSPARENCY).

RCA (docs/product/backlog.md:1327): no point of the installer ever diffed
``_REGISTRY``'s name set between an old install and a new one -- the
filesystem-sweep mechanisms (``sweep_retired_assets``) delete named FILES
one-per-line and do not apply here, because ``_REGISTRY`` rows are Python
source inside ONE file that travels whole via ``shutil.copytree``.

Everything here is a pure, side-effect-free reader over source text. It
never imports or executes the file it reads: the old tree may belong to a
different, unknown-compatible Python/des version, so importing it would be
both a portability and a safety violation (ADR-PLAT-001, pure-Python-only
extends to "never exec a foreign version's code to describe it").
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def _parse_or_none(path: Path) -> ast.Module | None:
    """Read and AST-parse *path*, ``None`` on any I/O or syntax failure.

    Shared by every reader in this module -- never imports or executes the
    file, so a foreign-version tree or a mid-edit syntax error degrades to
    "no fact", never a crash or a fabricated one.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def registry_names_from_source(path: Path) -> frozenset[str] | None:
    """Extract every ``_SubcommandRow(...)`` first-argument name via a
    static AST parse of *path*.

    Returns ``None`` (fail-open: no diff rather than a fabricated one) when
    the file is missing, unreadable, or does not parse as Python.
    """
    tree = _parse_or_none(path)
    if tree is None:
        return None

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else None
        if func_name != "_SubcommandRow":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            names.add(first_arg.value)

    return frozenset(names)


def _identity_dict_comp_names(node: ast.DictComp) -> frozenset[str] | None:
    """String constants of ``{name: Expr(...) for name in (S1, S2, ...)}``.

    The one comprehension shape this module's own ``_RETIRED`` currently
    uses to share one retirement reason across many names: a single
    generator, no ``if`` filters, whose key expression is exactly its own
    loop variable. Any other shape (multiple generators, filters, a
    computed key) is unsupported and returns ``None`` -- fail-open, never
    guessed at.
    """
    if len(node.generators) != 1:
        return None
    generator = node.generators[0]
    if generator.ifs:
        return None
    if not (isinstance(node.key, ast.Name) and isinstance(generator.target, ast.Name)):
        return None
    if node.key.id != generator.target.id:
        return None
    iterable = generator.iter
    if not isinstance(iterable, (ast.Tuple, ast.List, ast.Set)):
        return None
    names: set[str] = set()
    for element in iterable.elts:
        if not (isinstance(element, ast.Constant) and isinstance(element.value, str)):
            return None
        names.add(element.value)
    return frozenset(names)


def retired_names_declared(path: Path) -> frozenset[str] | None:
    """The string keys of the module-level ``_RETIRED`` mapping in *path*,
    via a static AST parse -- never imports the module.

    Supports two literal right-hand-side shapes for ``_RETIRED = ...``: a
    plain dict literal (keys read directly), or the identity dict
    comprehension ``_identity_dict_comp_names`` recognises. Returns
    ``None`` when the file is unreadable/unparseable, or declares no
    top-level ``_RETIRED`` assignment in either supported shape --
    fail-open, so an unsupported shape blocks the caller from trusting an
    empty set rather than silently reporting "nothing is retired".
    """
    tree = _parse_or_none(path)
    if tree is None:
        return None

    for node in ast.walk(tree):
        target_names: tuple[ast.expr, ...]
        if isinstance(node, ast.Assign):
            target_names = tuple(node.targets)
        elif isinstance(node, ast.AnnAssign):
            # `_RETIRED: dict[str, RetiredSubcommand] = {...}` -- the
            # annotated form this module actually uses.
            target_names = (node.target,)
        else:
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "_RETIRED"
            for target in target_names
        ):
            continue
        value = node.value
        if value is None:  # annotation-only, e.g. `_RETIRED: dict[str, X]`
            return None
        if isinstance(value, ast.Dict):
            return frozenset(
                key.value
                for key in value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
        if isinstance(value, ast.DictComp):
            return _identity_dict_comp_names(value)
        return None

    return None


@dataclass(frozen=True)
class RegistryDiff:
    """Name-set delta between an old and a new `_REGISTRY`."""

    old_count: int
    new_count: int
    removed: frozenset[str]
    added: frozenset[str]


def diff_registry_names(old_path: Path, new_path: Path) -> RegistryDiff | None:
    """Diff the subcommand name sets of two `__main__.py`-shaped files.

    ``None`` when either side fails to parse (see
    ``registry_names_from_source``) -- an unreadable side means no diff can
    be trusted, not that the diff is empty.
    """
    old_names = registry_names_from_source(old_path)
    new_names = registry_names_from_source(new_path)
    if old_names is None or new_names is None:
        return None

    return RegistryDiff(
        old_count=len(old_names),
        new_count=len(new_names),
        removed=frozenset(old_names - new_names),
        added=frozenset(new_names - old_names),
    )


def format_removal_summary(diff: RegistryDiff) -> str | None:
    """The user-facing summary line, or ``None`` when nothing changed.

    Format is fixed by the bug report itself:
    ``des subcommands: 79 -> 19 (65 removed, 5 added)``.
    """
    if not diff.removed and not diff.added:
        return None
    return (
        f"des subcommands: {diff.old_count} -> {diff.new_count} "
        f"({len(diff.removed)} removed, {len(diff.added)} added)"
    )


class _RetiredEntryLike(Protocol):
    replacement: str | None


class _SupportsInfo(Protocol):
    def info(self, message: str) -> None: ...


def log_retired_subcommand_removals(
    logger: _SupportsInfo,
    diff: RegistryDiff,
    retired: Mapping[str, _RetiredEntryLike],
) -> None:
    """One log line per removed subcommand name, in the same style already
    used for retired scripts/templates (``_sweep_retired_scripts``).

    Appends ``-> replaced by <name>`` only when *retired* names a known
    replacement for that exact removed name; never invents one, never adds
    a second line, and never logs added names (only removals are
    noteworthy on the removal-transparency axis).
    """
    for name in sorted(diff.removed):
        line = f"  \U0001f9f9 Removed retired des subcommand: {name}"
        entry = retired.get(name)
        if entry is not None and entry.replacement is not None:
            line += f" -> replaced by {entry.replacement}"
        logger.info(line)
