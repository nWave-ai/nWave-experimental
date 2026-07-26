"""Regression -- the f-attest-bundled-slice slice-01 AT must prove reverify's
shared-core-extraction claim on a small SYNTHETIC pytest project, not by
nesting a `pytest.main()` call over this repo's own REAL test suite inside
itself.

DEFECT: `tests/des/acceptance/attest_bundled_slice/steps/
test_slice_01_scaffold.py` (~3.95 min measured, `.test_durations`) drives its
"Extracting the shared core preserves reverify's existing behaviour" scenario
through `when_the_reverify_suite_is_rerun` (`steps/
composition_slice_01_scaffold.py::AttestScaffoldComposition
.when_the_reverify_suite_is_rerun` -> `._rerun_reverify_suite`), which calls
`pytest.main([...])` **in-process** over `tests/des/acceptance/
test_reverify_slice_commit.py` -- itself a 2.80-min acceptance suite -- so
that suite is paid TWICE: once on its own, once nested inside this scenario.
The single scenario measured 236.7s and is, by itself, essentially the whole
file's 3.95-min cost. This file is also the #1 contributor to the serialized
`real_repo_scan` xdist group (`tests/conftest.py::_item_depends_on_real_repo`
walks the scenario's import closure into `composition_slice_01_scaffold.py`,
which contains a literal `cwd=_repo_root()` subprocess-shaped call --
`_REAL_REPO_CWD_RE`, `tests/conftest.py:1405-1417` -- and pins the whole file
to the one-worker serialized group).

Charter: ``docs/product/expectations/fix-nested-pytest-self-invocation-
synthetic-fixture/two-acceptance-tests-re-run-this-repos-real-test-suite-
inside-themselves-via-a-nested-pytestmain.md``. The fix (crafter's job --
NOT implemented by this AT, test-authoring only, zero production/target-test
edits) swaps `_rerun_reverify_suite` onto a small synthetic pytest project
that reproduces the exact behaviour under test (a suite-rerun + a
shared-core-identity claim), completing in low single-digit seconds while
still proving the identical claim, and drops the file OUT of the
`real_repo_scan` serialized group.

Reuse-first precedent (same shape, read in full before authoring this file):
commit f337ece8e "fix(tests): swap two slow contract-gate self-tests to
synthetic fixture" -- regression test
``tests/bugs/des/test_contract_gate_self_tests_use_synthetic_fixture_not_real_repo.py``,
synthetic fixture ``ContractGateDigestComposition._stage_collapse_prone_project``
(``tests/des/cli/fix_contract_gate_digest_undercount/steps/
composition.py:392-439``).

This file pins FOUR independent contracts (the three-part shape the charter
demands, plus one mechanical corollary the operating dispatch adds):

1. TIMING -- the ONE scenario driving the nested `pytest.main()`
   (`test_extracting_the_shared_core_preserves_reverifys_existing_behaviour`)
   must complete within a generous-but-meaningful ceiling (30s -- far above
   what a handful-of-items synthetic fixture plus the composition's
   child-interpreter core-identity probe needs, far below today's measured
   236.7s / 3.95-min-file cost). Measured BEHAVIOURALLY: an actual bounded
   `pytest` subprocess run of the real nodeid, timed out at the ceiling
   (never waiting out the full 236.7s), so a cosmetic edit that does not
   really relocate the cost cannot satisfy it. RED today: the scenario still
   pays the real 2.80-min reverify-suite cost, so the bounded run times out
   well before it finishes.
2. NON-VACUOUS ORACLE (the important half per the charter) -- a small
   synthetic pytest project, reproducing the SAME shape of claim this
   scenario proves (a suite-rerun via `pytest.main()` whose outcome depends
   on a "core" module's correctness), must not be too trivial to ever fail:
   driven in "healthy" mode it exits 0, and driven in "broken" mode (the
   core module perturbed to a known-wrong value) it exits non-zero. No
   fixture of this shape existed in the repo before this file (verified by
   search -- see the reuse-first precedent's own fixture, which guards a
   DIFFERENT defect class); authored here, self-contained, module-local, per
   the "cite/reuse if found, author if not" instruction. Already GREEN
   today -- a capability floor independent of whether
   `composition_slice_01_scaffold.py` has been swapped onto it.
3. MECHANICAL (dispatch-added corollary) -- once fixed,
   `tests/conftest.py::_item_depends_on_real_repo()` must return `False` for
   the converted file: the mechanical form of "it no longer drives the real
   tree", checked directly rather than inferred from the speedup. RED today
   (measured `True` against this file at HEAD, via the composition's
   `cwd=_repo_root()` literal).
4. NEGATIVE -- no nested `pytest.main()` (or `-m pytest` child) targeting
   THIS repo's own `test_reverify_slice_commit.py` remains in the
   composition module. A static source-shape check (legitimate for this
   specific negative claim, per the charter's own "the recursion is
   removed, not merely bounded by a timeout" framing) -- distinct from, and
   never a substitute for, the BEHAVIOURAL timing pin above. RED today: the
   literal suite path is still referenced as a `pytest.main()` target.

Driving surface: item 1 and item 4's companion probe are driven as bounded
subprocess/source-scan checks against the REAL target file -- this file never
imports `AttestScaffoldComposition` or any of its production-adjacent step
modules directly (the target is driven through its own pytest nodeid, never
imported). Item 3 imports `tests.conftest` -- test infrastructure already
loaded for this very session, reused verbatim (DRY) per the sibling
`test_xdist_group_real_repo_scan_swallows_the_suite.py` precedent's own
`import tests.conftest as suite_conftest` idiom.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]

_TARGET_FILE_REL = (
    "tests/des/acceptance/attest_bundled_slice/steps/test_slice_01_scaffold.py"
)
_TARGET_ITEM = (
    f"{_TARGET_FILE_REL}"
    "::test_extracting_the_shared_core_preserves_reverifys_existing_behaviour"
)
_COMPOSITION_FILE_REL = (
    "tests/des/acceptance/attest_bundled_slice/steps/composition_slice_01_scaffold.py"
)
_REAL_REVERIFY_SUITE_REL = "tests/des/acceptance/test_reverify_slice_commit.py"

# Generous vs a handful-of-items synthetic fixture + one child-interpreter
# core-identity probe, far below today's measured 236.7s / 3.95-min-file cost
# (per the charter's own "low single-digit seconds" expectation).
_TIMING_CEILING_SECONDS = 30.0


def _completes_within_ceiling(nodeid: str) -> bool:
    """Run one pytest item as its own subprocess, bounded by the ceiling.

    A bounded run (not the full ~236.7s) so THIS regression test itself stays
    cheap even while RED: ``subprocess.run(timeout=...)`` kills the child at
    the ceiling rather than waiting out its real duration.
    """
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", nodeid, "-q", "--tb=no"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=_TIMING_CEILING_SECONDS,
        )
        return True
    except subprocess.TimeoutExpired:
        return False


# ===========================================================================
# 1. TIMING PIN -- the nested-pytest.main() scenario must not exceed the ceiling
# ===========================================================================


@pytest.mark.negative_at
def test_reverify_extraction_scenario_does_not_exceed_timing_ceiling() -> None:
    """The slice-01 "core extraction preserves reverify behaviour" scenario
    must not still pay the nested real-suite `pytest.main()` cost (236.7s
    measured) -- it must complete within the timing ceiling once it drives a
    small synthetic pytest project instead of the real 2.80-min reverify
    suite.
    """
    assert _completes_within_ceiling(_TARGET_ITEM), (
        f"{_TARGET_ITEM} still exceeds the {_TIMING_CEILING_SECONDS}s timing "
        "ceiling (measured 236.7s pre-fix). WHY: its When step "
        "(`when_the_reverify_suite_is_rerun`, `composition_slice_01_scaffold."
        "py::AttestScaffoldComposition._rerun_reverify_suite`) calls "
        "`pytest.main([...])` in-process over the REAL "
        f"`{_REAL_REVERIFY_SUITE_REL}` (a 2.80-min acceptance suite), paying "
        "that suite's cost a second time nested inside this scenario. HOW: "
        "swap `_rerun_reverify_suite`'s target onto a small synthetic pytest "
        "project reproducing the same claim (a suite-rerun outcome that "
        "depends on a shared-core module's correctness) per "
        "docs/product/expectations/fix-nested-pytest-self-invocation-"
        "synthetic-fixture/two-acceptance-tests-re-run-this-repos-real-test-"
        "suite-inside-themselves-via-a-nested-pytestmain.md."
    )


# ===========================================================================
# 2. NON-VACUOUS-ORACLE PIN -- the synthetic fixture must not be too trivial
#    to ever fail
# ===========================================================================

_SYNTHETIC_CORE_MODULE_TEMPLATE = "CORE_VALUE = {value}\n"

_SYNTHETIC_SUITE_MODULE = (
    "from core_module import CORE_VALUE\n\n\n"
    "def test_core_value_is_the_expected_constant():\n"
    "    assert CORE_VALUE == 42\n"
)

_SYNTHETIC_PYPROJECT = '[tool.pytest.ini_options]\naddopts = "-q"\ntestpaths = ["."]\n'


def _stage_synthetic_core_suite(tmp_path: Path, *, healthy: bool) -> Path:
    """Stage a small synthetic pytest project reproducing the SAME shape of
    claim the slice-01 scenario proves: a suite whose outcome (via a
    `pytest.main()`-driven rerun) depends on a "core" module's correctness --
    the exact behaviour under test, at a fraction of the size.

    ``healthy=True`` writes a correct core module (`CORE_VALUE = 42`) so the
    suite passes; ``healthy=False`` perturbs it to a known-wrong value so the
    suite fails -- the non-vacuity proof (see the test below).
    """
    proj = tmp_path / (
        "synthetic_core_suite_healthy" if healthy else "synthetic_core_suite_broken"
    )
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "pyproject.toml").write_text(_SYNTHETIC_PYPROJECT, encoding="utf-8")
    (proj / "core_module.py").write_text(
        _SYNTHETIC_CORE_MODULE_TEMPLATE.format(value=42 if healthy else 0),
        encoding="utf-8",
    )
    (proj / "test_synthetic_core_suite.py").write_text(
        _SYNTHETIC_SUITE_MODULE, encoding="utf-8"
    )
    return proj


def _run_synthetic_suite(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_synthetic_core_suite_fixture_is_not_too_trivial_to_ever_fail(
    tmp_path: Path,
) -> None:
    """The synthetic fixture that will replace the nested real-suite
    `pytest.main()` call must still be CAPABLE of exposing a genuine
    regression -- otherwise the swap would be a false speedup (a smaller
    fixture too trivial to distinguish correct from broken), per the
    charter's explicit non-vacuous-oracle requirement.

    No fixture of this shape (a suite-rerun whose result depends on a "core"
    module's correctness) existed in this repo before this file (verified by
    search -- the reuse-first precedent's own synthetic fixture guards a
    DIFFERENT defect class, digest undercounting, not shared-core-extraction
    correctness); authored here per the "cite/reuse if found, author if not"
    instruction.

    Proof mechanism: stage the fixture in BOTH modes and drive each through
    its own `pytest` subprocess (the same "rerun a suite, read the exit
    code" shape `_rerun_reverify_suite` uses) -- healthy must exit 0, broken
    must exit non-zero. If broken did NOT go red, the fixture could never
    distinguish a correct core extraction from a broken one.
    """
    healthy_project = _stage_synthetic_core_suite(tmp_path, healthy=True)
    broken_project = _stage_synthetic_core_suite(tmp_path, healthy=False)

    healthy_result = _run_synthetic_suite(healthy_project)
    broken_result = _run_synthetic_suite(broken_project)

    assert healthy_result.returncode == 0, (
        "expected the HEALTHY synthetic fixture to pass (CORE_VALUE == 42) -- "
        f"got returncode={healthy_result.returncode}, "
        f"stdout={healthy_result.stdout!r}, stderr={healthy_result.stderr!r}"
    )
    assert broken_result.returncode != 0, (
        "the BROKEN synthetic fixture (CORE_VALUE perturbed to 0) must FAIL -- "
        f"got returncode={broken_result.returncode} (a pass), "
        f"stdout={broken_result.stdout!r}. This fixture is too trivial to "
        "ever distinguish a correct core extraction from a broken one: "
        "swapping the nested-real-suite scenario onto a fixture that can "
        "never fail would be a false speedup, not a fix (the charter's "
        "explicit non-vacuous-oracle negative requirement)."
    )


# ===========================================================================
# 3. MECHANICAL PIN -- the converted file must drop OUT of real_repo_scan
# ===========================================================================


def test_target_file_no_longer_pins_the_real_repo_scan_xdist_group() -> None:
    """`tests/conftest.py::_item_depends_on_real_repo()` must return `False`
    for the converted file -- the mechanical form of "it no longer drives
    the real tree", checked directly rather than inferred from the speedup
    (per the charter's own instruction: "check it, do not infer it from the
    speedup").
    """
    import tests.conftest as suite_conftest

    target_file = (_REPO_ROOT / _TARGET_FILE_REL).resolve()

    assert suite_conftest._item_depends_on_real_repo(target_file) is False, (
        f"{_TARGET_FILE_REL} is still detected as driving a "
        "`cwd=<real repo>` subprocess (tests/conftest.py::"
        "_item_depends_on_real_repo returned True) and is therefore still "
        "pinned onto pytest.mark.xdist_group('real_repo_scan'), serializing "
        "it onto one xdist worker. WHY: its import closure includes "
        f"{_COMPOSITION_FILE_REL}, whose `_run_des` helper calls "
        "`run_cli_in_process(argv, cwd=_repo_root())` -- a literal `cwd=` "
        "keyword argument immediately followed by `_repo_root()`, which "
        "`_REAL_REPO_CWD_RE` (tests/conftest.py:1405-1417) matches. HOW: the "
        "fix must ensure the converted composition module's import closure "
        "no longer contains a `cwd=<real-repo-anchor>` subprocess-shaped "
        "call, so the file drops out of the serialized group."
    )


# ===========================================================================
# 4. NEGATIVE PIN -- no nested pytest.main() against the real reverify suite
#    remains
# ===========================================================================

_REAL_REVERIFY_SUITE_TARGET_RE = re.compile(
    re.escape(_REAL_REVERIFY_SUITE_REL.rsplit("/", maxsplit=1)[-1])
)


def test_composition_module_never_targets_the_real_reverify_suite() -> None:
    """No nested `pytest.main()` (or `-m pytest` child) targeting THIS
    repo's own `test_reverify_slice_commit.py` may remain in the composition
    module -- the recursion must be REMOVED, not merely bounded by a
    timeout (per the charter: "a timeout makes an unbounded recursion
    survivable, never correct").

    A static source-shape check, legitimate for this specific negative claim
    (distinct from, and never a substitute for, the BEHAVIOURAL timing pin
    above -- a source-text proxy could not stand in for that one, per the
    charter's own warning, but "does the source still name the real suite
    file as a nested-run target" is exactly what this negative claim asks).
    """
    composition_source = (_REPO_ROOT / _COMPOSITION_FILE_REL).read_text(
        encoding="utf-8"
    )

    assert not _REAL_REVERIFY_SUITE_TARGET_RE.search(composition_source), (
        f"{_COMPOSITION_FILE_REL} still references "
        f"'{_REAL_REVERIFY_SUITE_REL.rsplit('/', maxsplit=1)[-1]}' -- the composition "
        "module must no longer name the REAL "
        f"{_REAL_REVERIFY_SUITE_REL} as a nested pytest.main()/`-m pytest` "
        "target. The recursion must be removed (swap onto the small "
        "synthetic pytest project), not merely bounded by a timeout."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
