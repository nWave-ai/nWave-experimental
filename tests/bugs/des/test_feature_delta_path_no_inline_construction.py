"""Regression: the feature-delta path is CONSTRUCTED inline at ~30 call sites,
and the existing single-authority guard cannot see any of them.

``tests/bugs/des/test_feature_delta_path_single_authority.py`` guards ONE
property: that no file outside ``src/des/domain/repo_path_resolver.py``
*defines* a function named ``feature_delta_path`` / ``_feature_delta_path`` /
``_delta_path``. It walks ``ast.FunctionDef`` only. It is GREEN today and it
says nothing about a call site that defines nothing, imports nothing, and
simply writes ``root / "docs" / "feature" / fid / "feature-delta.md"`` inline.
A whole-tree AST scan finds ~30 such constructions. That is the hole this
test closes. Both guards stay: one guards the DEFINITION property, this one
guards the CONSTRUCTION property.

WHAT THIS TEST DECIDES ON (GDP-8: the PROPERTY, never the DESIGNATION)
---------------------------------------------------------------------
Not "does this line look like a path" (a text grep over the filename would
match 224 nodes, 107 of them docstrings). The decision is made on the
*syntactic role* of each string expression that mentions the filename:

* **CONSTRUCTION** -- the expression sits in a position that BUILDS a path:
  the right operand of a ``/`` join, or an argument to ``Path()`` /
  ``open()`` / ``os.path.join()`` / ``.joinpath()`` / ``.glob()`` /
  ``.rglob()``. The ``/`` right operand is RESOLVED, not merely matched: a
  bare ``Name`` bound in-module to the filename literal, or the authority's
  own ``FEATURE_DELTA_FILENAME`` imported and re-joined by hand, both count
  -- otherwise a one-line local alias launders the violation past the guard.
* **RE-DECLARATION** -- a whitespace-free string that terminates in the
  filename appearing anywhere else (a local ``_FEATURE_DELTA_NAME = ...``
  constant, a ``"*/feature-delta.md"`` glob pattern, a ``"/feature-delta.md"``
  suffix matcher, a journal dict key). These are not path joins, but each is
  an uncoordinated second copy of the authority's literal, and the alias
  variety is exactly what makes the CONSTRUCTION check blind.
* **MENTION** -- the string merely NAMES the path to a human. Mechanically:
  it contains whitespace (prose), or it is a docstring. Argparse help and
  description text, error/refusal message f-strings, and ``print()`` strings
  all fall here by that one rule -- no position whitelist, no keyword-name
  matching. ~64 non-docstring mentions exist in the tree and the guard must
  be GREEN with every one of them present; flagging them would be the same
  designation-not-property mistake pointed the other way.

Comments are invisible to this guard BY CONSTRUCTION -- ``ast`` discards
them, so no filtering for them exists or is needed. Stated here rather than
implemented.

THIRD ARITY VALUE (GDP-8 arity corollary)
-----------------------------------------
A file the scanner could not PARSE is neither pass nor fail: it is
``could-not-verify``, and it reaches the aggregate through its own test
below instead of collapsing into a silent ``continue``. (The existing
single-authority guard does silently ``continue`` on ``SyntaxError``; this
one does not.)

Driving surface: structural/architecture test. The SUT is the repository
tree itself under ``src/``, ``scripts/`` and ``nwave_ai/``, scanned with the
stdlib ``ast`` module -- no subprocess boundary is needed for a structural
fact, and no external tool is required (target-machine agnosticism).

RED-for-right-reason: this test needs no new symbol. It fails TODAY with a
real ``AssertionError`` naming ~30 concrete ``file:line`` sites in current
production code -- not an import error, not a collection error.
"""

from __future__ import annotations

import ast
from pathlib import Path

from des.domain import repo_path_resolver


_REPO_ROOT = Path(repo_path_resolver.__file__).resolve().parents[3]

#: The canonical file -- the ONLY file permitted to spell the convention.
_CANONICAL_FILE = Path("src/des/domain/repo_path_resolver.py")

#: Production trees in scope. ``nwave_ai/`` is included: it is a separate
#: distribution, but ``scripts/release/patch_pyproject.py`` force-includes
#: ``des`` into every wheel, so the authority is importable there too.
_SCAN_DIRS = ("src", "scripts", "nwave_ai")

#: The filename whose path convention has exactly one home.
_FILENAME = "feature-delta.md"

#: The authority's exported filename constant. A site that imports it and
#: re-joins it by hand has still hand-built the convention.
_AUTHORITY_CONSTANT = "FEATURE_DELTA_FILENAME"

#: Call targets whose arguments are paths (or path patterns).
_PATH_CALL_NAMES = frozenset({"Path", "open"})
_PATH_CALL_ATTRS = frozenset({"glob", "rglob", "joinpath", "join"})

