"""Regression: the telemetry-ledger path convention is CONSTRUCTED inline at
24 call sites (18 under ``src/des``, 6 under ``scripts/``), even though
``src/des/domain/telemetry_paths.py`` was written as its single authority.
Six resolvers used to answer "where does a ledger live" independently before
that authority existed; migrating the CALLERS is a separate crafter dispatch.
This test closes the DISTILL half: a mechanical guard that fails for real
today, naming every concrete site, so the migration has a fixed target and a
standing regression fence once it lands.

WHAT THIS TEST DECIDES ON (GDP-8: the PROPERTY, never the DESIGNATION)
------------------------------------------------------------------------
Not "does this line contain the word telemetry" (matches comments, prose,
unrelated substrings such as ``atdd-pure-events.jsonl``). The decision is
made on the *syntactic role* of every expression that could spell the
convention, resolved on FOUR independent axes -- because the defect this
guard exists to catch is not "the wrong path is produced", it is "the RIGHT
path is produced through the WRONG route": a caller that carries its own copy
of the mapping and reproduces the authority's output faithfully. A bare
value-equality assertion cannot see that shape at all.

* **CONSTRUCTION** (axis 1) -- an expression that BUILDS a path by spelling
  BOTH root-parts literals ``".nwave"`` and ``"telemetry"`` adjacently: as
  consecutive operands of a `/`-chain, as consecutive arguments to a
  path-building call (``Path()``/``open()``/``os.path.join()``/
  ``.joinpath()``/``.join()``/``.glob()``/``.rglob()``), or merged into ONE
  string literal (``".nwave/telemetry/atdd-pure"``). Resolution follows
  in-module aliases (a bare ``Name`` bound to one of the two literals) and
  ``Path(".nwave")`` heads of a chain, and expands a ``*tuple`` splat
  argument through its declared tuple value -- otherwise a one-line local
  alias, or a splat through a private root-parts tuple, launders the
  violation past the check exactly as the D73 precedent warned.
* **RE-DECLARATION, root-parts tuple** (axis 2) -- a second copy of the
  exact 2-tuple ``(".nwave", "telemetry")`` assigned anywhere outside the
  authority, independent of whether it is ever actually joined. This is the
  axis that catches ``_MY_ROOT = (".nwave", "telemetry")`` even when it is
  later splatted through ``repo.joinpath(*_MY_ROOT)`` rather than spelled as
  a literal `/`-chain -- CONSTRUCTION alone is blind to a call whose base is
  itself opaque plus a splat of an ALREADY-classified tuple, so this axis
  closes that gap independently.
* **FAMILY-SEGMENT-BY-HAND** (axis 3) -- one of the five ``LedgerFamily``
  values (``"atdd-pure"``, ``"examine"``, ``"review"``, ``"context"``,
  ``"mikado"``) spelled DIRECTLY as a path SEGMENT -- a `/`-chain
  right-operand, or a positional argument to a path-building call --
  regardless of what the rest of the chain resolves to. This is the axis
  that catches ``telemetry_root(repo) / "atdd-pure"``: CONSTRUCTION is blind
  to it (the chain's base is a ``Call``, never a literal, so no adjacent
  root-parts pair exists for axis 1 to see), yet the family half of the
  convention is still hand-spelled instead of routed through
  ``LedgerFamily``. This is arguably the MOST LIKELY post-migration bypass:
  it is the shape a developer reaches for when they have HALF-adopted the
  authority -- ``telemetry_root`` is imported (so it looks compliant, and an
  import-based check would pass it too) and the family is still hand-typed.
  Measured: 21 real occurrences today, all under the ``atdd-pure`` family,
  all genuinely path-segment positions carrying the root convention (the 21
  of the 24 axis-1 sites that use the ``atdd-pure`` family; the other 3 use
  ``red-green``/``feature-end``, deliberately not ``LedgerFamily`` members
  and so invisible to this axis) -- zero noise measured against 12 unrelated
  family-value occurrences elsewhere in the tree (log field names, wave/
  phase enum labels), because those never sit in a `/`-operand or call-arg
  position. Unconditional, not scoped to an authority import: the
  half-adopted shape looks syntactically identical whether or not
  ``telemetry_root`` happens to be imported in that module.
* **RE-DECLARATION, ledger-family value** (axis 4) -- one of the five
  ``LedgerFamily`` values re-declared as a dict VALUE or a bare-Name alias,
  scoped to a module that ALSO imports something from
  ``des.domain.telemetry_paths`` (the authority). This is the axis that
  catches a private family-name mapping (``_FAMILIES = {"atdd_pure":
  "atdd-pure"}``) whose VALUES are later reached through a subscript rather
  than spelled directly as a path segment (``telemetry_root(repo) /
  _FAMILIES[family]``) -- neither axis 1 nor axis 3 can see that shape,
  because neither the call base nor a dict-subscript expression resolves to
  a literal at the `/`-join site itself. Scoped to the authority import
  (unlike axis 3) because, unscoped, this axis over-fires on an unrelated
  dict carrying a coincidentally-matching value as an ordinary log field
  (e.g. ``{"kind": "context"}``) -- pinned green by a dedicated negative-
  control test below. Measured: zero real occurrences of any of the five
  values as a dict value or a bare alias anywhere in ``src/``, ``scripts/``
  or ``nwave_ai/`` today -- this axis exists to catch a shape that does not
  yet exist in the tree, proven by the synthetic-fixture tests below rather
  than a real-tree count.

Comments are invisible to this guard BY CONSTRUCTION -- ``ast`` discards
them, so no filtering for them exists or is needed.

HONEST GAP (stated, not hidden -- GDP-8 decide-on-the-property discipline):
what genuinely remains after axes 1-4 is a family segment that is NEITHER a
watched literal NOR a watched re-declaration -- e.g. a family value computed
at runtime (read from an environment variable, derived from a CLI argument,
or built from string concatenation the guard cannot fold to a constant), or
a brand-new dirname that matches none of the five current ``LedgerFamily``
members and shares no literal token with anything this guard watches for.
That is inherent to any static-literal check, not specific to this
implementation: a guard that decides on literal tokens cannot see a value it
never observes as a literal.

THIRD ARITY VALUE (GDP-8 arity corollary)
------------------------------------------
A path-shaped (internal ``"/"``), whitespace-free, non-docstring string that
carries BOTH root-parts segments -- ``".nwave"`` and ``"telemetry"``, exact
per-segment equality -- yet was classified by none of the axes above (a
genuine near-miss: both segments present but not adjacent) is
``could-not-classify``, reported by its own test below rather than silently
dropped. Deliberately narrower than a bare substring-of-``"telemetry"`` scan:
the real tree carries several unrelated whitespace-free literals that merely
contain the word (a regex alternation, a CLI flag name, an unrelated
pilot-metrics directory with no leading dot, an enum diagnostic label) --
none are copies of this convention, and a bare-substring rule would
misreport all of them as undecided. A file the
scanner could not PARSE is ``could-not-verify``, reported by a second,
independent test -- mirroring the D73 precedent's own third/fourth arity
tests exactly.

Driving surface: structural/architecture test. The SUT is the repository
tree itself under ``src/``, ``scripts/`` and ``nwave_ai/``, scanned with the
stdlib ``ast`` module -- no subprocess boundary is needed for a structural
fact, and no external tool is required (target-machine agnosticism).

RED-for-right-reason: this test needs no new symbol. It fails TODAY with two
real ``AssertionError``s -- axis 1 naming 24 concrete ``file:line`` sites,
axis 3 naming 21 -- in current production code, not an import error, not a
collection error.
"""

