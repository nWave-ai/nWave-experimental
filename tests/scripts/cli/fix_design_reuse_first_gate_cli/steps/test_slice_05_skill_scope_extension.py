"""Step definitions -- slice-05: nw-design skill scope extension (DDD-12).

F-DESIGN-REUSE-FIRST-GATE-CLI slice-05 (F-REUSE-GATE-COVER-METHODOLOGY-
COMPONENTS). DDD-12.

slice-05 closes the seam at the PRODUCING end of the gate. The gate's
methodology file-component unit (slice-03) is non-vacuous only if the upstream
nw-design skill instructs the architect to declare methodology components.

  - AT1 + AT2 are cross-artifact structural assertions on the shipped
    ``nWave/skills/nw-design/SKILL.md`` content (the skill-propagation pattern,
    mirroring the sibling ``fix-design-reuse-first-gate`` slice-03 precedent:
    skill template heading/columns == a normative constant). The coherence
    binding is that the prose names the EXACT methodology-path defaults the
    production gate detects (``nWave/data`` / ``nWave/skills`` /
    ``scripts/cli``), and the lenient-match note documents the file-component
    path and stem forms. These are read-only over the skill asset; the
    @then steps assert via ``assert_state_delta`` over a port-exposed bytes
    universe that the skill is not mutated by the read (Mandate 8).
  - AT3 is the recursive dogfood: the real ``check_reuse_first_design.py`` gate
    (driving port, ``main(argv)``) is run over a self-contained tmp_path git
    fixture that adds a methodology file under a skill-named path -- it PASSes
    when the architect names it in the Reuse Analysis, FAILs when omitted. The
    dogfood Given asserts the skill names the path first, so AT3 is RED until
    the slice-05 crafter extends the skill (the loop is not closed yet).

Layer 3. AT1/AT2 read the real skill file (example-only, no PBT -- single
structural-content assertions). AT3 drives the real gate over a real git
repository (@real-io, example-based, no PBT per Mandate 9 v2 OR-reduction).

Step bodies delegate to ``SkillAssetComposition`` (AT1/AT2) and
``ReuseFirstFixture`` (AT3); no inline business logic (Mandate-12 criterion 3)
-- each body is a typed lookup plus a composition call.

S1 (step-text uniqueness): every step literal here is slice-05-scoped and
distinct from the slice-01/02/03 literals (e.g. "reuse-first GATE" vs slice-03
"reuse-first CHECK"; "exit-gate guidance" / "lenient-match note" surfaces are
slice-05-only). No literal collides with another step file in this feature dir,
so pytest-bdd's global registry cannot shadow another slice's body.

RED contract (Mandate 7): on master the skill's Reuse-first exit-gate prose
scopes only NEW classes under ``src/`` (L115-116) and the lenient-match note
has only the class-name form (L121-123). It names NONE of the methodology-path
kinds and has NO file-component path/stem form. AT1 (names every path) and AT2
(documents both forms) FAIL with a semantic ``AssertionError``
(MISSING_FUNCTIONALITY RED). AT3's dogfood Given asserts the skill names the
path -- it FAILs on master too (the skill names no path), so the whole slice is
RED until the crafter extends the skill (DDD-12). Imports resolve cleanly --
``MethodologyPathKind`` and the slice-03 fixture machinery are shipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import CheckResult, ReuseFirstFixture
from .domain_types import (
    DOGFOOD_VERDICT_BY_NAMING_PHRASE,
    EXIT_CODE_BY_VERDICT,
    METHODOLOGY_PATH_KIND_BY_PHRASE,
    BaseBranch,
    FeatureId,
)
from .skill_assets import (
    LenientMatchNoteView,
    ReuseFirstExitGateProseView,
    SkillAssetComposition,
)


scenarios("../slice-05-skill-scope-extension.feature")


# The canonical methodology-file stem the dogfood scenario commits and
# (sometimes) names. The stem is the file-component key the lenient match
# (DDD-10) reads from the Reuse Analysis Existing Component column.
_DOGFOOD_METHODOLOGY_STEM = "dor-items"


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def skill() -> SkillAssetComposition:
    """Production composition root over the live nw-design skill asset."""
    return SkillAssetComposition()


@pytest.fixture
def dogfood(tmp_path: Path) -> ReuseFirstFixture:
    """Production-wired gate composition over a real tmp_path git repository."""
    return ReuseFirstFixture(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for asset views / CLI result + universe across When -> Then."""
    return {}


# === AT1 + AT2: cross-artifact skill structural assertions ==================


# --- Given -----------------------------------------------------------------


@given("the nw-design skill and the gate's methodology-path defaults")
def given_skill_and_gate_defaults(skill: SkillAssetComposition) -> None:
    # The skill exists in the repository tree -- nothing to provision.
    assert skill.nw_design_skill.is_file()


# --- When ------------------------------------------------------------------


