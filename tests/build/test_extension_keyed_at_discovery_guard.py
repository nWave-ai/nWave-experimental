"""Guard against a NEW extension-keyed AT-discovery site (agnostic-at-discovery-
ssot-repair, lane/at-discovery-archtest).

A prior repair (`ed2bb451c`, `aa5bacca0`, `8bb90d55d`) closed three of six known
gaps where a gate resolved "which files back this feature/slice's acceptance
tests" by scanning for the literal `.feature` extension ONLY -- silently blind
to a slice delivered exclusively via a head-comment-tagged pytest (or other
native-regression) AT. The shared authority for that fact is
`des.application.feature_at_files` (`feature_tag_files` /
`feature_tagged_test_files` / `discover_at_kind_for_slice`) and its composed
backstop `des.application.slice_at_completeness.feature_files_for_slice` --
BOTH already union the Gherkin and pytest taxonomies. Nothing mechanical stops
an EIGHTH site from reappearing tomorrow, extension-keyed the same way the six
were; this test is that mechanism.

PROPERTY, not designation (`test_no_duplicate_emit_json_helper.py` precedent):
the guard flags a CALL SHAPE -- `<expr>.rglob("*.feature")` / `<expr>.glob(
"*.feature")` / `<expr>.endswith(".feature")` / `<expr>.suffix == ".feature"`
-- never a function/module NAME. A helper renamed to anything is caught the
same way.

ALLOWLIST MECHANISM (deliberately NOT a path-keyed list): a site-local marker
comment, `# gherkin-scope: <reason>`, on the same source line as the flagged
node (or up to `_MARKER_LOOKBACK` lines above it, to cover a `for ... in
sorted(x.rglob(...)):` whose marker sits on the loop's own line, or a
multi-line call). A path-keyed allowlist rots silently -- a renamed file drops
out of the list unnoticed, or a site whose purpose quietly changed keeps a
stale exemption forever. A site-local marker travels WITH the code: it moves
when the code moves, and it is the thing under review in the same diff that
introduces or changes the site. This repo's own architecture-test/design-doc
culture already leans on comments-carry-the-decision (see e.g.
`feature_at_files.py`'s own extensive inline rationale); this guard extends
that idiom to a machine-checked marker instead of inventing a second registry.

The TWO shared-authority modules (`feature_at_files.py`,
`slice_at_completeness.py`) are excluded from the scan by construction -- they
DEFINE the fact, they cannot duplicate it (same reasoning
`test_no_duplicate_emit_json_helper.py` applies to its own canonical module).
Every marked site below was individually verified (lane/at-discovery-archtest,
2026-07-29), not inherited from a prior census -- see the marker's own
`# gherkin-scope:` reason for what was checked.
"""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Production-code roots in scope. `tests/` (this file's own tree) is
# deliberately excluded -- test fixtures legitimately plant `.feature` globs
# as part of exercising the very discovery machinery this guard protects.
SCAN_ROOTS = ("src", "scripts", "nwave_ai")

EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
    }
)

# The shared discovery authority: it DEFINES the `.feature`-vs-pytest fact,
# so it cannot duplicate itself. Excluded the same way `_emit_json.py` is
# excluded from `test_no_duplicate_emit_json_helper.py`'s scan.
AUTHORITY_MODULES = frozenset(
    {
        "src/des/application/feature_at_files.py",
        "src/des/application/slice_at_completeness.py",
    }
)

MARKER = "gherkin-scope:"
# Generous enough to cover a short rationale comment immediately preceding
# the flagged statement, not just a single trailing same-line comment --
# tight enough that a marker for one site cannot "leak" onto an unrelated
# flagged line several statements away.
_MARKER_LOOKBACK = 6  # lines above the flagged node's own line, inclusive.


def _iter_production_files() -> list[Path]:
    files: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = PROJECT_ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
                continue
            files.append(path)
    return files


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _feature_glob_literal(node: ast.expr) -> bool:
    """True iff `node` is a string constant shaped like a `.feature` glob
    pattern (`"*.feature"`, `"slice-*.feature"`, ...) -- a glob pattern whose
    non-wildcard tail is exactly the `.feature` extension."""
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    return node.value.rstrip("*").endswith(".feature") and node.value != ""


def _feature_suffix_literal(node: ast.expr) -> bool:
    """True iff `node` is the exact string constant `".feature"` (the
    `endswith`/`suffix ==` shape, as opposed to the glob-pattern shape)."""
    return isinstance(node, ast.Constant) and node.value == ".feature"