from __future__ import annotations

import ast
import itertools
from pathlib import Path

import pytest

from des.domain import telemetry_paths


_REPO_ROOT = Path(telemetry_paths.__file__).resolve().parents[3]

#: The canonical file -- the ONLY file permitted to spell the convention.
_CANONICAL_FILE = Path("src/des/domain/telemetry_paths.py")

#: Production trees in scope, mirroring the D73 precedent's own scope
#: (``nwave_ai/`` included: ``scripts/release/patch_pyproject.py`` force-
#: includes ``des`` into every wheel, so the authority is importable there).
_SCAN_DIRS = ("src", "scripts", "nwave_ai")

#: The telemetry root's two segments, hardcoded independently of the
#: authority's own ``TELEMETRY_ROOT_PARTS`` (GDP-8 witness corollary: a
#: guard that reads its target's own definition of the convention could not
#: notice the target drifting from it).
_ROOT_PARTS: tuple[str, str] = (".nwave", "telemetry")

#: The ``LedgerFamily`` values, hardcoded for the same reason.
_FAMILY_VALUES = frozenset({"atdd-pure", "examine", "review", "context", "mikado"})

#: The dotted module path a caller must import FROM to count as "coupled to
#: the authority" for axis 4's scoping (see the module docstring's axis-4
#: entry for why this scoping exists).
_AUTHORITY_IMPORT = "des.domain.telemetry_paths"

