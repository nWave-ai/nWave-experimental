"""Regression: the feature-end full-suite leg's verdict must track a
contributor's REAL source, never be silently confused by -- nor silently
opaque about -- a leftover generated/build directory sitting in the repo.

Authored FROM THE CHARTER ONLY:
docs/product/expectations/fix-stale-build-output-contamination/
gate-verdict-reflects-real-source-not-stale-output.md

This file does NOT read, reuse, or take any shape from
``tests/bugs/test_bug_primary_collect_shadowed_by_generated_dir.py`` (that
draft predates the charter and is SUSPECT -- it may encode the wrong fix
shape, a fixed build/dist name-list, which the charter's own negative
oracles reject). The charter wins by construction.

RCA (diagnosed empirically against this worktree, ahead of authoring):
``src/des/application/feature_end_cycle_service.py::_repo_has_contract_suite``
already prunes a DENYLIST of well-known generated-dir names (``build``,
``dist``, ...) from BOTH its primary and marker-agnostic secondary collect
scopes (``_CONTRACT_SUITE_PRUNE_DIRS``). Empirically confirmed today:

* A healthy repo + a stale, broken ``build/`` copy -> the leg genuinely RUNS
  and CERTIFIES (``FullSuiteLegRan``) -- but the returned outcome carries
  ONLY ``pytest_exit_code``, exactly ONE field, with NO trace anywhere that
  ``build/`` was ever seen, considered, or excluded. The charter's own
  oracle -- "When the check disregards a directory as stale/generated
  output, it says so visibly (names the directory, states it was excluded
  and why)... it is not an invisible internal choice" -- is UNMET: the
  exclusion is a completely silent, unobservable internal choice today.
  THIS is the positive defect this file's active-RED tests pin down.
* The SAME fixture with the generated dir renamed to ``_stage`` (a name
  outside the denylist) already correctly yields
  ``FullSuiteLegIndeterminate`` (never a silent clean pass) -- the
  epistemic-vs-ontological machinery (DDD-CERT-3) already in this function
  handles the differently-named case HONESTLY today, just via a DIFFERENT
  observable class of outcome than the well-known-name case (Indeterminate
  vs silently-successful). These are pinned as NEGATIVE (must-not-regress)
  oracles -- correct today, and this file protects them from a naive
  "widen the name list" fix that would turn them into a false positive.
  a real, hand-authored ``build_utils/`` test-helper package (a build-ish
  NAME, genuine content) is also already correctly NOT blinded -- pinned
  as a negative oracle too.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring
pass.

Driving surface (Mandate-13 driving-port-only, in-process): the dispatch
names the real seam under test as
``feature_end_cycle_service._repo_has_contract_suite``, invoked directly
over synthetic ``tmp_path`` target repos -- the SAME boundary-guard pattern
the sibling
``tests/bugs/test_bug_collect_error_is_indeterminate_not_absent.py`` (an
asset, freely read/reused for its established fixture-and-driving-surface
conventions -- it is NOT the excluded suspect file) already establishes for
this exact leg family: leg-level functions called directly, PLUS one
cycle-level real-CLI consequence test for the driving-port-only mandate.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from des.application import feature_end_cycle_service as svc
from des.cli import feature_end as feature_end_cli


_FEATURE_ID = "stale-output-fixture"

# ADR-GV-002 D4: `des feature-end run` exit 3 == CycleIndeterminate.
_EXPECTED_INDETERMINATE_EXIT = 3

# Keywords a WHAT/WHY explanation of a disregarded directory could
# reasonably use -- the fix's exact wording is a DELIVER decision, this
# file only requires SOME visible naming-plus-reasoning, never a specific
# sentence.
_EXCLUSION_EXPLANATION_KEYWORDS = (
    "exclud",
    "prun",
    "ignor",
    "skip",
    "generat",
    "stale",
    "disregard",
    "build output",
)


# ---------------------------------------------------------------------------
# Fixture builders.
# ---------------------------------------------------------------------------


def _seed_healthy_source_and_tests(repo_root: Path) -> None:
    """A real package with genuine source + a genuine, currently-passing
    test suite -- the charter's "real, current source and tests" that every
    verdict must trace to."""
    pkg = repo_root / "widgetpkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_core.py").write_text(
        "import pytest\n\n\n@pytest.mark.unit\ndef test_add():\n"
        "    from widgetpkg.core import add\n\n"
        "    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "widgetpkg"\nversion = "0.1.0"\n', encoding="utf-8"
    )


def _seed_stale_broken_copy(repo_root: Path, dirname: str) -> None:
    """A leftover generated/build directory under ``dirname`` carrying an
    OLD, stale copy of the source tree, deliberately broken so that
    importing it raises an error -- verbatim the charter's Preconditions
    (referencing a module/name that no longer exists in the real source).
    Confirmed empirically to raise a genuine pytest COLLECTION error (exit
    2), never a genuine "no tests collected" (exit 5)."""
    stale_tests = repo_root / dirname / "tests"
    stale_tests.mkdir(parents=True)
    (stale_tests / "test_core.py").write_text(
        "import widgetpkg_core_module_that_no_longer_exists\n\n\n"
        "def test_add_stale():\n    assert True\n",
        encoding="utf-8",
    )


def _seed_real_build_ish_named_package(repo_root: Path) -> None:
    """A real, hand-written package literally named ``build_utils/`` -- a
    name that merely CONTAINS a build-ish substring -- with its own genuine,
    currently-passing tests inside. The charter's oracle: this must be
    found and counted, never pruned away as collateral damage of a
    build/dist-shaped denylist."""
    pkg = repo_root / "build_utils"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "helper.py").write_text("def helper():\n    return 42\n", encoding="utf-8")
    tests_dir = pkg / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_helper.py").write_text(
        "import pytest\n\n\n@pytest.mark.unit\ndef test_helper():\n"
        "    from build_utils.helper import helper\n\n"
        "    assert helper() == 42\n",
        encoding="utf-8",
    )


def _seed_feature_dir(repo_root: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal) -- mirrors the sibling AT's own
    ``_seed_feature_dir``, keeping the fixture focused on the full-suite
    leg alone."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


def _stub_non_full_suite_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short-circuit every OTHER leg so only the REAL (unstubbed)
    full-suite leg -- and its real collection subprocess -- can determine
    the cycle's outcome. Mirrors the sibling AT's own
    ``_stub_non_full_suite_legs`` verbatim."""
    monkeypatch.setattr(
        svc,
        "_run_walking_skeleton_gate",
        lambda *, repo_root, feature_dir: repo_root,
    )
    monkeypatch.setattr(
        svc,
        "_run_environmental_e2e_gate",
        lambda *, ledger, repo_root, feature_id, feature_dir, walking_skeleton: None,
    )
    monkeypatch.setattr(
        svc,
        "_run_coverage_map_verify_leg",
        lambda *, ledger, repo_root, feature_id, feature_dir: None,
    )


