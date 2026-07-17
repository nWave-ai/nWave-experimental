"""Regression: a SCOPED (per-slice) build-tier run that legitimately collects
zero runnable node-ids is falsely refused as if the whole arch tier were
vacuous.

RCA: docs/analysis/root-cause-analysis-build-tier-arch-scope-zero-collect.md

``build_tier_exit_verdict`` (``src/des/cli/run_contract_gate.py:1257``) treats
``arch.collected == 0`` as ``BuildTierRefused reason=arch-scope-zero-collected``
UNCONDITIONALLY -- a sound floor for the WHOLE-TREE call shape (``full=True`` /
unscoped), where zero collected genuinely means the entire ``tests/build``
architecture tier vanished. But the Design B per-slice SCOPING fix
(``_slice_build_tier_paths``, ``src/des/cli/commit_slice.py:925-944``) hands
this SAME check a narrow, file-granular scope -- the entering slice's own 1-N
staged ``tests/build/``-prefixed paths -- and at that granularity, zero
collected is the ORDINARY, expected outcome whenever those specific paths are:

* Branch A -- a staged path that no longer exists on disk (a deletion, or the
  delete-half of an unflagged rename): the real worker's ``pytest.main`` exits
  4 (usage error, "file or directory not found").
* Branch B -- a staged path that EXISTS but carries zero collectible pytest
  items in isolation (an ``__init__.py``, a fixture, a ``conftest.py``): the
  real worker exits 5 ("no tests collected" -- a legitimate, non-failing
  pytest outcome).

Both branches converge on ``arch.collected == 0`` and are refused identically
by the SAME check the WHOLE-TREE vacancy floor uses -- misclassifying "this
slice's own build-tier content is non-test-bearing/deleted" as "the entire
arch tier is gutted".

Fix direction (RCA §Solutions, Permanent fix P1): key the ``arch.collected ==
0`` verdict off SCOPE KIND. For the SCOPED case (non-``full``, non-empty
``run_paths``), a zero-collected outcome degrades to the SAME honest
``BuildTierNotApplicable`` the already-shipped empty-scope branch two lines
above uses. The WHOLE-TREE (``full=True`` / unscoped) ``arch-scope-zero-
collected`` refusal MUST stay byte-identical (GDP-6: a genuinely vacuous
whole-tree run must still refuse).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): every
test below drives ``build_tier_exit_verdict`` directly -- the REAL production
entry ``des commit-slice`` calls at its build-tier exit check
(``commit_slice.py:1610-1614``) -- in-process, with a real ``tests/build``
fixture ON DISK and the REAL ``_run_arch_invariant_set`` worker (a genuine
``subprocess.run`` spawn of ``_collect_scope_worker.py --run``, exactly as
production spawns it). NOTHING about the collected-count outcome is mocked --
the whole point of this regression (per the RCA's WHY-4 finding) is that the
existing sibling suite's mock of ``_run_arch_invariant_set`` (unconditionally
``collected=1, passed=True``) is EXACTLY why it could not catch this defect.
The only faked port is the pre-launch resource window (``resource_readings``
kwarg -- deterministic, no real ``/proc`` reads), the SAME boundary the
sibling suite already fakes (Pillar 3: the external/non-deterministic port,
never the observable under test).

THIS FILE IS TEST-ONLY. No production code is touched by this authoring pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.run_contract_gate import build_tier_exit_verdict
from des.testing.output_capture import CapturingOutput


# A single fine reading (well above the 700 MiB / load1 design default) so the
# pre-launch resource window never trips a real wait in any test below.
_FINE_READING = (900, 1.0)

_MARKED_PASSING_TEST = (
    "import pytest\n\npytestmark = pytest.mark.unit\n\n\n"
    "def test_marked_passing():\n    assert True\n"
)

_MARKED_FAILING_TEST = (
    "import pytest\n\npytestmark = pytest.mark.unit\n\n\n"
    "def test_marked_failing():\n"
    '    assert False, "genuine arch-invariant violation"\n'
)


def _build_repo_with_build_tier(root: Path) -> Path:
    """A real (no-git-required) project carrying a ``tests/build`` arch tier.

    ``build_tier_exit_verdict`` / ``_arch_invariant_paths`` only READ the
    filesystem (``(repo / "tests" / "build").is_dir()``) and spawn a real
    pytest subprocess rooted at ``repo`` -- no git plumbing is exercised by
    the function under test, so this fixture stays a plain directory tree
    (faster than the sibling suite's full git init, and equally real-IO for
    the surface actually under test).
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    build_dir = root / "tests" / "build"
    build_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    return root