_HOW = (
    "HOW: import the authority instead of spelling the convention -- "
    f"`from {_AUTHORITY_IMPORT} import telemetry_root` for the root alone, "
    "`... import ledger_path` when a full per-partition ledger file is "
    "needed (`ledger_path(repo, LedgerFamily.ATDD_PURE, partition_key)`), "
    "or `... import LedgerFamily` for the family enum instead of a private "
    "string or mapping."
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


def _imports_authority(tree: ast.Module) -> bool:
    """Does this module import ANYTHING from the authority module -- the
    scoping signal axis 4 needs (see its module-docstring entry)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == _AUTHORITY_IMPORT:
            return True
        if isinstance(node, ast.Import):
            if any(alias.name == _AUTHORITY_IMPORT for alias in node.names):
                return True
    return False


class _ModuleFacts:
    """Per-module bindings needed to RESOLVE a `/`-chain's operands and a
    `*tuple` splat argument -- the alias-laundering surfaces axis 1 must
    see through."""

    def __init__(self, tree: ast.Module) -> None:
        self.literal_alias: dict[str, str] = {}
        self.tuple_alias: dict[str, tuple[str, ...]] = {}
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = list(node.targets), node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            if not names:
                continue
            text = _joined_text(value)
            if text is not None and (text in _ROOT_PARTS or text in _FAMILY_VALUES):
                for name in names:
                    self.literal_alias[name] = text
                continue
            if isinstance(value, ast.Tuple) and value.elts:
                elt_texts = [_joined_text(elt) for elt in value.elts]
                if all(t is not None for t in elt_texts):
                    tup = tuple(t for t in elt_texts if t is not None)
                    for name in names:
                        self.tuple_alias[name] = tup

    def resolve_operand(self, node: ast.expr) -> str | None:
        text = _joined_text(node)
        if text is not None:
            return text
        if isinstance(node, ast.Name):
            return self.literal_alias.get(node.id)
        return None

    def resolve_base(self, node: ast.expr) -> str | None:
        """The leftmost operand of a `/`-chain. A ``Path(<literal>)`` call
        head resolves to that literal's own segment, so ``Path(".nwave") /
        "telemetry"`` flattens identically to ``".nwave" / "telemetry"``."""
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Path"
            and node.args
        ):
            return self.resolve_operand(node.args[0])
        return self.resolve_operand(node)


def _flatten_chain(node: ast.expr, facts: _ModuleFacts) -> list[str | None] | None:
    """Flatten a `/`-join chain (nested ``BinOp(Div)``) into an ordered list
    of per-segment tokens, left to right. ``None`` marks an opaque
    (unresolvable) segment -- e.g. a bare variable holding a repo root.
    Returns ``None`` when ``node`` is not itself a `/`-join (the recursion
    base case for a non-chain expression)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left_segments = _flatten_chain(node.left, facts)
        if left_segments is None:
            left_segments = [facts.resolve_base(node.left)]
        return left_segments + [facts.resolve_operand(node.right)]
    return None


def _has_root_pair(segments: list[str | None]) -> bool:
    """Do two ADJACENT segments equal the root-parts pair, in order? Exact
    per-segment equality, never substring matching -- so a chain like
    ``".nwave" / "audit" / "atdd-pure-events.jsonl"`` (a real, deliberately
    NON-telemetry site) stays green: ``"audit"`` never equals ``"telemetry"``."""
    return any(
        a == _ROOT_PARTS[0] and b == _ROOT_PARTS[1]
        for a, b in itertools.pairwise(segments)
    )


_JOIN_CALL_NAMES = frozenset({"Path", "open"})
_JOIN_CALL_ATTRS = frozenset({"joinpath", "join", "glob", "rglob"})


def _is_join_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in _JOIN_CALL_NAMES
    if isinstance(func, ast.Attribute):
        return func.attr in _JOIN_CALL_ATTRS
    return False


def _call_arg_segments(node: ast.Call, facts: _ModuleFacts) -> list[str | None]:
    """Resolve a path-building call's positional arguments into segments,
    expanding a ``*tuple`` splat through its declared tuple alias -- the
    shape a plain per-argument resolver would silently pass through."""
    segments: list[str | None] = []
    for arg in node.args:
        if isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name):
            tup = facts.tuple_alias.get(arg.value.id)
            if tup is not None:
                segments.extend(tup)
            else:
                segments.append(None)
            continue
        segments.append(facts.resolve_operand(arg))
    return segments