def _run_cycle_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    *,
    planter: Callable[[Path], None],
    feature_id: str = _FEATURE_ID,
) -> tuple[int, dict[str, object]]:
    """Stage a target-repo fixture (via ``planter``) and drive the REAL
    ``des feature-end run`` CLI in-process (Layer 3 composition). Returns
    ``(exit_code, parsed_json_payload)`` -- the command's real observables."""
    _stub_non_full_suite_legs(monkeypatch)
    repo_root = tmp_path / "target-repo"
    repo_root.mkdir()
    planter(repo_root)
    feature_dir = _seed_feature_dir(repo_root, feature_id)

    exit_code = feature_end_cli.main(
        [
            "run",
            "--repo",
            str(repo_root),
            "--feature-id",
            feature_id,
            "--feature-dir",
            str(feature_dir),
            "--reviewer-agent-id",
            "nw-software-crafter-reviewer",
            "--verdict",
            "APPROVED",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    return exit_code, payload


# ---------------------------------------------------------------------------
# 1. POSITIVE (the defect, active-RED today) -- visibility of the exclusion.
# ---------------------------------------------------------------------------


def test_stale_build_dir_exclusion_is_named_when_leg_certifies(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a repo carrying a healthy real
    source/tests suite PLUS a stale, broken ``build/`` copy must, when the
    full-suite leg genuinely certifies, name ``build`` SOMEWHERE in its
    observable outcome -- the charter's own oracle: "When the check
    disregards a directory as stale/generated output, it says so visibly
    (names the directory...) -- the contributor can see and verify that
    decision, it is not an invisible internal choice."

    Today ``FullSuiteLegRan`` carries exactly ONE field
    (``pytest_exit_code``) -- ``build`` is pruned from collection but never
    named anywhere in the outcome. This assertion is what fails.
    """
    repo_root = tmp_path / "stale-build-repo"
    repo_root.mkdir()
    _seed_healthy_source_and_tests(repo_root)
    _seed_stale_broken_copy(repo_root, "build")

    outcome = svc._run_full_suite_leg(repo_root=repo_root)

    assert isinstance(outcome, svc.FullSuiteLegRan), (
        "the healthy real source/tests must still certify even with a "
        f"stale build/ dir alongside it: got {outcome!r}"
    )
    outcome_repr = repr(outcome)
    assert "build" in outcome_repr, (
        "the disregarded generated directory ('build') must be NAMED "
        "somewhere in the leg's observable outcome -- it must never be an "
        f"invisible internal choice (the charter's own wording): {outcome_repr!r}"
    )


def test_stale_build_dir_exclusion_explains_why_it_was_disregarded(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): naming the directory alone is not
    enough -- the charter demands the check "states it was excluded and
    why". Today's ``FullSuiteLegRan`` carries no explanation text at all
    (only a bare exit code); this assertion is what fails.
    """
    repo_root = tmp_path / "stale-build-repo"
    repo_root.mkdir()
    _seed_healthy_source_and_tests(repo_root)
    _seed_stale_broken_copy(repo_root, "build")

    outcome = svc._run_full_suite_leg(repo_root=repo_root)

    assert isinstance(outcome, svc.FullSuiteLegRan), (
        f"expected FullSuiteLegRan to inspect its exclusion explanation: "
        f"got {outcome!r}"
    )
    outcome_repr = repr(outcome).lower()
    assert any(kw in outcome_repr for kw in _EXCLUSION_EXPLANATION_KEYWORDS), (
        "the leg's observable outcome must explain WHY the directory was "
        "disregarded (e.g. 'excluded as stale generated output'), not just "
        f"silently succeed with a bare exit code: {outcome_repr!r}"
    )


# ---------------------------------------------------------------------------
# 2. NEGATIVE -- ordinary behavior for the well-known baseline and the
#    clean repo must be unaffected by the fix.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_healthy_repo_with_well_known_stale_dir_still_certifies(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (must not regress): the baseline fixture (healthy real
    source/tests + stale broken ``build/``) must still certify -- the
    verdict traces to the real source, never to the stale copy's broken
    imports. The visibility fix (tests above) must layer ON TOP of this,
    never replace a genuine PASS with a refusal or an INDETERMINATE.
    """
    repo_root = tmp_path / "stale-build-repo"
    repo_root.mkdir()
    _seed_healthy_source_and_tests(repo_root)
    _seed_stale_broken_copy(repo_root, "build")

    outcome = svc._run_full_suite_leg(repo_root=repo_root)

    assert isinstance(outcome, svc.FullSuiteLegRan), (
        f"a healthy real suite alongside a stale build/ dir must still "
        f"genuinely RUN and CERTIFY: got {outcome!r}"
    )
    assert outcome.pytest_exit_code in (0, 5), (
        f"the certified run must reflect the healthy real suite's own exit "
        f"code, never an error attributable to the stale copy: {outcome!r}"
    )


@pytest.mark.negative_at
def test_clean_repo_without_any_stale_dir_is_unaffected(tmp_path: Path) -> None:
    """NEGATIVE AT (must not regress): a repo with NO stale/generated
    directory at all must behave exactly as a contributor already expects
    -- the fix must not alter the ordinary case."""
    repo_root = tmp_path / "clean-repo"
    repo_root.mkdir()
    _seed_healthy_source_and_tests(repo_root)

    outcome = svc._run_full_suite_leg(repo_root=repo_root)

    assert isinstance(outcome, svc.FullSuiteLegRan), (
        f"a clean repo with no stale directory must certify normally: got {outcome!r}"
    )


# ---------------------------------------------------------------------------
# 3. NEGATIVE -- real content under a build-ish NAME must not be blinded.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_build_ish_named_real_package_is_not_blinded(tmp_path: Path) -> None:
    """NEGATIVE AT (must not regress): a repo whose ONLY suite lives under a
    real, hand-written package literally named ``build_utils/`` (a
    build-ish NAME, genuine content) must still have its real tests found
    and counted -- never pruned away merely because the name resembles a
    build artifact. Deliberately carries NO other top-level tests/ dir, so
    a regression that widens the denylist to substring-match 'build*'
    would collapse this repo to NOT_APPLICABLE.
    """
    repo_root = tmp_path / "build-ish-name-repo"
    repo_root.mkdir()
    _seed_real_build_ish_named_package(repo_root)
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "hostpkg"\nversion = "0.1.0"\n', encoding="utf-8"
    )

    presence = svc._repo_has_contract_suite(repo_root)

    assert presence is True, (
        "a real, hand-written build_utils/ package with its own genuine "
        f"tests must be found and counted, never blinded: got {presence!r}"
    )


# ---------------------------------------------------------------------------
# 4. NEGATIVE -- the non-contamination guarantee must not depend on the
#    stale directory carrying one of the "expected" names, and the check
#    must surface uncertainty rather than a silent confident verdict.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_differently_named_stale_dir_is_never_silently_declared_clean(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (must not regress): the SAME baseline fixture, with the
    generated directory renamed to something outside the well-known
    ``build``/``dist`` denylist (``_stage``), must NEVER be silently
    accepted as a clean, confident PASS -- the charter: "the check must not
    silently pass (declare clean) on a repo where contamination is present
    but the directory's name was not anticipated." Today this already
    yields ``FullSuiteLegIndeterminate`` (an honest "I could not tell"),
    which this test pins as the required floor: whatever shape the visible
    fix takes, it must never regress THIS case to a silent
    ``FullSuiteLegRan``/``True`` that never even considers ``_stage``.
    """
    repo_root = tmp_path / "renamed-stale-repo"
    repo_root.mkdir()
    _seed_healthy_source_and_tests(repo_root)
    _seed_stale_broken_copy(repo_root, "_stage")

    outcome = svc._run_full_suite_leg(repo_root=repo_root)

    assert not isinstance(outcome, svc.FullSuiteLegRan), (
        "a differently-named stale directory carrying broken content must "
        "never be silently folded into a confident PASS just because its "
        f"name was not anticipated: got {outcome!r}"
    )
    assert isinstance(outcome, svc.FullSuiteLegIndeterminate), (
        "when the check cannot confidently tell real source apart from a "
        "differently-named stale generated copy, it must surface that "
        f"uncertainty (INDETERMINATE), never a confident FAIL either: "
        f"got {outcome!r}"
    )


@pytest.mark.negative_at
def test_repo_whose_only_suite_is_stale_content_under_well_known_name_stays_not_applicable(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (must not regress, charter Negative oracle A): a repo
    whose ONLY test content anywhere is the stale copy under a well-known
    generated-dir name (``build/``) must NEVER be accepted as if it were
    the real project's own suite -- the check must report NOT_APPLICABLE
    (no real suite exists), never a false PASS built solely on stale
    content.
    """
    repo_root = tmp_path / "only-stale-well-known-repo"
    repo_root.mkdir()
    _seed_stale_broken_copy(repo_root, "build")

    presence = svc._repo_has_contract_suite(repo_root)

    assert presence is False, (
        "a suite consisting SOLELY of a stale copy under a well-known "
        "generated-dir name must never be accepted as if it were the real "
        f"project's own suite: got {presence!r}"
    )


@pytest.mark.negative_at
def test_repo_whose_only_suite_is_stale_content_under_unanticipated_name_is_never_accepted_as_real(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (must not regress, charter Negative oracle A + C
    combined): a repo whose ONLY test content anywhere is a stale, broken
    copy under a NAME OUTSIDE the well-known denylist (``_stage/``) must
    also never be silently accepted as if it were the real project's own
    passing suite -- the non-contamination guarantee must not depend on
    the directory's name being anticipated.
    """
    repo_root = tmp_path / "only-stale-unanticipated-repo"
    repo_root.mkdir()
    _seed_stale_broken_copy(repo_root, "_stage")

    presence = svc._repo_has_contract_suite(repo_root)

    assert presence is not True, (
        "a suite consisting SOLELY of a stale copy under an unanticipated "
        "directory name must never be silently accepted as real (True): "
        f"got {presence!r}"
    )


# ---------------------------------------------------------------------------
# 5. NEGATIVE -- the cycle-level consequence (driving-port-only, Mandate-13):
#    genuine uncertainty over an unanticipated stale dir must never let the
#    cycle sign a verdict.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_cycle_never_certifies_over_an_unanticipated_stale_dir_it_could_not_judge(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (must not regress) -- the CONSEQUENCE at the cycle level,
    driven through the REAL ``des feature-end run`` CLI (Mandate-13
    driving-port-only): a repo whose full-suite leg genuinely cannot tell
    real source apart from an unanticipated-named stale copy must reach
    ``CycleIndeterminate`` (exit 3), never a signed ``CycleSuccess`` /
    ``FeatureEndCycleComplete`` -- the contributor must never see "I looked
    and it's clean" when the check actually could not tell.
    """

    def _planter(repo_root: Path) -> None:
        _seed_healthy_source_and_tests(repo_root)
        _seed_stale_broken_copy(repo_root, "_stage")

    exit_code, payload = _run_cycle_cli(monkeypatch, capsys, tmp_path, planter=_planter)

    assert exit_code == _EXPECTED_INDETERMINATE_EXIT, (
        "a repo whose full-suite leg cannot tell real source apart from an "
        "unanticipated-named stale copy must exit "
        f"{_EXPECTED_INDETERMINATE_EXIT} (CycleIndeterminate): got exit "
        f"{exit_code}, payload={payload!r}"
    )
    assert payload.get("event") == "FeatureEndCycleIndeterminate", (
        f"expected FeatureEndCycleIndeterminate: payload={payload!r}"
    )
    assert "verdict_hash" not in payload, (
        "no signed verdict may be produced while the full-suite leg cannot "
        f"tell real source apart from stale generated output: payload={payload!r}"
    )