def _drive(
    repo: Path,
    *,
    regression_test_file: Path | None = None,
    light_invariant_paths: list[Path] | None,
    full: bool = False,
) -> tuple[int, list[dict[str, object]]]:
    """Drive the REAL ``build_tier_exit_verdict`` composition root in-process."""
    output = CapturingOutput()
    exit_code = build_tier_exit_verdict(
        repo,
        output=output,
        resource_readings=iter([_FINE_READING]),
        sleep_fn=lambda _seconds: None,
        regression_test_file=regression_test_file,
        light_invariant_paths=light_invariant_paths,
        full=full,
    )
    events = [json.loads(line) for line in output.lines if line.strip()]
    return exit_code, events


def _event_names(events: list[dict[str, object]]) -> list[object]:
    return [event.get("event") for event in events]


# ---------------------------------------------------------------------------
# T1 (POSITIVE, Branch B) -- a slice staging an EXISTING non-test-bearing
# tests/build/ file (an __init__.py) as its ONLY light-invariant scope must
# resolve to BuildTierNotApplicable, never BuildTierRefused.
#
# RED TODAY for the right reason: the real worker collects the __init__.py in
# isolation, pytest exits 5 ("no tests collected"), collected_count=0 ->
# arch.collected == 0 fires BEFORE the scope-kind is considered ->
# BuildTierRefused reason=arch-scope-zero-collected.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_scoped_existing_non_test_file_is_not_applicable_not_refused(
    tmp_path: Path,
) -> None:
    repo = _build_repo_with_build_tier(tmp_path / "repo")
    non_test_file = repo / "tests" / "build" / "__init__.py"
    non_test_file.write_text("", encoding="utf-8")

    exit_code, events = _drive(repo, light_invariant_paths=[non_test_file])

    assert exit_code == 0, (
        "BUG REPRODUCED: a slice whose only staged tests/build/ content is a "
        "non-test-bearing existing file (e.g. __init__.py) must let the "
        f"commit PROCEED (honest N/A) -- got exit {exit_code}, "
        f"events={_event_names(events)}. The real worker collects zero items "
        "from this file in isolation (pytest exit 5), and today's "
        "arch.collected == 0 check refuses unconditionally regardless of "
        "scope kind."
    )
    assert any(event.get("event") == "BuildTierNotApplicable" for event in events), (
        "expected a LOUD BuildTierNotApplicable (honest N/A) for a scoped run "
        f"whose only content is non-test-bearing -- got events={events}"
    )
    assert not any(event.get("event") == "BuildTierRefused" for event in events), (
        "a non-test-bearing scoped file must never surface as "
        f"BuildTierRefused -- got events={events}"
    )


# ---------------------------------------------------------------------------
# T2 (POSITIVE, Branch A) -- a slice staging a tests/build/ path that no
# longer exists on disk (a deletion / the delete-half of an unflagged rename)
# must resolve to BuildTierNotApplicable, never BuildTierRefused.
#
# RED TODAY for the right reason: the real worker is handed a path argument
# that does not exist; pytest exits 4 (usage error), collected_count=0 ->
# same unconditional arch.collected == 0 -> BuildTierRefused.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_scoped_deleted_path_is_not_applicable_not_refused(tmp_path: Path) -> None:
    repo = _build_repo_with_build_tier(tmp_path / "repo")
    deleted_path = repo / "tests" / "build" / "test_deleted_or_renamed.py"
    # Deliberately never written -- simulates a staged deletion/rename-away:
    # _slice_build_tier_paths (commit_slice.py) has no existence check, so a
    # git-diff-reported deleted path reaches this call unchanged.
    assert not deleted_path.exists()

    exit_code, events = _drive(repo, light_invariant_paths=[deleted_path])

    assert exit_code == 0, (
        "BUG REPRODUCED: a slice whose only staged tests/build/ path was "
        "deleted/renamed away must let the commit PROCEED (honest N/A) -- "
        f"got exit {exit_code}, events={_event_names(events)}. The real "
        "worker's pytest.main exits 4 (usage error: file or directory not "
        "found) against a non-existent path, and today's arch.collected == 0 "
        "check refuses unconditionally regardless of WHY collection was zero."
    )
    assert any(event.get("event") == "BuildTierNotApplicable" for event in events), (
        "expected a LOUD BuildTierNotApplicable (honest N/A) for a scoped run "
        f"whose only staged path no longer exists -- got events={events}"
    )
    assert not any(event.get("event") == "BuildTierRefused" for event in events), (
        f"a deleted/renamed scoped path must never surface as "
        f"BuildTierRefused -- got events={events}"
    )


