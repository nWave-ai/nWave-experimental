"""Regression: the `scripts/hooks/` source-directory resolution was defined
independently in THREE places (SSOT violation), not one -- and two of the
three copies used a FLAT-only probe that can never match a PyPI/pipx wheel
install, so `orchestrator_affordance_refresh.py` (and every other
`DES_HOOKS` script) was silently never copied to `~/.claude/scripts/` on a
wheel install. The installed Claude Code SessionStart command's discovery
one-liner (`hook_definitions._STANDALONE_ORCHESTRATOR_AFFORDANCE_DISCOVERY`)
then found nothing at `~/.claude/scripts/orchestrator_affordance_refresh.py`
and printed `[orchestrator-affordance-refresh] script not found` to stderr
with empty stdout -- the cross-host SessionStart acceptance contract
(`tests/des/acceptance/sessionstart_cross_host_contract/`) caught this on
the real installed artifact.

Three near-identical `... / "scripts" / "hooks"` path-join expressions
existed:

* `scripts/install/plugins/des_plugin.py`
  `_resolve_hook_scripts_source_dir` -- CANONICAL (single authority after
  this fix). Existence-probes the NESTED wheel layout
  (`framework_source/nWave/hooks/`) first, then the FLAT dist-tarball layout
  (`framework_source/scripts/hooks/`), then the dev checkout.
* `DESPlugin._get_hook_scripts_source_dir` -- duplicate, FLAT-only probe.
  Used by `validate_prerequisites`'s presence check.
* `DESPlugin._install_des_hook_scripts` -- duplicate, FLAT-only probe. Used
  to copy `DES_HOOKS` scripts into `<claude_dir>/scripts/` for the Claude
  Code host.
* `DESPlugin._install_nwave_runtime_assets` -- duplicate, but its OWN
  `using_prebuilt`-gated variant of the nested-first probe (already
  correct for the host-neutral/Codex install path, just re-derived instead
  of shared).

The fix (crafter's job, NOT this test's): the three duplicates now delegate
to the one canonical `_resolve_hook_scripts_source_dir` function.

Driving surface: whole-tree AST scan for the `... / "scripts" / "hooks"`
path-join SHAPE (a `BinOp` chain, not a named function -- the duplicates
were inline expressions, not repeated function definitions), mirroring
`tests/bugs/des/test_feature_delta_path_single_authority.py`'s "scan for a
re-derived fact, assert singular occurrence in the canonical location"
precedent, adapted from a function-name scan to an expression-shape scan
(GDP-8: decide on the PROPERTY -- the path-join expression itself -- never
a text-pattern designation for it).
"""

from __future__ import annotations

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The canonical file/function -- the ONLY place permitted to build a
#: `... / "scripts" / "hooks"` path-join expression.
_CANONICAL_FILE = Path("scripts/install/plugins/des_plugin.py")
_CANONICAL_FUNCTION = "_resolve_hook_scripts_source_dir"

#: Scoped to the installer plugins, not all of `scripts/` -- unrelated tools
#: (e.g. `scripts/flow_v2_closure_scorecard.py`'s wiring-registry file list)
#: legitimately glob `scripts/hooks/*.py` for a completely different purpose
#: (enumerating shipped hook files, not resolving an install-time source
#: directory) and are not part of this SSOT.
_SEARCH_ROOT = "scripts/install/plugins"


def _is_scripts_hooks_join(node: ast.AST) -> bool:
    """True when `node` is a `BinOp` matching `... / "scripts" / "hooks"`.

    Matches `X / "scripts" / "hooks"` for any left-hand expression `X`
    (`Path(...)`, `context.framework_source`, a bare `Path` call, ...) --
    the SHAPE that repeated across the three duplicate definitions.
    """
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
        return False
    if not (isinstance(node.right, ast.Constant) and node.right.value == "hooks"):
        return False
    inner = node.left
    return (
        isinstance(inner, ast.BinOp)
        and isinstance(inner.op, ast.Div)
        and isinstance(inner.right, ast.Constant)
        and inner.right.value == "scripts"
    )


def _enclosing_function_name(tree: ast.AST, target: ast.AST) -> str | None:
    """Name of the innermost `def` enclosing `target`, or `None` at module level."""
    best: str | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    best = node.name
    return best


def _scripts_hooks_join_definitions(
    root: Path,
) -> dict[Path, list[tuple[int, str | None]]]:
    """Every `.py` file under `root/scripts/` building a `.../"scripts"/"hooks"`
    path-join expression, mapped to `(lineno, enclosing_function_name)` pairs.
    """
    found: dict[Path, list[tuple[int, str | None]]] = {}
    search_root = root / _SEARCH_ROOT
    if not search_root.is_dir():
        return found
    for py_file in sorted(search_root.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        hits: list[tuple[int, str | None]] = []
        for node in ast.walk(tree):
            if _is_scripts_hooks_join(node):
                hits.append((node.lineno, _enclosing_function_name(tree, node)))
        if hits:
            found[py_file.relative_to(root)] = hits
    return found


def test_scripts_hooks_source_dir_has_exactly_one_definition_in_the_tree() -> None:
    """Positive AT: the ONLY function permitted to build a
    `... / "scripts" / "hooks"` path-join is `_resolve_hook_scripts_source_dir`
    in the canonical `des_plugin.py` (which itself legitimately contains TWO
    such expressions -- the nested-wheel probe and the flat-dist probe --
    both inside the one canonical function).
    """
    definitions = _scripts_hooks_join_definitions(_REPO_ROOT)
    canonical_hits = definitions.get(_CANONICAL_FILE, [])
    other_files = {p: hits for p, hits in definitions.items() if p != _CANONICAL_FILE}

    assert (
        canonical_hits
        and all(fn == _CANONICAL_FUNCTION for _, fn in canonical_hits)
        and not other_files
    ), (
        "expected exactly ONE `scripts/hooks` path-join in the tree, inside "
        f"{_CANONICAL_FILE}::{_CANONICAL_FUNCTION} -- found: "
        f"{ {str(p): lines for p, lines in definitions.items()}!r} "
        "(SSOT violation: independent re-derivations of the same install-time "
        "path drift out of sync -- two of them used a FLAT-only probe that "
        "never matches a wheel install). Fix: delete the duplicate "
        "expressions and call "
        "`scripts.install.plugins.des_plugin._resolve_hook_scripts_source_dir` "
        "instead."
    )


def test_offending_duplicate_joins_never_reappear_outside_canonical_function() -> None:
    """Negative AT: no function OTHER than `_resolve_hook_scripts_source_dir`
    may ever re-derive the `scripts/hooks` path-join again -- the specific
    regression this bug fixes (a duplicate re-introduced under a fourth
    call site).
    """
    definitions = _scripts_hooks_join_definitions(_REPO_ROOT)
    offenders = {
        path: [
            (lineno, fn)
            for lineno, fn in hits
            if not (path == _CANONICAL_FILE and fn == _CANONICAL_FUNCTION)
        ]
        for path, hits in definitions.items()
    }
    offenders = {path: hits for path, hits in offenders.items() if hits}

    assert offenders == {}, (
        "expected ZERO `scripts/hooks` path-join expressions outside "
        f"{_CANONICAL_FILE}::{_CANONICAL_FUNCTION} -- found: "
        f"{ {str(p): lines for p, lines in offenders.items()}!r}. "
        "Every install-time consumer must call "
        "`_resolve_hook_scripts_source_dir` instead of re-deriving its own "
        "copy of this path."
    )
