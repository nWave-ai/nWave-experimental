"""Guard against a third copy of the H2-section-BOUNDARY predicate (D31b,
mikado 2026-07-29). Two `##`-heading-boundary scanners -- one in
`scripts/cli/check_reuse_first_design.py`, one in
`scripts/cli/check_design_dimension_coverage.py` -- independently compiled
the exact same regex pattern (`^##\\s`) to answer "does a Markdown section end
here", verified byte-for-byte agreeing on all 292 real
`docs/feature/**/feature-delta.md` files in the tree, before being collapsed
into `des.cli.validate_feature_delta.next_h2_boundary`. Nothing mechanical
stopped a third copy from reappearing tomorrow; this test is that mechanism.

PROPERTY, not designation. The guard flags a module for compiling a regex
whose PATTERN STRING is exactly `^##\\s` -- independent of what the compiled
object is named. A copy named `_SECTION_END_RE` or anything else is caught the
same as one named `_H2_HEADING_START_RE` (see `test_the_guard_can_fail`, which
plants a differently-named third copy and watches it go red).

Deliberately NARROW to that one literal pattern -- the guard does NOT flag the
many OTHER `^##...` regexes in the tree (heading-RECOGNITION grammars such as
`is_reuse_analysis_heading`'s exact-form regex, the DESIGN-Dimensions lenient
CONTAINS regex, `_WAVE_HEADING_RE`, `_H2_RE`, etc.) -- those answer "which
section does this heading name", a DIFFERENT question D31b explicitly left
untouched (D31a's open, unratified recognition-grammar divergence). Widening
this guard to any `^##`-prefixed pattern would conflate the two questions the
D31a/D31b nodes were careful to keep apart.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SCAN_DIRS = (REPO_ROOT / "scripts" / "cli", REPO_ROOT / "src" / "des" / "cli")
CANONICAL_MODULE = REPO_ROOT / "src" / "des" / "cli" / "validate_feature_delta.py"

#: The exact boundary-predicate pattern string (property key, not a name).
_BOUNDARY_PATTERN = r"^##\s"


def _is_boundary_pattern_compile(node: ast.Call) -> bool:
    """True iff `node` is `re.compile(<the boundary literal>, ...)`. Pure.

    Keys on the PATTERN STRING of the first positional argument, not on the
    name the result is assigned to, and not on flags (a bare `re.compile(...)`
    and a `..., re.MULTILINE)` variant are the SAME property -- both original
    copies compiled the identical pattern, one with the flag and one without).
    """
    if not (isinstance(node.func, ast.Attribute) and node.func.attr == "compile"):
        return False
    if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "re"):
        return False
    if not node.args:
        return False
    first = node.args[0]
    return isinstance(first, ast.Constant) and first.value == _BOUNDARY_PATTERN


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _reimplementations_in(cli_dir: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(cli_dir.glob("*.py")):
        if path == CANONICAL_MODULE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_boundary_pattern_compile(node):
                offenders.append(f"{_display_path(path)}:{node.lineno}")
    return offenders


def test_no_cli_module_reimplements_the_h2_boundary_predicate():
    offenders = [o for scan_dir in SCAN_DIRS for o in _reimplementations_in(scan_dir)]
    assert offenders == [], (
        "the following module(s) compile the exact H2-section-boundary "
        r"pattern `^##\s` already shared as "
        "des.cli.validate_feature_delta.next_h2_boundary -- import it "
        f"instead of reimplementing it: {offenders}"
    )


def test_the_guard_spares_heading_recognition_regexes():
    """Documents (and locks in) that the guard does not over-fire on the
    heading-RECOGNITION regexes deliberately left independent (D31a's open,
    unratified divergence) -- a regression here would mean the guard started
    keying on "any `##`-shaped pattern" instead of the exact boundary literal.
    """
    offenders = set()
    for scan_dir in SCAN_DIRS:
        offenders.update(_reimplementations_in(scan_dir))
    assert not any(o.endswith("check_design_dimension_coverage.py") for o in offenders)
    assert not any("validate_feature_delta.py" in o for o in offenders)


def test_the_guard_can_fail(tmp_path: Path):
    """Prove the guard fails for the right reason: plant a third copy under a
    NAME the guard has never seen (`_SECTION_END_RE`, not `_H2_HEADING_START_RE`
    or `next_section_re`) in an isolated directory, and watch it go red --
    then remove it and confirm the same directory goes green again."""
    shadow_dir = tmp_path / "cli"
    shadow_dir.mkdir()
    planted = shadow_dir / "some_new_gate.py"
    planted.write_text(
        "import re\n\n\n"
        r'_SECTION_END_RE = re.compile(r"^##\s", re.MULTILINE)'
        "\n",
        encoding="utf-8",
    )

    red_offenders = _reimplementations_in(shadow_dir)
    assert red_offenders, (
        "planting a differently-named third copy did not trip the guard -- "
        "it is keying on the variable name, not the pattern string"
    )

    planted.unlink()
    green_offenders = _reimplementations_in(shadow_dir)
    assert green_offenders == [], (
        "removing the planted copy should clear the guard, and it did not"
    )


def test_the_guard_spares_its_own_canonical_definition():
    """The real des.cli.validate_feature_delta.py contains the exact banned
    pattern as ITS OWN canonical definition -- confirm the by-construction
    exclusion actually fires on the real scan, not merely by inspection of
    the source."""
    offenders = []
    for scan_dir in SCAN_DIRS:
        offenders.extend(_reimplementations_in(scan_dir))
    assert not any("validate_feature_delta.py" in o for o in offenders), (
        "the guard flagged its own canonical reference module"
    )