_AUTHORITY_IMPORT = "des.domain.repo_path_resolver"

_HOW = (
    "HOW: import the authority instead of spelling the convention -- "
    f"`from {_AUTHORITY_IMPORT} import feature_delta_path` when the site has "
    "a feature_id (`feature_delta_path(root, feature_id)`), "
    "`... import feature_delta_in_dir` when it only has an already-resolved "
    "feature directory (`feature_delta_in_dir(feature_dir)`), "
    "`... import feature_dir_path` for the bare `docs/feature/<id>` "
    f"directory, or `... import {_AUTHORITY_CONSTANT}` for a glob pattern / "
    "filename comparison."
)


def _joined_text(node: ast.AST) -> str | None:
    """The literal text of a whole string expression.

    A plain ``Constant`` yields its value; a ``JoinedStr`` (f-string) yields
    its literal parts with each interpolation rendered as ``{}``, so the
    f-string is judged as ONE expression rather than as its fragments.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    return None


def _terminates_in_filename(text: str) -> bool:
    """True when the whole string is a path-shaped token ending in the
    feature-delta filename -- i.e. it carries no whitespace (prose always
    does) and its last segment is the filename."""
    return (
        bool(text) and not any(c.isspace() for c in text) and text.endswith(_FILENAME)
    )


def _mentions_filename(text: str) -> bool:
    return _FILENAME in text


class _ModuleFacts:
    """Per-module bindings needed to RESOLVE a ``/`` join's right operand."""

    def __init__(self, tree: ast.Module) -> None:
        self.filename_alias_names: set[str] = set()
        self.authority_constant_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == _AUTHORITY_CONSTANT:
                        self.authority_constant_names.add(alias.asname or alias.name)
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = list(node.targets), node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            text = _joined_text(value) if value is not None else None
            if text is None or not _terminates_in_filename(text):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    self.filename_alias_names.add(target.id)

    def right_operand_is_the_filename(self, node: ast.expr) -> bool:
        """Does this ``/`` right operand resolve to the feature-delta filename?"""
        text = _joined_text(node)
        if text is not None:
            return _terminates_in_filename(text)
        if isinstance(node, ast.Name):
            return (
                node.id in self.filename_alias_names
                or node.id in self.authority_constant_names
            )
        if isinstance(node, ast.Attribute):
            return node.attr == _AUTHORITY_CONSTANT
        return False


def _is_path_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in _PATH_CALL_NAMES
    if isinstance(func, ast.Attribute):
        return func.attr in _PATH_CALL_ATTRS
    return False


