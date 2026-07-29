# @feature-declared-facts-reachable-recorded
# @slice-02
"""D2 (DD-7): one Reuse Analysis heading predicate, not two (unify the split).

declared-facts-reachable-recorded slice-02. Value statement (feature-delta.md
[REF] Slice Plan / Decisions Table DD-7): today two independent
``_REUSE_ANALYSIS_HEADING_RE``-shaped regexes exist for the SAME grammar
concept -- ``src/des/cli/validate_feature_delta.py`` (EXACT, whitespace-
tolerant, bare ``## Reuse Analysis`` only) and
``scripts/cli/check_reuse_first_design.py`` (LENIENT, matches any heading
CONTAINING "Reuse Analysis", including the Wave-form
``## Wave: DESIGN / [REF] Reuse Analysis``). The SAME document is therefore
seen as HAVING a Reuse Analysis section by one gate and MISSING it by the
other -- a verdict divergence proved by execution (mikado 3.2/D2).

Target state (DD-7): ``validate_feature_delta`` exports a new, pure,
exported predicate ``is_reuse_analysis_heading(line: str) -> bool`` wrapping
the EXISTING exact regex; ``check_reuse_first_design`` imports it and DELETES
its own lenient regex. EXACT wins -- the Wave-form is rejected by both call
sites, consistently, instead of accepted by one and rejected by the other.

Contract-shape: pure-function (feature-delta.md [REF] Contract-Tests row
"is_reuse_analysis_heading (D2)").

Driving surface (Mandate 13, Layer 3 composition-root default): every
scenario drives the REAL, STABLE, EXISTING production modules
``des.cli.validate_feature_delta`` and (via its published module path)
``scripts.cli.check_reuse_first_design`` directly -- both are already the
composition root this repo's own precedent tests directly (no CLI subprocess
boundary is needed for a pure-function predicate; see
``tests/des/acceptance/agnostic_at_discovery/test_slice_01_suffix_map_ssot.py``
for the identical in-tree precedent of testing these exact two modules'
public/module-level surface directly).

RED-for-right-reason (P1-P4, ``nw-distill-red-scaffolding``): the module-top
import list contains ONLY the two STABLE, already-existing modules -- never
the not-yet-defined ``is_reuse_analysis_heading`` symbol itself. Each
scenario that needs the new symbol converts the otherwise-raw
``AttributeError``/``ImportError`` into a semantic, message-carrying
``AssertionError`` via an explicit ``hasattr`` guard at RUNTIME inside the
test body, never at collection time. The agreement scenario
(``test_check_reuse_first_design_extraction_diverges_from_exact_heading_
semantics_on_wave_form_heading``) and the never-a-second-definition scenario
need no guard at all: both are genuine, already-failing assertions against
CURRENT production behaviour (verdict divergence / duplicate regex
definition), so they fail for a real business-logic reason today, before the
new symbol exists.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# Ensure the repo-local `scripts/` tree is importable the same way the CLI
# entry point resolves it -- `scripts/cli/check_reuse_first_design.py` is not
# a package under `src/`, so it is imported by locating it on disk relative
# to a STABLE, already-existing module rather than assuming a particular
# sys.path setup. This mirrors this repo's own precedent for driving a
# scripts/cli/ gate module directly (Layer 3 composition-root default).
from des.cli import validate_feature_delta


_REPO_ROOT = Path(validate_feature_delta.__file__).resolve().parents[3]
_SCRIPTS_CLI = _REPO_ROOT / "scripts" / "cli"
if str(_SCRIPTS_CLI) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_CLI))

import check_reuse_first_design


_BARE_CANONICAL_VARIANTS = [
    pytest.param("## Reuse Analysis", id="exact"),
    pytest.param("##  Reuse Analysis", id="double-space-after-hashes"),
    pytest.param("## Reuse  Analysis", id="double-space-mid-heading"),
    pytest.param("##\tReuse Analysis", id="tab-after-hashes"),
    pytest.param("## Reuse Analysis   ", id="trailing-whitespace"),
]

_NON_MATCHING_VARIANTS = [
    pytest.param(
        "## Wave: DESIGN / [REF] Reuse Analysis", id="wave-form-carpaccio-heading"
    ),
    pytest.param("### Reuse Analysis", id="wrong-level-h3"),
    pytest.param("# Reuse Analysis", id="wrong-level-h1"),
    pytest.param("## Reuse Analysis Detail", id="suffix-variant"),
    pytest.param("## Foo Reuse Analysis", id="prefix-variant"),
    pytest.param("## reuse analysis", id="case-mismatch"),
]


def _require_is_reuse_analysis_heading():
    """Runtime guard converting a missing symbol into a semantic AssertionError.

    P1-P4 RED-for-right-reason: the module import above never names the
    not-yet-defined symbol, so collection always succeeds; this guard is
    what turns "impl missing" into a real, message-carrying test failure.
    """
    assert hasattr(validate_feature_delta, "is_reuse_analysis_heading"), (
        "des.cli.validate_feature_delta must export "
        "is_reuse_analysis_heading(line: str) -> bool (DD-7) -- not yet "
        "defined. It must wrap the existing _REUSE_ANALYSIS_HEADING_RE "
        "(exact, whitespace-tolerant, bare '## Reuse Analysis' only)."
    )
    return validate_feature_delta.is_reuse_analysis_heading


@pytest.mark.parametrize("heading_line", _BARE_CANONICAL_VARIANTS)
def test_is_reuse_analysis_heading_accepts_bare_canonical_heading_whitespace_tolerant(
    heading_line: str,
) -> None:
    """Every whitespace-tolerant spelling of the bare canonical heading must
    be accepted (DD-7 winning semantics: EXACT, bare-only)."""
    is_reuse_analysis_heading = _require_is_reuse_analysis_heading()
    assert is_reuse_analysis_heading(heading_line) is True, (
        f"expected is_reuse_analysis_heading({heading_line!r}) is True -- "
        "the bare canonical heading (whitespace-tolerant) must be recognised"
    )


@pytest.mark.parametrize("heading_line", _NON_MATCHING_VARIANTS)
def test_is_reuse_analysis_heading_rejects_wave_form_and_every_other_variant(
    heading_line: str,
) -> None:
    """The Wave-form heading and every other non-bare variant must be
    REJECTED (DD-7: the Wave-form is now consistently rejected everywhere,
    not accepted by one gate and rejected by the other)."""
    is_reuse_analysis_heading = _require_is_reuse_analysis_heading()
    assert is_reuse_analysis_heading(heading_line) is False, (
        f"expected is_reuse_analysis_heading({heading_line!r}) is False -- "
        "only the bare canonical heading may be recognised, per DD-7's "
        "EXACT (bare-only) winning semantics"
    )


_WAVE_FORM_ONLY_DOCUMENT = """\
# Feature Delta

