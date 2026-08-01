"""Regression -- carpaccio ceiling SSOT + the `@coupled` authoring affordance.

Feature ``fix-carpaccio-ceiling-coupled-surface`` (backlog
``F-CARPACCIO-CEILING-7-AND-COUPLED-SURFACE``, ratified 2026-07-05).

DEFECT 1 -- DIVERGENT ceiling SSOT: the carpaccio slice-size ceiling default
lives in >=3 loci that DISAGREE -- ``carpaccio_format.py:57``
``_DEFAULT_SLICE_MAX = 3``, its docstring example (``_scan_atdd_pure_int``,
``carpaccio_slice_max: 3``), and ``.nwave/config.yaml:28``
(``carpaccio_slice_max: 5``). The ratified value 7 exists NOWHERE in code.
This violates one-locus-SSOT: a ceiling change must be ONE edit.

DEFECT 2 -- MISSING inline affordance: the `@coupled` override (which clears
a genuinely-coupled over-ceiling slice as ``CoupledSliceAccepted`` instead of
forcing a re-slice, see ``carpaccio_format.py:_check_slice_size_count``) is
self-explaining ONLY in the gate's rejection message (reactive) -- it is
ABSENT from the authoring surfaces (``nw-discuss`` Slice Plan vocabulary,
``nw-buddy-wave-knowledge``). A reasoner-ahead declares a false wall.

AT-a / AT-b / AT-c drive the SAME production function the entry gate calls
(``check_carpaccio`` / ``_check_slice_size_count``) -- the driving-port-only
mandate is satisfied by reusing the real gate logic, never a re-implemented
shadow check. AT-d is a doc-content assertion (no executable port exists for
"the affordance is documented"); it reads the two authoring-surface SKILL.md
files directly -- these ARE the shipped artifact (the source-of-truth in
``nWave/skills/``, mirrored byte-identical into the installed
``~/.claude/skills`` tree).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from des.cli.carpaccio_format import (
    _DEFAULT_SLICE_MAX,
    GateError,
    Scenario,
    SlicePlan,
    SlicePlanRow,
    _config_slice_max,
    check_carpaccio,
)


_REPO_ROOT = Path(__file__).resolve().parents[4]
_CARPACCIO_FORMAT_PATH = _REPO_ROOT / "src" / "des" / "cli" / "carpaccio_format.py"
_CONFIG_PATH = _REPO_ROOT / ".nwave" / "config.yaml"
_RATIFIED_CEILING = 15  # raised from 7 (Ale, 2026-08-01) -- see carpaccio_format.py


def test_repo_root_resolution_sanity() -> None:
    """Self-check: ``_REPO_ROOT`` must resolve to the real repo root.

    Guards every other test in this file -- if the ``parents[N]`` depth ever
    drifts (test relocated to a different directory depth), every path-based
    assertion below would silently read the wrong file instead of failing
    loudly here first.
    """
    assert (_REPO_ROOT / "pyproject.toml").is_file(), (
        "repo-root resolution is wrong -- expected pyproject.toml at "
        f"{_REPO_ROOT}; fix the parents[N] depth in this test file"
    )


# --- AT-a: ONE-LOCUS ceiling SSOT --------------------------------------------


def test_default_slice_max_is_the_ratified_ceiling_of_fifteen() -> None:
    """The canonical constant is the RATIFIED ceiling (15), not a stale value.

    Ale originally ratified 7 on 2026-07-05
    (F-CARPACCIO-CEILING-7-AND-COUPLED-SURFACE), then raised it to 15 on
    2026-08-01 once the escape valve proved itself the correct call on
    cohesive slices. This test pins the ONE canonical locus to whatever the
    current ratified value is -- it must never silently drift.
    """
    assert _DEFAULT_SLICE_MAX == _RATIFIED_CEILING, (
        f"_DEFAULT_SLICE_MAX must be the ratified ceiling {_RATIFIED_CEILING}, "
        f"found {_DEFAULT_SLICE_MAX} -- update the ONE canonical locus in "
        "carpaccio_format.py"
    )


def test_scan_atdd_pure_int_docstring_does_not_carry_a_diverging_literal() -> None:
    """The ``_scan_atdd_pure_int`` docstring's config example must not hardcode
    a numeric literal that diverges from the canonical ``_DEFAULT_SLICE_MAX``.

    Today the docstring shows ``carpaccio_slice_max: 3`` -- a second, silently
    stale copy of the ceiling that drifts the moment the canonical constant
    changes. One-locus-SSOT requires either a non-numeric placeholder, or a
    literal that always agrees with the canonical constant.
    """
    source = _CARPACCIO_FORMAT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_CARPACCIO_FORMAT_PATH))
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_scan_atdd_pure_int"
    )
    docstring = ast.get_docstring(fn) or ""
    match = re.search(r"carpaccio_slice_max:\s*(\d+)", docstring)
    assert match is None or int(match.group(1)) == _DEFAULT_SLICE_MAX, (
        "the docstring example hardcodes carpaccio_slice_max: "
        f"{match.group(1) if match else None!r}, which diverges from the "
        f"canonical _DEFAULT_SLICE_MAX={_DEFAULT_SLICE_MAX} -- use a "
        "non-numeric placeholder or keep the example in lockstep with the "
        "one canonical locus"
    )


def test_project_config_yaml_ceiling_does_not_diverge_from_the_canonical_default() -> (
    None
):
    """``.nwave/config.yaml``'s ``carpaccio_slice_max`` must equal the canonical
    default -- never a THIRD independently-drifted literal.

    Today the repo's own config carries 5, while the code default is 3 and
    the ratified value is 7 -- three numbers, one ceiling, the exact
    divergence this feature closes. Project config MAY still override the
    ceiling deliberately, but it must not silently disagree with the
    canonical constant it is meant to specialize.
    """
    resolved = _config_slice_max(_REPO_ROOT)
    assert resolved == _DEFAULT_SLICE_MAX, (
        f"repo .nwave/config.yaml resolves carpaccio_slice_max={resolved}, "
        f"which diverges from the canonical _DEFAULT_SLICE_MAX="
        f"{_DEFAULT_SLICE_MAX} -- either remove the project override (inherit "
        "the canonical default) or raise it to match the ratified ceiling "
        f"at {_CONFIG_PATH}"
    )


# --- shared scenario/plan builders (AT-b, AT-c) -------------------------------


def _scenario(slice_id: str, *, coupled: bool, ordinal: int) -> Scenario:
    return Scenario(
        slice_tags=(slice_id,),
        has_coupled_tag=coupled,
        normalized_body=f"given precondition {ordinal}\nwhen action {ordinal}\nthen outcome {ordinal}",
    )


def _single_row_plan(
    slice_id: str, *, annotation: str = "", justification: str = ""
) -> SlicePlan:
    return SlicePlan(
        rows=(
            SlicePlanRow(
                slice_id=slice_id,
                value_statement="a thin end-to-end vertical",
                status="pending",
                annotation=annotation,
                justification=justification,
            ),
        )
    )


# --- AT-b: CEILING-7 CLEARS ---------------------------------------------------


def test_six_at_slice_clears_carpaccio_under_the_default_ceiling(
    tmp_path: Path,
) -> None:
    """A 6-AT slice (no ``@coupled``) must CLEAR ``check_carpaccio`` under the
    project-resolved default ceiling -- 6 <= 7.

    FAILS TODAY: the default resolves to 3 (code) or 5 (this repo's own
    config) -- both below 6 -- so the gate raises
    ``CARPACCIO_SLICE_TOO_LARGE`` for a slice that the ratified ceiling of 7
    should accept outright, no ``@coupled`` escape needed.
    """
    slice_max = _config_slice_max(tmp_path)  # no .nwave/config.yaml -> pure default
    plan = _single_row_plan("slice-01")
    scenarios = [_scenario("slice-01", coupled=False, ordinal=i) for i in range(6)]

    try:
        result = check_carpaccio(plan, scenarios, "slice-01", slice_max)
    except GateError as exc:
        pytest.fail(
            "a 6-AT slice with no @coupled tag must clear under the default "
            f"ceiling ({slice_max}) -- check_carpaccio raised instead: "
            f"{exc.payload!r}"
        )

    assert result is None, (
        "a clearing check_carpaccio call returns None (no CoupledSliceAccepted "
        f"escape needed for an in-ceiling slice) -- observed {result!r}"
    )


# --- AT-c: OVERRIDE PRESERVED (regression-lock guard) -------------------------


def test_sixteen_coupled_ats_still_clear_via_the_coupled_escape(tmp_path: Path) -> None:
    """GUARD (regression-lock): a 16-AT slice where EVERY scenario carries
    ``@coupled`` AND the plan row records a justification must still clear
    via ``CoupledSliceAccepted`` -- raising the ceiling default must never
    remove or weaken this escape.

    This assertion is expected to PASS today (the escape already exists) --
    it exists to CATCH a future fix that raises the ceiling but accidentally
    drops or narrows the ``@coupled`` override. Count raised 9 -> 16 (Ale,
    2026-08-01) alongside the ceiling raise 7 -> 15, so the fixture still
    genuinely exceeds whatever ceiling is in effect.
    """
    slice_max = _config_slice_max(tmp_path)
    assert slice_max < 16, (
        "test setup invariant broken: 16 ATs must exceed whatever ceiling is "
        f"in effect ({slice_max}) so the size check actually engages the "
        "coupled-escape branch, not the plain in-ceiling pass-through"
    )
    plan = _single_row_plan(
        "slice-01",
        annotation="@coupled",
        justification=(
            "a cohesive AT group that cannot be decomposed further without "
            "breaking the single end-to-end vertical it proves"
        ),
    )
    scenarios = [_scenario("slice-01", coupled=True, ordinal=i) for i in range(16)]

    result = check_carpaccio(plan, scenarios, "slice-01", slice_max)

    assert isinstance(result, dict) and result.get("event") == "CoupledSliceAccepted", (
        "a fully @coupled, justified, over-ceiling slice must clear via "
        f"CoupledSliceAccepted -- observed {result!r}. If this regresses, "
        "the @coupled escape has been weakened or removed -- do NOT let a "
        "ceiling-raise fix touch this branch."
    )
    assert result.get("at_count") == 16, (
        f"CoupledSliceAccepted must report the true AT count -- observed "
        f"{result.get('at_count')!r}"
    )


# --- AT-d: INLINE AFFORDANCE PRESENT (authoring-surface doc content) ---------


_AUTHORING_SURFACES = (
    _REPO_ROOT / "nWave" / "skills" / "nw-discuss" / "SKILL.md",
    _REPO_ROOT / "nWave" / "skills" / "nw-buddy-wave-knowledge" / "SKILL.md",
)


@pytest.mark.parametrize(
    "surface_path", _AUTHORING_SURFACES, ids=lambda p: p.parent.name
)
def test_coupled_escape_is_documented_on_the_authoring_surface(
    surface_path: Path,
) -> None:
    """A reasoner-ahead of the ceiling must be able to learn about the
    ``@coupled`` escape BEFORE hitting the gate's rejection -- not only from
    the gate's reactive rejection message.

    FAILS TODAY on both surfaces: ``nw-discuss/SKILL.md`` documents the Slice
    Plan's five-column shape but never enumerates ``@coupled`` as an
    Annotation-column token; ``nw-buddy-wave-knowledge/SKILL.md`` documents
    the wave sequence but never mentions ``@coupled`` at all.
    """
    assert surface_path.is_file(), f"expected authoring-surface file at {surface_path}"
    content = surface_path.read_text(encoding="utf-8")

    assert "@coupled" in content, (
        f"{surface_path} must document the `@coupled` Slice Plan annotation "
        "token -- a reasoner-ahead currently has no inline affordance "
        "explaining the over-ceiling escape before hitting the gate's "
        "reactive rejection"
    )
    assert re.search(r"ceiling", content, re.IGNORECASE), (
        f"{surface_path} mentions `@coupled` in isolation without explaining "
        "the ceiling it overrides -- the affordance must connect the tag to "
        "the carpaccio slice-size ceiling it lifts"
    )