def _docstring_node_ids(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            ids.add(id(body[0].value))
    return ids


def _scan_module(
    rel_path: Path, tree: ast.Module
) -> tuple[list[str], list[str], list[str]]:
    """Classify every filename-mentioning string expression in one module.

    Returns ``(constructions, redeclarations, unclassifiable)`` as
    ``file:line`` strings.
    """
    facts = _ModuleFacts(tree)
    docstrings = _docstring_node_ids(tree)
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    constructions: set[tuple[int, str]] = set()
    redeclarations: set[tuple[int, str]] = set()
    unclassifiable: set[tuple[int, str]] = set()

    # (1) Path-BUILDING positions.
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if facts.right_operand_is_the_filename(node.right):
                constructions.add((node.lineno, "'/' join terminating in the filename"))
        elif isinstance(node, ast.Call) and _is_path_call(node):
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                text = _joined_text(arg)
                if text is not None and _mentions_filename(text):
                    constructions.add(
                        (arg.lineno, "filename literal handed to a path call")
                    )
    construction_lines = {line for line, _ in constructions}

    # (2) Every other whole string expression mentioning the filename.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Constant, ast.JoinedStr)):
            continue
        if isinstance(parents.get(id(node)), ast.JoinedStr):
            continue  # a fragment; the enclosing f-string is the expression
        if id(node) in docstrings:
            continue  # MENTION: documentation
        text = _joined_text(node)
        if text is None or not _mentions_filename(text):
            continue
        if node.lineno in construction_lines:
            continue  # already reported as a construction
        if any(c.isspace() for c in text):
            continue  # MENTION: prose naming the path to a human
        if _terminates_in_filename(text):
            redeclarations.add((node.lineno, f"second copy of the literal {text!r}"))
            continue
        unclassifiable.add((node.lineno, f"whitespace-free string {text!r}"))

    def fmt(items: set[tuple[int, str]]) -> list[str]:
        return [f"{rel_path}:{line} ({why})" for line, why in sorted(items)]

    return fmt(constructions), fmt(redeclarations), fmt(unclassifiable)


def _scan_tree(root: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    """Whole-tree scan. Returns constructions, redeclarations, unclassifiable
    sites and unparseable files (the ``could-not-verify`` third value)."""
    constructions: list[str] = []
    redeclarations: list[str] = []
    unclassifiable: list[str] = []
    unparseable: list[str] = []
    for scan_dir in _SCAN_DIRS:
        base = root / scan_dir
        if not base.is_dir():
            continue
        for py_file in sorted(base.rglob("*.py")):
            rel_path = py_file.relative_to(root)
            if rel_path == _CANONICAL_FILE:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError) as exc:
                unparseable.append(f"{rel_path} ({type(exc).__name__}: {exc})")
                continue
            built, declared, unknown = _scan_module(rel_path, tree)
            constructions.extend(built)
            redeclarations.extend(declared)
            unclassifiable.extend(unknown)
    return constructions, redeclarations, unclassifiable, unparseable


def test_no_expression_outside_the_authority_constructs_the_feature_delta_path() -> (
    None
):
    """No expression under ``src/``, ``scripts/`` or ``nwave_ai/`` -- other
    than the canonical resolver itself -- may BUILD a path terminating in the
    feature-delta filename.

    Fails for real today: ~30 inline constructions exist, including one
    laundered through a local filename alias that a literal-only check would
    miss entirely.
    """
    constructions, _, _, _ = _scan_tree(_REPO_ROOT)

    assert constructions == [], (
        f"WHAT: {len(constructions)} expression(s) outside {_CANONICAL_FILE} "
        "construct the feature-delta path inline.\n"
        "WHY: the path convention "
        "`<root>/docs/feature/<feature_id>/feature-delta.md` has exactly ONE "
        f"home -- {_CANONICAL_FILE}. Every inline join is a copy that the "
        "authority cannot see and a convention change cannot reach.\n"
        f"{_HOW}\n"
        "Offending sites:\n  " + "\n  ".join(constructions)
    )


def test_no_second_copy_of_the_feature_delta_filename_literal_exists() -> None:
    """No module outside the authority may re-declare the filename literal --
    as a local constant, a glob pattern, a suffix matcher, or a dict key.

    This is the alias hole: a one-line ``_FEATURE_DELTA_NAME =
    "feature-delta.md"`` turns every later ``dir / _FEATURE_DELTA_NAME`` into
    a join a literal-matching guard cannot see.
    """
    _, redeclarations, _, _ = _scan_tree(_REPO_ROOT)

    assert redeclarations == [], (
        f"WHAT: {len(redeclarations)} second cop(ies) of the "
        f"{_FILENAME!r} literal exist outside {_CANONICAL_FILE}.\n"
        "WHY: a local copy of the literal is an uncoordinated duplicate of "
        "the authority's exported constant, and an aliased copy makes the "
        "inline-construction guard blind by construction.\n"
        f"{_HOW}\n"
        "Offending sites:\n  " + "\n  ".join(redeclarations)
    )


def test_every_filename_mention_is_mechanically_classifiable() -> None:
    """Third arity value, reaching the aggregate: any string that mentions the
    filename but is neither a construction, nor a second copy of the literal,
    nor prose, is reported as ``could-not-classify`` -- never silently passed.
    """
    _, _, unclassifiable, _ = _scan_tree(_REPO_ROOT)

    assert unclassifiable == [], (
        f"WHAT: {len(unclassifiable)} string(s) mentioning {_FILENAME!r} "
        "could not be classified as construction, re-declaration, or prose.\n"
        "WHY: this guard refuses to pass a site it could not decide on -- a "
        "silent pass over an undecided site is exactly the false-green this "
        "test exists to prevent.\n"
        "HOW: inspect each site; if it is a real construction, migrate it to "
        f"{_AUTHORITY_IMPORT}; if it is prose, the classifier needs a "
        "correction (do NOT widen it to pass the site).\n"
        "Undecided sites:\n  " + "\n  ".join(unclassifiable)
    )


def test_every_scanned_production_file_was_parseable() -> None:
    """Third arity value, second axis: a file the scanner could not parse was
    never inspected, so the two guards above say nothing about it. That
    ``could-not-verify`` reaches the aggregate here instead of collapsing
    into a silent skip.
    """
    _, _, _, unparseable = _scan_tree(_REPO_ROOT)

    assert unparseable == [], (
        f"WHAT: {len(unparseable)} production file(s) could not be parsed, so "
        "the feature-delta-path construction guard could not inspect them.\n"
        "WHY: an unparseable file is neither pass nor fail -- skipping it "
        "silently would report a green over an unexamined region of the "
        "tree.\n"
        "HOW: fix the syntax/encoding error in the named file(s), then re-run "
        "this test.\n"
        "Unparseable files:\n  " + "\n  ".join(unparseable)
    )