# ---------------------------------------------------------------------------
# T3 (POSITIVE, no arch path staged at all) -- a slice that stages NOTHING
# under tests/build/ resolves its light-invariant scope to an empty list
# (mirroring commit_slice.py's real light_invariant_paths=[] call when
# regression_test_file is None and _slice_build_tier_paths(repo) finds
# nothing). Empirically verified below: the ALREADY-SHIPPED empty-run_paths
# branch (run_contract_gate.py:1140-1167, added alongside Design B) special-
# cases this BEFORE _run_arch_invariant_set is ever invoked -- so this
# scenario is a GREEN invariant guard today, not a new RED. Kept here (a)
# because the defect report enumerates it as one of the three
# collected==0-producing shapes and (b) as a regression pin: the fix for T1/T2
# must not perturb this already-correct branch.
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_scoped_no_build_tier_path_staged_is_not_applicable(tmp_path: Path) -> None:
    repo = _build_repo_with_build_tier(tmp_path / "repo")

    exit_code, events = _drive(repo, light_invariant_paths=[])

    assert exit_code == 0, (
        f"a slice staging no tests/build/ path at all must PROCEED -- got "
        f"exit {exit_code}, events={_event_names(events)}"
    )
    assert any(event.get("event") == "BuildTierNotApplicable" for event in events), (
        f"expected BuildTierNotApplicable for a genuinely-empty per-slice "
        f"scope -- got events={events}"
    )
    assert not any(event.get("event") == "BuildTierRefused" for event in events), (
        f"an empty per-slice scope must never surface as BuildTierRefused -- "
        f"got events={events}"
    )


# ---------------------------------------------------------------------------
# T4 (NEGATIVE, fail-closed) -- a slice whose own staged tests/build/ test
# ACTUALLY FAILS must still be refused. The N/A relaxation must never swallow
# a real, in-scope arch-test failure. Already GREEN today (collected=1 != 0,
# so the zero-collected branch never fires) -- pinned as an invariant guard
# the fix must not perturb.
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_scoped_genuinely_failing_test_still_refused(tmp_path: Path) -> None:
    repo = _build_repo_with_build_tier(tmp_path / "repo")
    failing_file = repo / "tests" / "build" / "test_genuinely_failing.py"
    failing_file.write_text(_MARKED_FAILING_TEST, encoding="utf-8")

    exit_code, events = _drive(repo, light_invariant_paths=[failing_file])

    assert exit_code == 1, (
        "NEVER-SWALLOW: a slice whose own staged tests/build/ test genuinely "
        f"FAILS must still be REFUSED (exit 1) -- got exit {exit_code}, "
        f"events={_event_names(events)}. The N/A relaxation for zero-"
        "collected scopes must not extend to a non-zero collected, failing "
        "run."
    )
    refused = [e for e in events if e.get("event") == "BuildTierRefused"]
    assert refused, (
        f"expected a BuildTierRefused event naming the failing arch test -- "
        f"got events={events}"
    )
    assert refused[0].get("reason") == "arch-invariant-failed", (
        "a real in-scope test failure must be refused as "
        f"'arch-invariant-failed', not swallowed as N/A or misreported -- "
        f"got {refused[0]}"
    )
    assert not any(
        event.get("event") == "BuildTierNotApplicable" for event in events
    ), (
        f"a genuinely failing scoped test must never be reported as an "
        f"honest N/A -- got events={events}"
    )


# ---------------------------------------------------------------------------
# T5 (NEGATIVE, whole-tree intact) -- the WHOLE-TREE build-tier run
# (full=True) over a genuinely-empty tests/build/ (present but carrying zero
# collectible tests anywhere) must STILL refuse arch-scope-zero-collected.
# The N/A relaxation is SCOPED-ONLY (GDP-6: never a blanket weakening of the
# whole-tree floor). Already GREEN today -- pinned as an invariant guard the
# fix must not perturb.
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_whole_tree_vacuous_still_refused(tmp_path: Path) -> None:
    repo = _build_repo_with_build_tier(tmp_path / "repo")
    # tests/build/ exists but carries only a non-test file anywhere in the
    # tree -- a genuine whole-tree vacancy, not a narrowed per-slice scope.
    (repo / "tests" / "build" / "__init__.py").write_text("", encoding="utf-8")

    exit_code, events = _drive(repo, light_invariant_paths=None, full=True)

    assert exit_code == 1, (
        "the WHOLE-TREE arch-scope-zero-collected floor must stay "
        f"byte-identical -- got exit {exit_code}, events={_event_names(events)}"
    )
    refused = [e for e in events if e.get("event") == "BuildTierRefused"]
    assert refused and refused[0].get("reason") == "arch-scope-zero-collected", (
        f"expected BuildTierRefused reason=arch-scope-zero-collected for a "
        f"genuinely vacuous WHOLE-TREE run -- got events={events}"
    )
    assert not any(
        event.get("event") == "BuildTierNotApplicable" for event in events
    ), (
        "the scoped-only N/A relaxation must never leak into the whole-tree "
        f"call shape -- got events={events}"
    )