@when("the architect reads the skill's reuse-first exit-gate guidance")
def when_read_exit_gate_prose(
    skill: SkillAssetComposition, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = skill.capture_universe()
    result_box["prose"] = skill.read_exit_gate_prose()


@when("the architect reads the skill's lenient-match note")
def when_read_lenient_match_note(
    skill: SkillAssetComposition, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = skill.capture_universe()
    result_box["note"] = skill.read_lenient_match_note()


# --- Then ------------------------------------------------------------------


@then("the exit-gate guidance names every methodology-path the gate detects")
def then_prose_names_every_path(result_box: dict[str, object]) -> None:
    prose = result_box["prose"]
    assert isinstance(prose, ReuseFirstExitGateProseView)
    assert prose.names_all_methodology_paths, (
        f"the nw-design reuse-first exit-gate prose names only "
        f"{list(prose.named_methodology_paths)} of the gate's methodology-path "
        f"defaults -- it must instruct the architect to declare reuse for "
        f"methodology components (nWave/data, nWave/skills, scripts/cli), not "
        f"only src/ classes (DDD-12); the gate's file-component unit is "
        f"otherwise vacuous"
    )


@then("the lenient-match note documents the methodology file-component path form")
def then_note_documents_path_form(result_box: dict[str, object]) -> None:
    note = result_box["note"]
    assert isinstance(note, LenientMatchNoteView)
    assert note.documents_path_form, (
        "the nw-design lenient-match note has no file-component path form -- it "
        "must document that a methodology file-component is justified when its "
        "repo-relative path appears in an Existing Component cell (DDD-10/DDD-12)"
    )


@then("the lenient-match note documents the methodology file-component stem form")
def then_note_documents_stem_form(result_box: dict[str, object]) -> None:
    note = result_box["note"]
    assert isinstance(note, LenientMatchNoteView)
    assert note.documents_stem_form, (
        "the nw-design lenient-match note has no file-component stem form -- it "
        "must document that a methodology file-component is justified when its "
        "stem appears in an Existing Component cell (DDD-10/DDD-12)"
    )


@then("reading the skill leaves it unchanged")
def then_skill_unchanged(
    skill: SkillAssetComposition, result_box: dict[str, object]
) -> None:
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=skill.capture_universe(),
        universe={"nw_design_skill.bytes"},
        expected={"nw_design_skill.bytes": unchanged()},
    )


# === AT3: recursive-dogfood -- the real gate closes the loop ================


# --- Given -----------------------------------------------------------------


@given("the nw-design skill instructs the architect to declare methodology components")
def given_skill_instructs_methodology(skill: SkillAssetComposition) -> None:
    """Coherence pre-condition: the dogfood is meaningful only once the skill
    names the methodology paths the gate detects. On master the skill names
    none, so this Given FAILs -- AT3 is RED until the slice-05 crafter extends
    the skill (the end-to-end loop is not yet closed)."""
    prose = skill.read_exit_gate_prose()
    assert prose.names_all_methodology_paths, (
        "the nw-design skill does not yet instruct the architect to declare "
        "methodology components -- the recursive-dogfood loop (skill guidance "
        "-> architect-authored row -> passing gate) cannot close until the "
        "skill names nWave/data, nWave/skills, scripts/cli (DDD-12)"
    )


@given(
    parsers.parse(
        'a feature whose commits add a NEW methodology file under "{methodology_path}"'
    )
)
def given_feature_adds_methodology_file(
    dogfood: ReuseFirstFixture, methodology_path: str
) -> None:
    dogfood.create_feature(FeatureId("reuse-first-cli-demo"))
    dogfood.init_repository(BaseBranch("master"))
    dogfood.commit_methodology_file(
        _DOGFOOD_METHODOLOGY_STEM, METHODOLOGY_PATH_KIND_BY_PHRASE[methodology_path]
    )


@given(
    parsers.parse(
        "the feature {naming} that NEW methodology file in its Reuse Analysis section"
    )
)
def given_feature_names_or_omits(dogfood: ReuseFirstFixture, naming: str) -> None:
    named = [_DOGFOOD_METHODOLOGY_STEM] if naming == "names" else []
    dogfood.write_reuse_analysis_naming(named=named)


# --- When ------------------------------------------------------------------


@when(
    "the architect runs the reuse-first gate on the feature's commit range "
    "with methodology detection"
)
def when_run_dogfood_gate(
    dogfood: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = dogfood.capture_repo_universe()
    result_box["result"] = dogfood.run_check_on_range_with_methodology()


# --- Then ------------------------------------------------------------------


@then(parsers.parse("the methodology-aware commit range reaches the {naming} verdict"))
def then_dogfood_verdict(result_box: dict[str, object], naming: str) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected_verdict = DOGFOOD_VERDICT_BY_NAMING_PHRASE[naming]
    assert result.verdict is expected_verdict, (
        f"recursive-dogfood: expected verdict {expected_verdict.value} when the "
        f"architect {naming} the methodology file, got {result.verdict.value} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the end-to-end loop (skill guidance -> "
        f"architect-authored row -> gate verdict) is not closed"
    )
    expected_exit = EXIT_CODE_BY_VERDICT[expected_verdict]
    assert result.exit_code == expected_exit, (
        f"expected exit code {expected_exit} for verdict "
        f"{expected_verdict.value}, got {result.exit_code}"
    )


@then("running the reuse-first gate leaves the feature repository unchanged")
def then_dogfood_repo_unchanged(
    dogfood: ReuseFirstFixture, result_box: dict[str, object]
) -> None:
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=dogfood.capture_repo_universe(),
        universe={
            "feature_delta.bytes",
            "repo.head_sha",
            "repo.porcelain_status",
        },
        expected={
            "feature_delta.bytes": unchanged(),
            "repo.head_sha": unchanged(),
            "repo.porcelain_status": unchanged(),
        },
    )