## Wave: DESIGN / [REF] Reuse Analysis

| Existing Component | Justification |
|---|---|
| Foo | reused as-is |
"""


def test_check_reuse_first_design_extraction_diverges_from_exact_heading_semantics_on_wave_form_heading() -> (
    None
):
    """The load-bearing agreement AT (D2): the SAME feature-delta document,
    containing ONLY the Wave-form heading, must produce the SAME
    section-presence verdict at BOTH call sites.

    Uses the CURRENT public surface of both modules -- no new symbol is
    required for this scenario to fail today: `check_reuse_first_design`'s
    lenient regex currently extracts a section for the Wave-form heading
    (treats it as PRESENT) while `validate_feature_delta`'s exact regex does
    not (treats it as ABSENT). That is the D2 defect, proved by execution.
    After DD-7 ships (check_reuse_first_design routes through the unified
    is_reuse_analysis_heading predicate and drops its own lenient regex),
    both sides must agree the Wave-form heading is ABSENT.
    """
    exact_heading_indices = validate_feature_delta._reuse_analysis_heading_indices(
        _WAVE_FORM_ONLY_DOCUMENT
    )
    lenient_extracted_sections = (
        check_reuse_first_design._extract_reuse_analysis_sections(
            _WAVE_FORM_ONLY_DOCUMENT
        )
    )

    exact_sees_present = len(exact_heading_indices) > 0
    lenient_sees_present = len(lenient_extracted_sections) > 0

    assert exact_sees_present == lenient_sees_present, (
        "verdict divergence (D2): validate_feature_delta's exact heading "
        f"predicate sees the Wave-form-only document as "
        f"present={exact_sees_present} while check_reuse_first_design's "
        f"section extraction sees it as present={lenient_sees_present}. "
        "Both call sites must agree on Reuse Analysis section presence for "
        "the SAME document -- check_reuse_first_design must route through "
        "the unified is_reuse_analysis_heading predicate (DD-7) instead of "
        "its own independent lenient CONTAINS regex."
    )


def _module_level_reuse_heading_regex_definitions(root: Path) -> list[Path]:
    """Every .py file under `root` (src/ and scripts/) that defines its own
    module-level `_REUSE_ANALYSIS_HEADING_RE`-named assignment. Pure, AST-based
    (GDP-8: decide on the property -- a name binding for this grammar concept
    -- never a text-pattern designation for it)."""
    found: list[Path] = []
    for search_root in (root / "src", root / "scripts"):
        if not search_root.is_dir():
            continue
        for py_file in sorted(search_root.rglob("*.py")):
            try:
                tree = ast.parse(
                    py_file.read_text(encoding="utf-8"), filename=str(py_file)
                )
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "_REUSE_ANALYSIS_HEADING_RE"
                    ):
                        found.append(py_file)
    return found


def test_check_reuse_first_design_never_defines_its_own_reuse_analysis_heading_regex() -> (
    None
):
    """Negative AT for D2 / Architecture-Tests row "Exactly one Reuse
    Analysis heading predicate exists in the tree": `check_reuse_first_
    design.py` must NEVER carry its own `_REUSE_ANALYSIS_HEADING_RE`-named
    module-level definition -- it must import and route through
    `is_reuse_analysis_heading` instead. Fails for real today: the lenient
    CONTAINS regex is still independently defined in
    scripts/cli/check_reuse_first_design.py.
    """
    definitions = _module_level_reuse_heading_regex_definitions(_REPO_ROOT)
    offenders = [p for p in definitions if p.name != "validate_feature_delta.py"]
    assert offenders == [], (
        "expected ZERO _REUSE_ANALYSIS_HEADING_RE-named definitions outside "
        "validate_feature_delta.py (DD-7: exactly one Reuse Analysis "
        f"heading predicate must exist in the tree) -- found: "
        f"{[str(p.relative_to(_REPO_ROOT)) for p in offenders]!r}. "
        "check_reuse_first_design.py must delete its own lenient regex and "
        "import is_reuse_analysis_heading from validate_feature_delta "
        "instead."
    )
