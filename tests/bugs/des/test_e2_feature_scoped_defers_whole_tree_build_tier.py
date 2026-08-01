"""Regression: the E2 leg of ``des commit-slice`` refuses a slice whose OWN
scope is fully green, because an architecture test in a file the slice never
touched -- belonging to a different feature owned by a different concurrent
lane -- is failing.

Measured twice on 2026-07-30 (lanes ``c1-matcher`` and ``D80``); both ended
blocked holding staged, verified-green work. The blocking failures were
legitimate, deliberate active-RED scaffolds of OTHER in-flight features -- the
CORRECT form of atdd_pure JIT work-in-progress in this repo, not defects.
Defect entry key:
``e2-whole-tree-scope-structurally-incompatible-with-concurrent-atdd-pure-jit-swarm``.

RCA (verified from source at HEAD of this worktree)
---------------------------------------------------
The E2 leg is ``run_contract_gate --feature-id <fid> --entering-slice <sid>``,
composed as a subprocess by
``src/des/cli/verify_slice_commit_completeness.py::_run_contract_gate``.

The offending code is ``src/des/cli/run_contract_gate.py::_mode_feature_scoped``,
the "keystone" arch block::

    arch_paths = _arch_invariant_paths(repo)   # <-- WHOLE TREE tests/build/**
    if arch_paths:
        arch = _run_arch_invariant_set(repo, arch_paths)   # <-- RUNS all of them
        ...
        if not arch.passed:
            return _feature_scope_malformed(..., "arch-invariant-failed", ...)

It runs the ENTIRE ``tests/build/**`` architecture tier on EVERY entering slice,
so any other lane's red blocks this lane.

The SIBLING leg in the same module already implements the correct C1 scoping and
is already wired: ``build_tier_exit_verdict`` + ``_resolve_build_tier_run_paths``
+ ``_light_invariant_paths``, which emit a LOUD ``BuildTierWholeTreeDeferred``
event naming ``feature-end`` and run only the scoped set;
``src/des/cli/commit_slice.py`` already opts into it via
``_slice_build_tier_paths``. The drift is ONLY in the feature-scoped E2 path.

The standard being RESTORED (not invented) -- ``nw-throughput`` SKILL.md, move 3
"Scope the box per-slice (C1)": *"The per-slice seal digests only the ENTERING
slice's regression test + light always-on invariants; the whole-tree tier defers
to feature-end. Running the whole tree per-slice is the JIT poison that forbids
pipelining."*

What this file pins (the charter oracle, not an implementation shape)
--------------------------------------------------------------------
Charter: ``docs/product/expectations/fix-e2-whole-tree-scope-blocks-unrelated-
slices/a-slice-commit-whose-own-scope-is-fully-green----its-declared-regression-
test-passes-its-at.md``.

* **T1 (RED today)** -- a slice whose own scope is clean CLEARS the E2 leg even
  while an unrelated lane's ``tests/build/**`` architecture test is failing, and
  the deferral is LOUD (``BuildTierWholeTreeDeferred`` naming
  ``deferred_to: feature-end``), never a silent narrowing. The refusal must never
  name a file the entering slice never touched.
* **T2 (negative, GREEN today)** -- the slice's OWN committed build-tier content
  still fail-closes at the ``commit_slice`` chokepoint. The fix narrows the blast
  radius of what blocks a commit; it never becomes a blanket bypass.
* **T3 / T4 (negative, GREEN today)** -- nothing is dropped: the whole-tree
  failures are still enforced at feature-end, on TWO independent axes (the
  full-suite leg the feature-end cycle actually invokes, and the whole-tree
  build-tier floor). The visibility MOVES from "blocks every slice, tree-wide,
  immediately" to "blocks that feature's own close"; it does not vanish (GDP-6).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition, in-process)
------------------------------------------------------------------------------
Every test drives a REAL production entry in-process against a synthetic repo:

* ``run_contract_gate.main(["--repo", ..., "--feature-id", ..., "--entering-slice",
  ...])`` -- the real CLI composition root of the E2 leg (the same argv
  ``verify_slice_commit_completeness._run_contract_gate`` composes);
* ``run_contract_gate.main(["--repo", ...])`` -- the real feature-end full-suite
  leg (the same argv ``feature_end_cycle_service._run_full_suite_leg`` composes);
* ``run_contract_gate.build_tier_exit_verdict(...)`` -- the real entry
  ``des commit-slice`` calls at its build-tier exit check.

NOTHING about the architecture outcome is mocked: ``_run_arch_invariant_set``
spawns its REAL ``_collect_scope_worker.py --run`` subprocess against the
synthetic tier, exactly as production spawns it. This follows the sibling
``test_build_tier_scoped_zero_is_not_applicable.py`` precedent, whose docstring
records that the OTHER sibling suite's mock of ``_run_arch_invariant_set``
(unconditionally ``collected=1, passed=True``) is EXACTLY why it could not catch
its own defect. The only faked port is the pre-launch resource window
(``resource_readings`` -- deterministic, no real ``/proc`` reads), the same
boundary both siblings already fake (Pillar 3).

LOAD-BEARING FIXTURE DETAIL -- ``norecursedirs``
------------------------------------------------
pytest's DEFAULT ``norecursedirs`` contains ``build``, so a synthetic repo that
does not override it silently drops ``tests/build/**`` from every path-less
collection -- which would make T3 (the feature-end full-suite leg) pass
VACUOUSLY, asserting a floor that never looked. The real repo overrides
``norecursedirs`` (``pyproject.toml``, no ``build`` entry) so its full-suite leg
genuinely covers the tier; the fixture below reproduces that override for the
same reason. Verified empirically during authoring: WITHOUT the override the
full-suite leg collects 1 item and reports ``passed: true``; WITH it, 2 items and
``passed: false``.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring pass.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from des.cli.run_contract_gate import build_tier_exit_verdict, main
from des.testing.output_capture import CapturingOutput


# The entering lane's own feature -- its scope is ALWAYS green in every fixture
# below. The whole point of the defect is that a fully-green own scope is still
# refused, so the own scope is never the variable.
_ENTERING_FEATURE_ID = "entering-lane"
_ENTERING_SLICE_TAG = "slice-01"

# The OTHER lane's in-flight work: a deliberate, legitimate active-RED scaffold
# living in the architecture tier, which the entering lane never opened. This is
# the method working correctly (atdd_pure JIT), NOT a defect to clear.
_OTHER_LANE_ARCH_TEST = Path("tests/build/test_arch_other_lane_active_red.py")
_OTHER_LANE_ARCH_BODY = (
    "import pytest\n\n"
    "@pytest.mark.unit\n"
    "def test_other_lane_invariant_not_implemented_yet():\n"
    '    raise AssertionError("other lane active-RED scaffold: impl missing")\n'
)

# A single fine reading (well above the 700 MiB / load1 design default) so the
# pre-launch resource window never trips a real wait.
_FINE_READING = (900, 1.0)

_ARCH_INVARIANT_FAILED = "arch-invariant-failed"


def _build_repo(root: Path) -> Path:
    """A synthetic project: a GREEN entering-lane scope + another lane's RED tier.

    Filesystem only -- no git. Neither ``_mode_feature_scoped`` nor
    ``build_tier_exit_verdict`` needs a work-tree for the surface under test
    (the full-suite leg degrades LOUD on the absent HEAD and still runs, which
    is the honest production behaviour on any non-git tree).
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'markers = ["unit", "integration", "acceptance"]\n'
        # See the module docstring: pytest's DEFAULT norecursedirs contains
        # `build`, which would silently hide tests/build/** from the
        # path-less full-suite collection and make T3 vacuous. The real repo
        # overrides it; so does this fixture, for the same reason.
        'norecursedirs = ["__pycache__", ".git", ".venv"]\n',
        encoding="utf-8",
    )

    scope = root / "tests" / "entering_lane" / "acceptance"
    scope.mkdir(parents=True, exist_ok=True)
    (scope / "entering_lane.feature").write_text(
        f"@feature-{_ENTERING_FEATURE_ID}\n"
        "Feature: the entering lane\n"
        f"  @{_ENTERING_SLICE_TAG}\n"
        "  Scenario: the entering lane's own scope is green\n"
        "    Given a precondition\n"
        "    When an action occurs\n"
        "    Then an outcome is observed\n",
        encoding="utf-8",
    )
    (scope / "test_entering_lane.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.acceptance\n"
        "def test_entering_lane_own_scope_is_green():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    other = root / _OTHER_LANE_ARCH_TEST
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text(_OTHER_LANE_ARCH_BODY, encoding="utf-8")
    return root


def _drive_in_process(argv: list[str]) -> tuple[int, str, list[dict[str, object]]]:
    """Drive the REAL ``run_contract_gate`` CLI composition root in-process.

    ``_mode_feature_scoped`` emits its verdict through ``_emit`` (bare
    ``print``), so the parent's stdout is the observable; the arch worker's own
    child output is irrelevant to the verdict and is left on the inherited fd.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = main(argv)
    stdout = buffer.getvalue()
    events: list[dict[str, object]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "event" in payload:
            events.append(payload)
    return exit_code, stdout, events


def _event_names(events: list[dict[str, object]]) -> list[object]:
    return [event.get("event") for event in events]


@pytest.fixture(scope="module")
def entering_lane_gate_run(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[int, str, list[dict[str, object]], Path]:
    """Drive the E2 leg ONCE over the shared fixture (it spawns real workers)."""
    repo = _build_repo(tmp_path_factory.mktemp("entering_lane") / "repo")
    exit_code, stdout, events = _drive_in_process(
        [
            "--repo",
            str(repo),
            "--feature-id",
            _ENTERING_FEATURE_ID,
            "--entering-slice",
            _ENTERING_SLICE_TAG,
        ]
    )
    return exit_code, stdout, events, repo


# ---------------------------------------------------------------------------
# T1 -- THE PRIMARY RED PIN. A slice whose OWN scope is fully green clears the
# E2 leg regardless of an unrelated lane's failing tests/build/** test, and the
# whole-tree deferral is LOUD (never a silent narrowing).
#
# RED TODAY for the diagnosed reason: `_mode_feature_scoped` resolves the
# WHOLE-TREE `_arch_invariant_paths(repo)` and runs every member, so the other
# lane's active-RED scaffold fails the run and the gate returns exit 2
# `FeatureScopeMalformed` reason `arch-invariant-failed`, naming a node-id in a
# file the entering slice never touched.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_a_green_slice_clears_though_another_lanes_architecture_test_is_failing(
    entering_lane_gate_run: tuple[int, str, list[dict[str, object]], Path],
) -> None:
    exit_code, stdout, events, repo = entering_lane_gate_run

    assert exit_code == 0, (
        "BUG REPRODUCED: a slice whose OWN scope is fully green must clear the "
        "feature-scoped E2 leg even while an unrelated lane's active-RED "
        f"tests/build/** scaffold ({_OTHER_LANE_ARCH_TEST}) is failing -- got "
        f"exit {exit_code}, events={_event_names(events)}. "
        "_mode_feature_scoped resolves the WHOLE-TREE _arch_invariant_paths(repo) "
        "and runs every member on EVERY entering slice, so any other lane's red "
        "blocks this lane. Fix direction (nw-throughput move 3, C1): the "
        "feature-scoped path must DEFER the whole-tree tests/build/** tier to "
        "feature-end -- the same scoping the sibling _resolve_build_tier_run_paths "
        "leg already implements and commit_slice.py already opts into."
    )

    cleared = [e for e in events if e.get("event") == "FeatureScopeCleared"]
    assert cleared, (
        "the E2 leg must surface a FeatureScopeCleared verdict for a slice whose "
        f"own scope is green -- got events={_event_names(events)}"
    )

    deferred = [e for e in events if e.get("event") == "BuildTierWholeTreeDeferred"]
    assert deferred, (
        "GDP-6, no silent-wrong: the whole-tree deferral must be LOUD -- the "
        "feature-scoped leg must emit BuildTierWholeTreeDeferred, proving the "
        "tier was DEFERRED rather than silently narrowed away. Got "
        f"events={_event_names(events)}"
    )
    assert deferred[0].get("deferred_to") == "feature-end", (
        "the deferral record must NAME where the whole-tree run moves to, so the "
        "coverage is traceable rather than merely dropped -- got "
        f"{deferred[0]}"
    )


# ---------------------------------------------------------------------------
# T1-bis (negative) -- the refusal shape that IS the defect: a rejection naming
# a file belonging to a lane the blocked maintainer has never opened, with no
# action available to them inside their own scope. Charter negative #3.
#
# RED TODAY for the diagnosed reason: the refusal's `failed_node_ids` names
# tests/build/test_arch_other_lane_active_red.py.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_the_gate_never_refuses_naming_a_file_the_entering_slice_never_touched(
    entering_lane_gate_run: tuple[int, str, list[dict[str, object]], Path],
) -> None:
    _exit_code, stdout, events, _repo = entering_lane_gate_run

    refusals = [e for e in events if e.get("event") == "FeatureScopeMalformed"]
    assert not any(e.get("reason") == _ARCH_INVARIANT_FAILED for e in refusals), (
        "a legitimate refusal must name something the maintainer can act on "
        "INSIDE THEIR OWN SCOPE (GDP-3 WHAT/WHY/HOW, where the HOW is available "
        "to them). Got an "
        f"{_ARCH_INVARIANT_FAILED!r} refusal instead: {refusals}"
    )
    assert _OTHER_LANE_ARCH_TEST.name not in stdout, (
        "THE DEFECT SHAPE: the E2 leg's verdict names "
        f"{_OTHER_LANE_ARCH_TEST}, a file belonging to a different concurrent "
        "lane that the entering slice never opened -- the blocked maintainer has "
        "no action available other than fixing somebody else's in-flight work. "
        f"Verdict stdout: {stdout.strip()[:500]!r}"
    )


# ---------------------------------------------------------------------------
# T2 (negative) -- NOT A BLANKET BYPASS. A slice whose OWN committed build-tier
# content genuinely fails is still REFUSED at the commit_slice chokepoint
# (`build_tier_exit_verdict` with the slice's own scoped paths -- the already-
# wired `_slice_build_tier_paths` route). GREEN today; must stay GREEN.
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_a_slice_breaking_its_own_build_tier_content_is_still_refused(
    tmp_path: Path,
) -> None:
    repo = _build_repo(tmp_path / "repo")
    own_failing = repo / "tests" / "build" / "test_arch_entering_lane_own.py"
    own_failing.write_text(
        "import pytest\n\n"
        "@pytest.mark.unit\n"
        "def test_entering_lane_own_architecture_invariant():\n"
        '    assert False, "the entering lane broke its OWN architecture invariant"\n',
        encoding="utf-8",
    )

    output = CapturingOutput()
    exit_code = build_tier_exit_verdict(
        repo,
        output=output,
        resource_readings=iter([_FINE_READING]),
        sleep_fn=lambda _seconds: None,
        light_invariant_paths=[own_failing],
    )
    events = [json.loads(line) for line in output.lines if line.strip()]

    assert exit_code == 1, (
        "NEVER A BLANKET BYPASS: a slice whose OWN committed tests/build/ "
        "content genuinely FAILS must still be refused (exit 1) -- the fix "
        "narrows the blast radius of what blocks a commit, it does not remove "
        f"the block. Got exit {exit_code}, events={_event_names(events)}"
    )
    refused = [e for e in events if e.get("event") == "BuildTierRefused"]
    assert refused and refused[0].get("reason") == _ARCH_INVARIANT_FAILED, (
        "expected a BuildTierRefused naming the entering lane's OWN failing "
        f"architecture test -- got events={events}"
    )
    named = json.dumps(refused[0])
    assert own_failing.name in named, (
        "the refusal must name the maintainer's OWN failing file so the HOW is "
        f"actionable inside their own scope -- got {refused[0]}"
    )
    assert _OTHER_LANE_ARCH_TEST.name not in named, (
        "a per-slice refusal must never leak the OTHER lane's file into a scope "
        f"the maintainer cannot act on -- got {refused[0]}"
    )


# ---------------------------------------------------------------------------
# T3 (negative) -- NOTHING IS DROPPED, axis 1. The feature-end full-suite leg
# (`des run-contract-gate --repo <root>`, the argv
# `feature_end_cycle_service._run_full_suite_leg` composes) still REFUSES while
# the architecture failure stands: the visibility MOVED to that feature's own
# close, it did not vanish. GREEN today; must stay GREEN.
# CONTRACT_SHAPE: unbounded-preservation (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_the_feature_end_full_suite_leg_still_refuses_while_the_failure_stands(
    tmp_path: Path,
) -> None:
    repo = _build_repo(tmp_path / "repo")

    exit_code, stdout, events = _drive_in_process(["--repo", str(repo)])

    assert exit_code != 0, (
        "the whole-tree failures must NOT be silently dropped by the per-slice "
        "deferral -- the feature-end full-suite leg must still refuse to certify "
        "a feature done while its tree carries an unresolved architecture "
        f"failure. Got exit {exit_code}, events={_event_names(events)}"
    )
    results = [e for e in events if e.get("event") == "ContractGateResult"]
    assert results, (
        "the feature-end full-suite leg must surface a ContractGateResult -- got "
        f"events={_event_names(events)} (stdout: {stdout.strip()[:400]!r})"
    )
    assert results[-1].get("passed") is False, (
        "the feature-end full-suite verdict must report passed=false while the "
        f"architecture tier is red -- got {results[-1]}. If this ever reports "
        "true, the deferral target is vacuous and the deferral became a silent "
        "drop (check the fixture's norecursedirs override -- pytest's default "
        "hides tests/build/** from a path-less collection)."
    )


# ---------------------------------------------------------------------------
# T4 (negative) -- NOTHING IS DROPPED, axis 2 (GDP-8 witness corollary: verify
# the property on a SECOND axis). The whole-tree build-tier floor still runs the
# full tier and still NAMES the failing architecture test. GREEN today; must
# stay GREEN -- this is the surface the deferral defers TO.
# CONTRACT_SHAPE: unbounded-preservation (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_the_whole_tree_build_tier_floor_still_names_the_failing_architecture_test(
    tmp_path: Path,
) -> None:
    repo = _build_repo(tmp_path / "repo")

    output = CapturingOutput()
    exit_code = build_tier_exit_verdict(
        repo,
        output=output,
        resource_readings=iter([_FINE_READING]),
        sleep_fn=lambda _seconds: None,
        full=True,
    )
    events = [json.loads(line) for line in output.lines if line.strip()]

    assert exit_code == 1, (
        "the whole-tree build-tier floor must stay byte-identical -- it is the "
        "surface the per-slice deferral defers TO, so weakening it would turn "
        f"the deferral into a silent drop. Got exit {exit_code}, "
        f"events={_event_names(events)}"
    )
    refused = [e for e in events if e.get("event") == "BuildTierRefused"]
    assert refused and refused[0].get("reason") == _ARCH_INVARIANT_FAILED, (
        f"expected BuildTierRefused reason={_ARCH_INVARIANT_FAILED!r} on the "
        f"whole-tree run -- got events={events}"
    )
    assert _OTHER_LANE_ARCH_TEST.name in json.dumps(refused[0]), (
        "the whole-tree floor must still NAME the failing architecture test -- "
        "the failure stays observable somewhere a maintainer would look, it is "
        f"never silenced. Got {refused[0]}"
    )
    assert not any(e.get("event") == "BuildTierWholeTreeDeferred" for e in events), (
        "the whole-tree run must never defer -- it IS the whole-tree run"
    )
