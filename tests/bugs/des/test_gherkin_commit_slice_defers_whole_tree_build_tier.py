"""Regression: a Gherkin/atdd_pure per-slice seal (no ``--regression-test-file``)
sweeps the WHOLE ``tests/build/**`` architecture tier and trips on ANY
unrelated in-flight ``CONTRACT_SHAPE`` scaffold living there -- instead of
deferring the whole-tree run to feature-end the way a declared
``--regression-test-file`` slice already does.

RCA (given): ``src/des/cli/commit_slice.py`` (~line 1500) calls::

    regression_test_file = (
        repo / args.regression_test_file if args.regression_test_file else None
    )
    if build_tier_exit_verdict(repo, regression_test_file=regression_test_file) != 0:
        return 1

For a Gherkin slice there is no ``--regression-test-file``, so
``regression_test_file=None`` and ``light_invariant_paths`` is never passed
either. Inside ``src/des/cli/run_contract_gate.py``,
``_resolve_build_tier_run_paths`` computes ``scope_requested =
regression_test_file is not None or light_invariant_paths is not None``; with
BOTH absent, ``scope_requested`` is ``False`` and the resolver returns the
WHOLE-TREE ``_arch_invariant_paths(repo)`` -- so a Gherkin per-slice seal
sweeps every file under ``tests/build/**``, including a genuinely-failing
future-slice/unrelated ``CONTRACT_SHAPE`` scaffold that has nothing to do
with the entering slice.

**This file pins the FIXED observable OUTCOME** (Design B, LOCKED by the
design owner 2026-07-17), not the implementation shape: a Gherkin per-slice
seal (``regression_test_file=None``) has a legitimately EMPTY per-slice arch
scope (a Gherkin slice owns no arch test of its own), and that MUST (a)
select a scope that never includes the unrelated planted scaffold, (b)
resolve the empty scope to ``BuildTierNotApplicable`` (a no-op) -- it must
NEVER re-expand to the whole repo/tree, (c) LOUDLY emit
``BuildTierWholeTreeDeferred`` (naming feature-end) proving the deferral
actually happened, and (d) let the commit land (exit 0). The whole-tree floor
at feature-end (``run_contract_gate --repo . --full`` / ``full=True``) must
stay byte-for-byte unchanged -- T2/T3 below pin that as an invariant guard.

Design B note (supersedes an earlier anti-vacuity draft pinned in a prior
authoring pass on this same file): an EMPTY per-slice arch scope is NOT
itself a defect -- it is the CORRECT, expected shape for a Gherkin slice.
The defect was ever letting that empty scope reach the arch-invariant
worker at all, because ``_collect_scope_worker.py``'s own fallback
(``paths if paths else [repo]``) silently re-expands an empty ``--path``
list to the WHOLE REPO. The fix is therefore to special-case a genuinely-
empty resolved scope BEFORE handing it to ``_run_arch_invariant_set`` --
exactly the same shape ``build_tier_exit_verdict`` already uses for the "no
``tests/build`` directory" case (``_BUILD_TIER_NOT_APPLICABLE_EVENT``) --
never to force a fake non-empty path list just to dodge the worker's
fallback, and never to hand the empty list to the runner unguarded either.
T1 below fails equally against BOTH the current bug (whole-tree sweep) and a
naive "just pass an empty list straight to the runner" attempt (worker
re-expands it to the repo root).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): T1
drives the REAL ``des.cli.commit_slice.main()`` composition root
end-to-end (real git work-tree, real staging/commit, real charter +
examine-verdict evidence -- the proven ``no --regression-test-file`` E1/E2
recipe already established by
``tests/build/scoped_per_slice_build_tier_wiring/acceptance/
test_commit_slice_scoped_wiring.py``'s T3). The only faked surface is the
external/non-deterministic heavy arch-invariant runner
(``run_contract_gate._run_arch_invariant_set``, monkeypatched to a
recording spy that reports failure iff the unrelated poison scaffold would
be swept by the selected paths -- never a real 646-test pytest spawn) and
the pre-launch resource window (stubbed always-open) -- the SAME two
boundaries the sibling acceptance suites already fake, Pillar 3. T2/T3 drive
``build_tier_exit_verdict`` directly (Layer 3 composition, in-process),
mirroring ``tests/build/scoped_per_slice_build_tier/acceptance/
test_scoped_build_tier.py``'s ``_drive_gate`` pattern.

**CONFLICT DISCOVERED, RECONCILED PER DESIGN B** (design owner locked
Design B 2026-07-17 -- this note records the resolution, not an open item):

  * ``tests/build/scoped_per_slice_build_tier/acceptance/
    test_scoped_build_tier.py::
    test_default_call_with_no_new_kwargs_preserves_whole_tree_selection``
    (T5) asserts a zero-new-kwarg ``build_tier_exit_verdict(repo)`` call
    selects the whole ``tests/build`` tree. Design B does NOT touch this
    test: the FUNCTION's zero-kwarg default stays whole-tree forever -- the
    fix changes only what ``commit_slice.py`` PASSES into
    ``build_tier_exit_verdict`` (it must now pass an explicit empty scope
    for the Gherkin/no-regression-file case), never the function's own
    default. T5 stays GREEN, untouched, by design.
  * ``tests/build/scoped_per_slice_build_tier_wiring/acceptance/
    test_commit_slice_scoped_wiring.py::
    test_commit_slice_without_regression_test_file_preserves_whole_tree_
    build_tier_call`` (T3, ``@pytest.mark.negative_at``) pinned the OLD
    invariant ("no ``--regression-test-file`` -> preserve the whole-tree
    call, ``BuildTierWholeTreeDeferred`` must NOT fire"). Design B
    SUPERSEDES that invariant: this same authoring pass REWRITES T3 to pin
    the NEW invariant (no-regression-file -> deferral + no-op, never
    whole-tree per-slice) -- see that file's updated docstring/test body.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring pass.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli import run_contract_gate
from des.cli.commit_slice import main as commit_slice_main
from des.cli.record_examine_verdict import main as record_examine_verdict_main
from des.cli.run_contract_gate import (
    _ArchVerdict,
    _ResourceWindowResult,
    build_tier_exit_verdict,
)
from des.testing.output_capture import CapturingOutput


_FEATURE_ID = "fix-gherkin-commit-slice-defers-whole-tree-build-tier"
_SLICE_ID = "slice-01"

# WHY -- a single fine reading (well above the 700 MiB / load1 design
# default) so the resource window never trips a real wait in T2/T3.
_FINE_READING = (900, 1.0)

_PASSING_TEST = "def test_base():\n    assert True\n"

# The planted unrelated in-flight scaffold -- simulates a future-slice
# CONTRACT_SHAPE AT (impl missing, genuinely failing) living somewhere
# ELSE under tests/build/**, with nothing to do with the entering slice.
_POISON_SCAFFOLD_REL = Path("tests/build/unrelated_inflight_feature/test_scaffold.py")
_POISON_SCAFFOLD_BODY = (
    "import pytest\npytestmark = pytest.mark.unit\n\n"
    "def test_unrelated_future_slice_behaviour():\n"
    '    raise AssertionError("unrelated in-flight scaffold: not implemented yet")\n'
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo_with_poison_build_tier(root: Path) -> None:
    """A real git work-tree carrying a ``tests/build`` tier that contains an
    unrelated, genuinely-failing scaffold -- the exact layout
    ``_arch_invariant_paths``/``build_tier_exit_verdict`` read as real-IO.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")

    unit_dir = root / "tests" / "unit"
    unit_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (unit_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (unit_dir / "test_base.py").write_text(_PASSING_TEST, encoding="utf-8")

    build_dir = root / "tests" / "build"
    build_dir.mkdir(parents=True)
    (build_dir / "__init__.py").write_text("", encoding="utf-8")

    poison_path = root / _POISON_SCAFFOLD_REL
    poison_path.parent.mkdir(parents=True, exist_ok=True)
    (poison_path.parent / "__init__.py").write_text("", encoding="utf-8")
    poison_path.write_text(_POISON_SCAFFOLD_BODY, encoding="utf-8")

    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton with a build tier")


class _WiringRun:
    """The observable outcome of driving ``des commit-slice`` once."""

    def __init__(
        self,
        exit_code: int,
        events: list[dict[str, object]],
        arch_paths_calls: list[list[Path]],
    ) -> None:
        self.exit_code = exit_code
        self.events = events
        self.arch_paths_calls = arch_paths_calls

    def event_names(self) -> list[object]:
        return [event.get("event") for event in self.events]


def _swept(poison: Path, arch_paths: list[Path]) -> bool:
    """Whether ``poison`` would be collected by any of ``arch_paths``."""
    return any(poison == p or poison.is_relative_to(p) for p in arch_paths)


def _drive_commit_slice(
    repo: Path,
    *,
    argv_extra: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> _WiringRun:
    """Drive the REAL ``des commit-slice`` composition root end-to-end.

    Fakes exactly the external/non-deterministic ports (Pillar 3): the
    arch-invariant runner (a recording spy that fails IFF the unrelated
    poison scaffold would be swept by the paths it was asked to target --
    never a real pytest spawn) and the pre-launch resource window
    (deterministic, no real ``/proc`` reads).
    """
    arch_calls: list[list[Path]] = []
    poison = repo / _POISON_SCAFFOLD_REL

    def _fake_run_arch_invariant_set(
        repo_arg: Path, arch_paths: list[Path]
    ) -> _ArchVerdict:
        arch_calls.append(list(arch_paths))
        if _swept(poison, arch_paths):
            return _ArchVerdict(
                collected=2,
                passed=False,
                failed_node_ids=(str(poison.relative_to(repo)),),
            )
        if not arch_paths:
            # An honest simulation of a genuinely-empty selection: zero
            # collected. build_tier_exit_verdict's OWN vacuous-scope guard
            # (arch.collected == 0 -> BuildTierRefused/arch-scope-zero-
            # collected) must catch this -- a naive "pass an empty list"
            # fix must not silently pass either.
            return _ArchVerdict(collected=0, passed=True, failed_node_ids=())
        return _ArchVerdict(collected=len(arch_paths), passed=True, failed_node_ids=())

    def _fake_await_resource_window(
        *, resource_readings: object, sleep_fn: object, output: object
    ) -> _ResourceWindowResult:
        return _ResourceWindowResult(
            opened=True,
            attempts=0,
            last_reading=None,
            mem_threshold_mib=0,
            load1_threshold=0.0,
        )

    monkeypatch.setattr(
        run_contract_gate, "_run_arch_invariant_set", _fake_run_arch_invariant_set
    )
    monkeypatch.setattr(
        run_contract_gate, "_await_resource_window", _fake_await_resource_window
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            _FEATURE_ID,
            "--all",
            *argv_extra,
        ]
    )
    out = capsys.readouterr().out
    events = [
        json.loads(line) for line in out.splitlines() if line.strip().startswith("{")
    ]
    return _WiringRun(exit_code=exit_code, events=events, arch_paths_calls=arch_calls)


def _arm_examine_verdict(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The proven no-``--regression-test-file`` E1/E2 evidence recipe: a
    charter + a fresh matching PASS ``ExamineVerdict`` (mirrors
    ``test_commit_slice_scoped_wiring.py``'s
    ``test_commit_slice_without_regression_test_file_preserves_whole_tree_
    build_tier_call``). This is FIXTURE SETUP for the driving surface, never
    the observable under test.
    """
    charter_dir = repo / "docs" / "product" / "expectations" / _FEATURE_ID
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_file = charter_dir / f"{_SLICE_ID}.md"
    charter_file.write_text(
        "# Charter\n\nWalk the Gherkin per-slice build-tier deferral.\n",
        encoding="utf-8",
    )
    charter_relpath = str(charter_file.relative_to(repo))
    examine_exit_code = record_examine_verdict_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            _FEATURE_ID,
            "--slice",
            _SLICE_ID,
            "--charter",
            charter_relpath,
            "--verdict",
            "PASS",
            "--observations",
            "observed during the Gherkin per-slice walkthrough",
            "--examiner",
            "nw-user-examiner",
        ]
    )
    capsys.readouterr()  # drain -- the producer's own JSON is not under test
    assert examine_exit_code == 0, (
        "fixture precondition: recording the examine PASS verdict must "
        f"itself succeed -- got exit {examine_exit_code}"
    )


# ---------------------------------------------------------------------------
# T1 -- the primary RED pin (Design B, LOCKED). A Gherkin per-slice seal (no
# --regression-test-file) has a legitimately EMPTY per-slice arch scope. That
# empty scope must (a) never sweep an unrelated in-flight scaffold under
# tests/build/**, (b) resolve to a no-op BuildTierNotApplicable -- NEVER
# re-expand to the whole repo/tree, (c) still LOUDLY emit
# BuildTierWholeTreeDeferred naming feature-end, and (d) let the commit land.
#
# RED TODAY for the right reason: commit_slice.py calls
# build_tier_exit_verdict(repo, regression_test_file=None) zero-scope, so
# scope_requested is False and the whole tests/build tree (which contains the
# poison scaffold) is selected -- the fake arch runner reports a genuine
# failure, the commit is refused (exit 1), no BuildTierNotApplicable fires,
# and no BuildTierWholeTreeDeferred fires either.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_gherkin_slice_defers_whole_tree_and_never_sweeps_unrelated_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    _init_repo_with_poison_build_tier(repo)
    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )
    _arm_examine_verdict(repo, capsys)

    run = _drive_commit_slice(
        repo,
        argv_extra=[
            "--message",
            f"feat(slice): gherkin slice\n\nSlice-Id: {_SLICE_ID}",
        ],
        monkeypatch=monkeypatch,
        capsys=capsys,
    )

    poison = repo / _POISON_SCAFFOLD_REL
    whole_tree = repo / "tests" / "build"
    calls_as_sets = [{Path(p) for p in call} for call in run.arch_paths_calls]

    # (a) KEPT -- never sweep the unrelated planted scaffold, on ANY call the
    # arch-invariant runner was invoked with.
    for selected in calls_as_sets:
        assert not _swept(poison, list(selected)), (
            "BUG REPRODUCED: a Gherkin per-slice seal (no --regression-test-file) "
            "must never select a scope that sweeps the unrelated in-flight "
            f"scaffold {poison} -- got selected={selected}. Today "
            "commit_slice.py calls build_tier_exit_verdict(repo, "
            "regression_test_file=None) with no light_invariant_paths, so "
            "_resolve_build_tier_run_paths sees scope_requested=False and "
            f"returns the whole {whole_tree} tree, which contains the poison "
            "scaffold. Fix direction (Design B): the per-slice commit-slice "
            "path must opt into the SCOPED tier -- an empty resolved scope -- "
            "for the no-regression-test-file case too."
        )

    # (b) Design B replaces the old anti-vacuity assertion: the empty
    # per-slice scope must resolve to a no-op -- it must NEVER re-expand to
    # the whole repo/tree. Either the arch runner is never invoked at all
    # (the no-op short-circuits before the runner call, mirroring the
    # existing "no tests/build directory" -> BuildTierNotApplicable branch),
    # or -- if it IS invoked -- it must be invoked with an empty path list,
    # never the bare repo root / whole tests/build tree.
    for selected in calls_as_sets:
        assert selected == set(), (
            "ANTI-VACUITY (Design B): an empty per-slice arch scope must "
            "resolve to a no-op BuildTierNotApplicable deferral -- it must "
            "NEVER re-expand to the whole repo/tree (the "
            "'paths if paths else [repo]' worker-fallback trap), and if the "
            "arch-invariant runner is invoked at all it must be invoked with "
            f"NO paths. Got selected={selected} "
            f"(arch_paths_calls={run.arch_paths_calls}, events={run.events})"
        )

    not_applicable_events = [
        event for event in run.events if event.get("event") == "BuildTierNotApplicable"
    ]
    assert not_applicable_events, (
        "Design B: a Gherkin per-slice seal with a genuinely-empty arch scope "
        "must resolve to a LOUD BuildTierNotApplicable (a no-op) -- proof the "
        "empty scope was special-cased explicitly rather than handed to the "
        "arch-invariant runner (which would re-expand it to the whole repo "
        f"via the worker's own fallback). Got events={run.event_names()}"
    )

    deferral_events = [
        event
        for event in run.events
        if event.get("event") == "BuildTierWholeTreeDeferred"
    ]
    assert deferral_events, (
        "a Gherkin per-slice seal must LOUDLY emit BuildTierWholeTreeDeferred "
        "(naming feature-end) -- proof the deferral actually happened instead "
        f"of silently sweeping the whole tree. Got events={run.event_names()}"
    )
    assert deferral_events[0].get("deferred_to") == "feature-end", (
        "the deferral record must name feature-end as where the whole-tree "
        f"run moves to -- got {deferral_events[0]}"
    )

    assert run.exit_code == 0, (
        "the commit must land (exit 0): an unrelated in-flight scaffold "
        "elsewhere under tests/build/** must never block a Gherkin slice "
        f"that never touched it -- got exit {run.exit_code}, events={run.events}"
    )


# ---------------------------------------------------------------------------
# T2 (negative_at) -- a slice WITH a declared regression_test_file must still
# scope to exactly that file (+ light invariants), unchanged by this fix.
# Already-shipped capability (C1 scoped-per-slice-build-tier) -- GREEN today
# AND must stay GREEN after the fix.
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_regression_test_file_slice_still_scopes_to_declared_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo_with_poison_build_tier(repo)
    regression_file = repo / "tests" / "build" / "slice_01" / "test_regression.py"
    regression_file.parent.mkdir(parents=True, exist_ok=True)
    regression_file.write_text(_PASSING_TEST, encoding="utf-8")

    output = CapturingOutput()
    arch_calls: list[list[Path]] = []

    def _fake_run_arch_invariant_set(
        repo_arg: Path, arch_paths: list[Path]
    ) -> _ArchVerdict:
        arch_calls.append(list(arch_paths))
        return _ArchVerdict(collected=1, passed=True, failed_node_ids=())

    monkeypatch.setattr(
        run_contract_gate, "_run_arch_invariant_set", _fake_run_arch_invariant_set
    )

    exit_code = build_tier_exit_verdict(
        repo,
        output=output,
        resource_readings=iter([_FINE_READING]),
        sleep_fn=lambda _seconds: None,
        regression_test_file=regression_file,
        light_invariant_paths=[],
    )

    assert exit_code == 0, f"expected exit 0 -- got {exit_code}"
    assert arch_calls, "the arch-invariant runner must be invoked exactly once"
    selected = {Path(p) for p in arch_calls[-1]}
    whole_tree = repo / "tests" / "build"
    poison = repo / _POISON_SCAFFOLD_REL
    assert selected == {regression_file}, (
        "a slice with a declared regression_test_file must scope to exactly "
        f"that file -- expected {{{regression_file}}}, got {selected}"
    )
    assert whole_tree not in selected, (
        f"a declared regression_test_file scope must never widen to the bare "
        f"whole-tree {whole_tree} directory -- got {selected}"
    )
    assert poison not in selected, (
        f"the unrelated poison scaffold {poison} must never leak into a "
        f"declared regression_test_file scope -- got {selected}"
    )


# ---------------------------------------------------------------------------
# T3 (negative_at) -- full=True still forces the whole tests/build tree,
# overriding any scope -- the feature-end / --full / CI floor is UNCHANGED
# by this fix.
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_full_mode_still_sweeps_whole_tree_including_the_poison_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo_with_poison_build_tier(repo)

    output = CapturingOutput()
    arch_calls: list[list[Path]] = []

    def _fake_run_arch_invariant_set(
        repo_arg: Path, arch_paths: list[Path]
    ) -> _ArchVerdict:
        arch_calls.append(list(arch_paths))
        return _ArchVerdict(collected=3, passed=True, failed_node_ids=())

    monkeypatch.setattr(
        run_contract_gate, "_run_arch_invariant_set", _fake_run_arch_invariant_set
    )

    exit_code = build_tier_exit_verdict(
        repo,
        output=output,
        resource_readings=iter([_FINE_READING]),
        sleep_fn=lambda _seconds: None,
        full=True,
    )

    assert exit_code == 0, f"expected exit 0 -- got {exit_code}"
    assert arch_calls, "the arch-invariant runner must be invoked exactly once"
    selected = {Path(p) for p in arch_calls[-1]}
    whole_tree = repo / "tests" / "build"
    poison = repo / _POISON_SCAFFOLD_REL
    assert selected == {whole_tree}, (
        f"full=True must select the WHOLE tests/build tree -- expected "
        f"{{{whole_tree}}}, got {selected}"
    )
    assert _swept(poison, list(selected)), (
        "the feature-end/full whole-tree floor must still be capable of "
        f"catching the poison scaffold {poison} -- that coverage must never "
        f"be lost by this fix. Selected={selected}"
    )
    deferral_events = [json.loads(line) for line in output.lines]
    assert not any(
        event.get("event") == "BuildTierWholeTreeDeferred" for event in deferral_events
    ), "full=True must never defer -- it IS the whole-tree run"