def _flagged_lines(tree: ast.Module) -> list[int]:
    """Every line number where an extension-keyed `.feature` discovery/
    classification call or comparison appears -- the PROPERTY this guard
    checks, independent of the surrounding function/variable names."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in ("rglob", "glob") and node.args:
                if _feature_glob_literal(node.args[0]):
                    lines.append(node.lineno)
            elif attr == "endswith" and node.args:
                if _feature_suffix_literal(node.args[0]):
                    lines.append(node.lineno)
        elif isinstance(node, ast.Compare) and len(node.ops) == 1:
            if isinstance(node.ops[0], (ast.Eq,)):
                left, right = node.left, node.comparators[0]
                for a, b in ((left, right), (right, left)):
                    if (
                        isinstance(a, ast.Attribute)
                        and a.attr == "suffix"
                        and _feature_suffix_literal(b)
                    ):
                        lines.append(node.lineno)
    return sorted(set(lines))


def _has_marker(source_lines: list[str], lineno: int) -> bool:
    """True iff a `# gherkin-scope:` marker appears on `lineno`'s own line or
    up to `_MARKER_LOOKBACK` lines above it (1-indexed, inclusive)."""
    start = max(1, lineno - _MARKER_LOOKBACK)
    for line_no in range(start, lineno + 1):
        if MARKER in source_lines[line_no - 1]:
            return True
    return False


def _unmarked_sites_in(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    source_lines = text.splitlines()
    offenders = []
    for lineno in _flagged_lines(tree):
        if not _has_marker(source_lines, lineno):
            offenders.append(f"{_display_path(path)}:{lineno}")
    return offenders


def _unmarked_sites(files: list[Path]) -> list[str]:
    offenders: list[str] = []
    for path in files:
        if _display_path(path) in AUTHORITY_MODULES:
            continue
        offenders.extend(_unmarked_sites_in(path))
    return offenders


def test_no_new_unmarked_extension_keyed_at_discovery_site():
    offenders = _unmarked_sites(_iter_production_files())
    assert offenders == [], (
        "the following site(s) resolve 'which file(s) back this AT' by keying "
        "on the literal .feature extension, with no # gherkin-scope: marker "
        "explaining why the shared discovery authority "
        "(des.application.feature_at_files.discover_at_kind_for_slice / "
        "feature_tag_files / feature_tagged_test_files, or the "
        "slice_at_completeness.feature_files_for_slice backstop -- both "
        "already union the Gherkin and pytest/native-regression taxonomies) "
        "does not apply here: this is the exact class agnostic-at-discovery-"
        "ssot-repair closed three of six instances of. FIX by calling the "
        "shared authority (or composing feature_tagged_test_files + "
        "resolve_test_file_attribution + is_pytest_collectible the way "
        "run_contract_gate._node_belongs_to_slice / "
        "carpaccio_precheck._check_binding / "
        "verify_deliver_entry_contract._authored_slice_tags already do). If "
        "the site is genuinely Gherkin-only by subject matter (a Gherkin<->"
        "atdd_pure migration tool, a Gherkin tag-syntax convention checker, a "
        "frozen historical scorecard, ...), add a `# gherkin-scope: <reason>` "
        f"comment on the flagged line explaining why: {offenders}"
    )


def test_the_guard_spares_the_shared_discovery_authority_modules():
    """The authority modules genuinely contain the banned shapes (they ARE
    the `.feature`-file walk) -- confirm the by-construction exclusion fires
    on the real scan, not merely by inspection of the source."""
    for rel in AUTHORITY_MODULES:
        path = PROJECT_ROOT / rel
        assert path.is_file(), f"authority module moved or renamed: {rel}"
        # Sanity: the authority module really does carry the flagged shape,
        # so a future refactor that removes it should prompt re-examining
        # whether this exclusion is still needed -- not silently stay inert.
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert _flagged_lines(tree), (
            f"{rel} no longer carries an extension-keyed .feature shape -- "
            "the AUTHORITY_MODULES exclusion may now be unnecessary"
        )
    offenders = _unmarked_sites(_iter_production_files())
    assert not any(o.split(":")[0] in AUTHORITY_MODULES for o in offenders), (
        "the guard flagged its own shared-authority module(s)"
    )


def test_the_guard_can_fail(tmp_path: Path):
    """Prove the guard fails for the right reason: plant an eighth,
    differently-shaped, differently-named extension-keyed site in an isolated
    directory and watch it go red -- then remove it and confirm green."""
    shadow_root = tmp_path / "src" / "des" / "cli"
    shadow_root.mkdir(parents=True)
    planted = shadow_root / "some_new_gate.py"
    planted.write_text(
        "from pathlib import Path\n\n\n"
        "def _resolve_evidence(target_dir: Path) -> list[Path]:\n"
        "    return sorted(target_dir.rglob('*.feature'))\n",
        encoding="utf-8",
    )

    red_offenders = _unmarked_sites([planted])
    assert any(o.endswith("some_new_gate.py:5") for o in red_offenders), (
        "planting a differently-named, differently-shaped eighth site did "
        "not trip the guard -- it is keying on something other than the "
        "call shape"
    )

    marked_text = planted.read_text(encoding="utf-8").replace(
        "rglob('*.feature'))",
        "rglob('*.feature'))  # gherkin-scope: plant-and-remove proof",
    )
    planted.write_text(marked_text, encoding="utf-8")
    marked_offenders = _unmarked_sites([planted])
    assert marked_offenders == [], (
        "adding the # gherkin-scope: marker did not clear the guard"
    )

    planted.unlink()
    green_offenders = _unmarked_sites(sorted(shadow_root.rglob("*.py")))
    assert green_offenders == [], (
        "removing the planted copy should clear the guard, and it did not"
    )