def _scan_module(
    rel_path: Path, tree: ast.Module
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Classify every telemetry-path-convention expression in one module.

    Returns ``(constructions, root_tuple_redeclarations,
    family_segment_by_hand, family_redeclarations, unclassifiable)`` as
    ``file:line`` strings.
    """
    facts = _ModuleFacts(tree)
    docstrings = _docstring_node_ids(tree)
    authority_imported = _imports_authority(tree)
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    constructions: set[tuple[int, str]] = set()
    root_tuple_redecls: set[tuple[int, str]] = set()
    family_segment_by_hand: set[tuple[int, str]] = set()
    family_redecls: set[tuple[int, str]] = set()
    unclassifiable: set[tuple[int, str]] = set()

    # (1) `/`-join chains -- only the OUTERMOST BinOp(Div) of each chain (one
    # whose parent is itself a BinOp(Div) is a sub-chain, already covered
    # when the outer one is flattened).
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        parent = parents.get(id(node))
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div):
            continue
        segments = _flatten_chain(node, facts)
        if segments is not None and _has_root_pair(segments):
            constructions.add(
                (node.lineno, "'/' join chain carrying the telemetry root parts")
            )

    # (2) path-building calls: Path()/open()/os.path.join()/.joinpath()/
    # .join()/.glob()/.rglob(), including a `*tuple` splat argument.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_join_call(node):
            segments = _call_arg_segments(node, facts)
            if _has_root_pair(segments):
                constructions.add(
                    (
                        node.lineno,
                        "path-building call carrying the telemetry root parts",
                    )
                )

    construction_lines = {line for line, _ in constructions}

    # (3) the whole convention merged into ONE string literal -- a shape
    # (1)/(2) cannot see because each classifies exactly one ast node, and a
    # merged literal is a single node with no internal `/`-join structure.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Constant, ast.JoinedStr)):
            continue
        if isinstance(parents.get(id(node)), ast.JoinedStr):
            continue  # a fragment; the enclosing f-string is the expression
        if id(node) in docstrings:
            continue
        text = _joined_text(node)
        if text is None or any(c.isspace() for c in text):
            continue
        if node.lineno in construction_lines:
            continue
        if "/" in text and _has_root_pair(text.split("/")):
            constructions.add(
                (
                    node.lineno,
                    f"single literal {text!r} carrying the telemetry root parts",
                )
            )
            construction_lines.add(node.lineno)

    # (4) FAMILY-SEGMENT-BY-HAND: a `LedgerFamily` value spelled directly as
    # a path segment -- a `/`-chain right-operand, or a positional argument
    # to a path-building call -- regardless of what the rest of the chain
    # resolves to. Catches `telemetry_root(repo) / "atdd-pure"`: axis 1 is
    # blind to it (the base is a Call, never a literal, so no adjacent
    # root-parts pair exists), yet the family half is still hand-spelled.
    # Unconditional -- see the module docstring's axis-3 entry for why this
    # one is NOT scoped to an authority import while axis 4 (below) is.
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            text = facts.resolve_operand(node.right)
            if text in _FAMILY_VALUES:
                family_segment_by_hand.add(
                    (
                        node.right.lineno,
                        f"ledger-family value {text!r} spelled by hand as a "
                        "'/' join right-operand",
                    )
                )
        elif isinstance(node, ast.Call) and _is_join_call(node):
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    continue
                text = facts.resolve_operand(arg)
                if text in _FAMILY_VALUES:
                    family_segment_by_hand.add(
                        (
                            arg.lineno,
                            f"ledger-family value {text!r} spelled by hand "
                            "as a path-building call argument",
                        )
                    )

    # (5) the root-parts tuple re-declared anywhere, independent of use.
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not isinstance(value, ast.Tuple) or len(value.elts) != 2:
            continue
        elt_texts = tuple(_joined_text(e) for e in value.elts)
        if elt_texts != _ROOT_PARTS:
            continue
        if not any(isinstance(t, ast.Name) for t in targets):
            continue
        root_tuple_redecls.add(
            (node.lineno, "second copy of the telemetry root-parts tuple")
        )

    # (6) a ledger-family VALUE re-declared as a dict value or a bare alias,
    # scoped to a module that ALSO imports the authority (see the module
    # docstring's axis-4 entry: unscoped, this over-fires on an unrelated
    # dict carrying a coincidentally-matching value as an ordinary log
    # field, e.g. `{"kind": "context"}`).
    if authority_imported:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for value_node in node.values:
                text = _joined_text(value_node)
                if text in _FAMILY_VALUES:
                    family_redecls.add(
                        (
                            value_node.lineno,
                            f"ledger-family value {text!r} re-declared as a dict value",
                        )
                    )
        for node in ast.walk(tree):
            targets = []
            value = None
            if isinstance(node, ast.Assign):
                targets, value = list(node.targets), node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            text = _joined_text(value)
            if text in _FAMILY_VALUES and any(isinstance(t, ast.Name) for t in targets):
                family_redecls.add(
                    (
                        node.lineno,
                        f"ledger-family value {text!r} re-declared as a bare alias",
                    )
                )

    # (7) third arity: a path-SHAPED literal (internal "/", so it is at least
    # attempting to spell a filesystem path) that carries BOTH root-parts
    # segments -- ".nwave" and "telemetry" -- as EXACT split-segments
    # somewhere in the string, in either order, yet was not already
    # classified above (adjacent occurrences are already CONSTRUCTION).
    # Deliberately NOT a bare substring-of-"telemetry" scan: the real tree
    # carries several unrelated whitespace-free literals that merely contain
    # the word -- a regex alternation (`\.nwave/|telemetry|ledger`), a CLI
    # flag name (`--telemetry-dir`), an unrelated pilot-metrics directory
    # (`nWave/telemetry/...`, no leading dot -- a different convention
    # entirely), an enum diagnostic label (`spine-telemetry-absent`) -- none
    # of these are path-shaped copies of THIS convention, and a bare-
    # substring rule would misreport all four as undecided. Requiring BOTH
    # exact segments, path-shaped, is the narrowest rule that still surfaces
    # a genuine near-miss (e.g. the two root segments present but separated
    # by an extra path component) without false-flagging an unrelated site.
    classified_lines = (
        construction_lines
        | {line for line, _ in root_tuple_redecls}
        | {line for line, _ in family_segment_by_hand}
        | {line for line, _ in family_redecls}
    )
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Constant, ast.JoinedStr)):
            continue
        if isinstance(parents.get(id(node)), ast.JoinedStr):
            continue
        if id(node) in docstrings:
            continue
        text = _joined_text(node)
        if text is None or any(c.isspace() for c in text):
            continue
        if "/" not in text:
            continue
        segments = text.split("/")
        if not (_ROOT_PARTS[0] in segments and _ROOT_PARTS[1] in segments):
            continue
        if node.lineno in classified_lines:
            continue
        unclassifiable.add(
            (
                node.lineno,
                f"path-shaped string {text!r} carries both root-parts "
                "segments but not adjacently",
            )
        )

    def fmt(items: set[tuple[int, str]]) -> list[str]:
        return [f"{rel_path}:{line} ({why})" for line, why in sorted(items)]

    return (
        fmt(constructions),
        fmt(root_tuple_redecls),
        fmt(family_segment_by_hand),
        fmt(family_redecls),
        fmt(unclassifiable),
    )


def _scan_tree(
    root: Path,
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[str]]:
    """Whole-tree scan. Returns constructions, root-tuple redeclarations,
    family-segment-by-hand sites, family redeclarations, unclassifiable
    sites, and unparseable files (the ``could-not-verify`` third value)."""
    constructions: list[str] = []
    root_tuple_redecls: list[str] = []
    family_segment_by_hand: list[str] = []
    family_redecls: list[str] = []
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
            built, root_tuples, by_hand, families, unknown = _scan_module(
                rel_path, tree
            )
            constructions.extend(built)
            root_tuple_redecls.extend(root_tuples)
            family_segment_by_hand.extend(by_hand)
            family_redecls.extend(families)
            unclassifiable.extend(unknown)
    return (
        constructions,
        root_tuple_redecls,
        family_segment_by_hand,
        family_redecls,
        unclassifiable,
        unparseable,
    )


def _scan_source(
    source: str,
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Scan a source STRING directly (no filesystem) -- the synthetic-
    fixture entry point the faithful-reimplementation-shape tests use."""
    tree = ast.parse(source, filename="<synthetic>.py")
    return _scan_module(Path("<synthetic>.py"), tree)


# --- real-tree tests -------------------------------------------------------


def test_no_expression_outside_the_authority_constructs_a_telemetry_path() -> None:
    """No expression under ``src/``, ``scripts/`` or ``nwave_ai/`` -- other
    than the canonical authority itself -- may BUILD a path carrying the
    telemetry root parts ``.nwave`` / ``telemetry``.

    Fails for real today: 24 constructions exist across 18 files (12 under
    ``src/des``, 6 under ``scripts/``).
    """
    constructions, _, _, _, _, _ = _scan_tree(_REPO_ROOT)

    assert constructions == [], (
        f"WHAT: {len(constructions)} expression(s) outside {_CANONICAL_FILE} "
        "construct a telemetry-ledger path inline.\n"
        "WHY: the telemetry root convention "
        f"`<repo>/{_ROOT_PARTS[0]}/{_ROOT_PARTS[1]}/<family>/<key>.jsonl` has "
        f"exactly ONE home -- {_CANONICAL_FILE}. Every inline join is a copy "
        "the authority cannot see and a convention change cannot reach.\n"
        f"{_HOW}\n"
        "Offending sites:\n  " + "\n  ".join(constructions)
    )


def test_no_second_copy_of_the_telemetry_root_parts_tuple_exists() -> None:
    """No module outside the authority may re-declare the exact 2-tuple
    ``(".nwave", "telemetry")`` -- independent of whether it is ever joined.

    This is the alias-splat hole: ``_MY_ROOT = (".nwave", "telemetry")``
    followed by ``repo.joinpath(*_MY_ROOT)`` produces a `/`-join whose two
    operands (an opaque call base, an opaque starred name) neither operand
    resolves to a literal from the CONSTRUCTION check's point of view unless
    it also expands the splat -- this test guards the tuple's existence
    directly, as an independent axis.
    """
    _, root_tuple_redecls, _, _, _, _ = _scan_tree(_REPO_ROOT)

    assert root_tuple_redecls == [], (
        f"WHAT: {len(root_tuple_redecls)} second cop(ies) of the telemetry "
        f"root-parts tuple {_ROOT_PARTS!r} exist outside {_CANONICAL_FILE}.\n"
        "WHY: a local copy of the root-parts tuple is an uncoordinated "
        "duplicate of the authority's exported `TELEMETRY_ROOT_PARTS`, and "
        "it can reproduce the correct path through a route the CONSTRUCTION "
        "check alone may not see (e.g. splatted into `.joinpath(*_ROOT)`).\n"
        f"{_HOW}\n"
        "Offending sites:\n  " + "\n  ".join(root_tuple_redecls)
    )


def test_no_ledger_family_value_is_spelled_by_hand_as_a_path_segment() -> None:
    """No `/`-chain right-operand, and no path-building call argument, may
    spell one of the five ``LedgerFamily`` values directly.

    Fails for real today: 21 sites exist -- exactly the subset of the 24
    axis-1 constructions that use the ``atdd-pure`` family (the other 3 use
    ``red-green``/``feature-end``, deliberately not ``LedgerFamily``
    members, so invisible to this axis by design).

    This axis stays RED even after a naive migration that replaces the
    hand-built root (`.nwave`/`telemetry`) with `telemetry_root(repo)` but
    leaves the family segment hand-typed -- exactly the half-adopted shape
    most likely to survive the migration, because it already looks
    compliant (the authority IS imported) at a glance.
    """
    _, _, family_segment_by_hand, _, _, _ = _scan_tree(_REPO_ROOT)

    assert family_segment_by_hand == [], (
        f"WHAT: {len(family_segment_by_hand)} ledger-family value(s) are "
        "spelled by hand as a path segment.\n"
        "WHY: even when the root half of the path is fetched correctly "
        "through `telemetry_root(repo)`, a hand-spelled family segment "
        "still bypasses `LedgerFamily` -- the correct value produced "
        "through the wrong route, and a shape that looks compliant at a "
        "glance because the authority IS imported.\n"
        f"{_HOW}\n"
        "Offending sites:\n  " + "\n  ".join(family_segment_by_hand)
    )


def test_no_ledger_family_value_is_redeclared_outside_the_authority() -> None:
    """No module that imports the authority may ALSO re-declare one of the
    five ``LedgerFamily`` values as a dict value or a bare-Name alias.

    Measured: zero occurrences today -- this test is a standing regression
    fence, not a currently-failing count. The synthetic-fixture tests below
    prove the axis actually fires when the shape is present.
    """
    _, _, _, family_redecls, _, _ = _scan_tree(_REPO_ROOT)

    assert family_redecls == [], (
        f"WHAT: {len(family_redecls)} ledger-family value(s) are re-declared "
        f"outside {_CANONICAL_FILE}.\n"
        'WHY: a private family-name mapping (e.g. `{"atdd_pure": '
        '"atdd-pure"}`) bypasses `LedgerFamily` even when the root half of '
        "the path is fetched correctly through `telemetry_root(repo)` -- a "
        "shape neither the CONSTRUCTION axis nor the family-segment-by-hand "
        "axis can see, because the family value is reached through a dict "
        "subscript rather than spelled directly at the `/`-join site.\n"
        f"{_HOW}\n"
        "Offending sites:\n  " + "\n  ".join(family_redecls)
    )


def test_every_telemetry_mention_is_mechanically_classifiable() -> None:
    """Third arity value, reaching the aggregate: any path-shaped,
    whitespace-free, non-docstring string carrying BOTH root-parts segments
    (a near-miss, present but not adjacent) that is classified by none of
    the axes above is reported as ``could-not-classify`` -- never silently
    passed.
    """
    _, _, _, _, unclassifiable, _ = _scan_tree(_REPO_ROOT)

    assert unclassifiable == [], (
        f"WHAT: {len(unclassifiable)} string(s) mentioning 'telemetry' could "
        "not be classified as construction, re-declaration, or prose.\n"
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
    never inspected, so the axes above say nothing about it. That
    ``could-not-verify`` reaches the aggregate here instead of collapsing
    into a silent skip.
    """
    _, _, _, _, _, unparseable = _scan_tree(_REPO_ROOT)

    assert unparseable == [], (
        f"WHAT: {len(unparseable)} production file(s) could not be parsed, "
        "so the telemetry-path construction guard could not inspect them.\n"
        "WHY: an unparseable file is neither pass nor fail -- skipping it "
        "silently would report a green over an unexamined region of the "
        "tree.\n"
        "HOW: fix the syntax/encoding error in the named file(s), then "
        "re-run this test.\n"
        "Unparseable files:\n  " + "\n  ".join(unparseable)
    )


# --- synthetic-fixture tests: the four faithful-reimplementation shapes ---
#
# Each proves (or honestly disproves) that the guard catches ONE of the four
# shapes named in the dispatch brief: a caller that reproduces the correct
# path through a route the authority cannot see. None of these shapes exist
# in the real tree today (measured), so they are exercised directly against
# synthetic source text rather than real files.


def test_guard_catches_shape_1_root_tuple_reimplemented_via_splat_join() -> None:
    """Shape 1: a private ``_MY_ROOT`` tuple joined via
    ``repo.joinpath(*_MY_ROOT)``. Caught on BOTH axes: the splat is expanded
    through the tuple alias (CONSTRUCTION), and the tuple itself is a second
    copy (RE-DECLARATION) independent of how it is later used.
    """
    source = (
        "from pathlib import Path\n"
        '_MY_ROOT = (".nwave", "telemetry")\n'
        "def ledger_dir(repo: Path) -> Path:\n"
        '    return repo.joinpath(*_MY_ROOT, "atdd-pure")\n'
    )
    constructions, root_tuple_redecls, family_segment_by_hand, _, _ = _scan_source(
        source
    )

    assert constructions, "splat-expanded root-parts join must be a CONSTRUCTION"
    assert root_tuple_redecls, "the private root-parts tuple must be a RE-DECLARATION"
    assert family_segment_by_hand, (
        "the trailing 'atdd-pure' argument is ALSO a hand-spelled family "
        "segment (a positional path-building-call argument) -- both axes "
        "fire independently on this fixture"
    )


def test_guard_catches_shape_2_family_mapping_dict_via_redeclaration_only() -> None:
    """Shape 2: a private family-name mapping dict, with the ROOT fetched
    correctly through ``telemetry_root(repo)``. CAUGHT on the
    RE-DECLARATION axis only -- honestly NOT on CONSTRUCTION, and honestly
    NOT on family-segment-by-hand either, because neither the call base
    (``telemetry_root(repo)``, a Call) nor the family segment
    (``_FAMILIES[family]``, a Subscript) resolves to a literal anywhere. This
    is the concrete case the module docstring's axis-4 entry describes: the
    correct path, produced through the wrong route, visible ONLY as a
    second copy of the literal sitting inside the dict.
    """
    source = (
        "from des.domain.telemetry_paths import telemetry_root\n"
        '_FAMILIES = {"atdd_pure": "atdd-pure"}\n'
        "def ledger_dir(repo, family):\n"
        "    return telemetry_root(repo) / _FAMILIES[family]\n"
    )
    constructions, _, family_segment_by_hand, family_redecls, _ = _scan_source(source)

    assert family_redecls, "the family-mapping dict value must be a RE-DECLARATION"
    assert constructions == [], (
        "documents the honest gap: CONSTRUCTION cannot see this shape "
        "(neither chain operand is a literal) -- RE-DECLARATION is the only "
        "axis that catches it, which is why family_redecls must be non-empty"
    )
    assert family_segment_by_hand == [], (
        "documents the honest gap on a SECOND axis: the family value is "
        "reached through a dict subscript (`_FAMILIES[family]`), never "
        "spelled directly at the `/`-join site, so family-segment-by-hand "
        "cannot see it either -- RE-DECLARATION is the ONLY axis that fires"
    )


def test_guard_catches_shape_2b_family_segment_by_hand_onto_authority_root() -> None:
    """Shape 2b (the hole a peer review measured): the ROOT fetched
    correctly through ``telemetry_root(repo)``, but the family segment
    spelled DIRECTLY as a `/`-chain right-operand instead of going through
    ``LedgerFamily`` -- ``telemetry_root(repo) / "atdd-pure"``. This is the
    shape a developer reaches for while HALF-adopting the authority: it
    looks compliant (the authority IS imported) yet still hand-spells the
    family. CAUGHT on family-segment-by-hand only -- honestly NOT on
    CONSTRUCTION, because the chain's base is a ``Call``, never a literal,
    so no adjacent root-parts pair exists for axis 1 to see.
    """
    source = (
        "from des.domain.telemetry_paths import telemetry_root\n"
        "def ledger_dir(repo):\n"
        '    return telemetry_root(repo) / "atdd-pure"\n'
    )
    constructions, _, family_segment_by_hand, family_redecls, _ = _scan_source(source)

    assert family_segment_by_hand, (
        "a family value spelled directly as a '/' right-operand onto the "
        "authority's own root call must be family-segment-by-hand"
    )
    assert constructions == [], (
        "documents the honest gap: CONSTRUCTION cannot see this shape "
        "(the chain's base is a Call, never a literal, so no adjacent "
        "root-parts pair exists) -- family-segment-by-hand is the axis "
        "that closes it"
    )
    assert family_redecls == [], (
        "no dict and no bare-Name alias exists in this fixture -- the "
        "RE-DECLARATION axis has nothing to see here, by design"
    )


def test_guard_catches_shape_3_whole_convention_copied_as_one_literal() -> None:
    """Shape 3: the whole convention copied as ONE merged string literal
    rather than a `/`-join of separate literals."""
    source = '_TELEMETRY_DIR = ".nwave/telemetry/atdd-pure"\n'
    constructions, _, _, _, _ = _scan_source(source)

    assert constructions, "a merged single-literal copy must be a CONSTRUCTION"


def test_guard_catches_shape_4_private_helper_reimplementing_ledger_path() -> None:
    """Shape 4: a private helper re-implementing ``ledger_path`` with the
    literals spelled inline -- the exact shape measured 24 times in the real
    tree; this fixture proves the CONSTRUCTION axis fires on it directly."""
    source = (
        "from pathlib import Path\n"
        "def _my_ledger_path(repo: Path, family: str, key: str) -> Path:\n"
        '    return repo / ".nwave" / "telemetry" / family / f"{key}.jsonl"\n'
    )
    constructions, _, _, _, _ = _scan_source(source)

    assert constructions, (
        "a hand-built ledger_path re-implementation must be a CONSTRUCTION"
    )


@pytest.mark.negative_at
def test_guard_stays_green_on_the_non_telemetry_audit_log_path() -> None:
    """Negative control: the real, deliberately non-telemetry
    ``.nwave/audit/atdd-pure-events.jsonl`` path (verify_deliver_integrity.py
    line 420) must NOT be flagged on any axis -- ``"audit"`` is adjacent to
    ``".nwave"``, never ``"telemetry"``, and per-segment equality (not
    substring matching) means the shared ``"atdd-pure"`` text inside
    ``"atdd-pure-events.jsonl"`` never matches the exact family-value
    equality check either.
    """
    source = (
        "from pathlib import Path\n"
        '_COMMON_AUDIT_LOG_REL = Path(".nwave") / "audit" / "atdd-pure-events.jsonl"\n'
    )
    (
        constructions,
        root_tuple_redecls,
        family_segment_by_hand,
        family_redecls,
        unclassifiable,
    ) = _scan_source(source)

    assert constructions == []
    assert root_tuple_redecls == []
    assert family_segment_by_hand == []
    assert family_redecls == []
    assert unclassifiable == []


@pytest.mark.negative_at
def test_guard_stays_green_on_a_family_word_used_as_a_non_path_value() -> None:
    """Negative control: a ``LedgerFamily`` value spelled as an ordinary,
    non-path VALUE -- a log-event dict field (``{"kind": "context"}``) or a
    bare wave/phase-name constant (``WAVE = "feature-end"``) -- must NOT be
    flagged on any axis. Neither sits in a `/`-chain operand or
    path-building-call-argument position (so family-segment-by-hand does not
    fire), and the dict-value / bare-alias RE-DECLARATION axis is scoped to
    modules that import the authority -- this fixture imports nothing from
    it, so that axis does not fire either. Pins the axis-4 scoping decision
    stated in the module docstring: unscoped, this exact dict would have
    been a false positive.
    """
    source = 'record = {"kind": "context"}\nWAVE = "feature-end"\n'
    (
        constructions,
        root_tuple_redecls,
        family_segment_by_hand,
        family_redecls,
        unclassifiable,
    ) = _scan_source(source)

    assert constructions == []
    assert root_tuple_redecls == []
    assert family_segment_by_hand == []
    assert family_redecls == []
    assert unclassifiable == []
