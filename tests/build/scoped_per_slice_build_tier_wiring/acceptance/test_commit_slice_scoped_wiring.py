"""Acceptance tests -- activate the scoped per-slice BuildTier (DISTILL, slice-01).

Feature-delta: docs/feature/scoped-per-slice-build-tier-wiring/feature-delta.md
  Wave: DESIGN / [REF] Architecture & Contract + [REF] Slice Plan (slice-01)

C1 slice-01 (scoped-per-slice-build-tier, 6cffadeed) SHIPPED the CAPABILITY on
``build_tier_exit_verdict`` (keyword-only ``regression_test_file`` /
``light_invariant_paths`` / ``full``, scoped selection + a LOUD
``BuildTierWholeTreeDeferred`` event -- see
``tests/build/scoped_per_slice_build_tier/acceptance/test_scoped_build_tier.py``).
That capability is INERT: the single caller, ``des commit-slice``
(``src/des/cli/commit_slice.py``, the Step build-tier
``build_tier_exit_verdict(repo)`` call, ~line 932), still calls it ZERO-KWARG
-- whole-tree, byte-for-byte the pre-C1 behaviour. Per-slice seals therefore
still run the whole ``tests/build/**`` tree (~2 min observed, 2026-07-10).

This slice WIRES the caller: when the entering slice declares
``--regression-test-file``, ``commit_slice.py`` forwards it (resolved
repo-relative, mirroring ``verify_slice_commit_completeness.py``'s
``test_path = repo / regression_test_file`` convention, line 506) as
``regression_test_file=`` into ``build_tier_exit_verdict``, plus the light
always-on invariant set as ``light_invariant_paths=`` -- turning the per-slice
seal from whole-tree to SCOPED. When NO ``--regression-test-file`` is
declared, the call stays zero-kwarg (whole tree) -- the safety-net default is
preserved, never silently narrowed.

DESIGN PIN this AT establishes (necessary -- no prior slice fixed the CALLER
side; C1 slice-01 fixed only the CALLEE signature): the ``commit_slice.py``
build-tier Step (~line 932) branches on ``args.regression_test_file``:

    regression_test_file = (
        repo / args.regression_test_file if args.regression_test_file else None
    )
    if build_tier_exit_verdict(
        repo, regression_test_file=regression_test_file
    ) != 0:
        return 1

Active-RED scaffolding: this module imports ONLY STABLE, ALREADY-PRESENT names
(``commit_slice.main``, the ``run_contract_gate`` module, ``_ArchVerdict``,
``_ResourceWindowResult`` -- all shipped by C1 slice-01 / C3) -- nothing
absent is imported, collection is clean (never BROKEN). The missing
functionality (the CALL SITE forwarding) is reached at RUNTIME: T1/T2 drive
the real ``des commit-slice`` composition root end-to-end and assert WHAT
``build_tier_exit_verdict`` was actually invoked with -- at HEAD it is called
zero-kwarg regardless of a declared ``--regression-test-file``, so the scoped
selection / deferral-event assertions fail with a plain semantic
``AssertionError`` (no signature to raise ``TypeError`` -- the callee already
accepts the kwargs; only the CALLER is wrong). RED for the right reason,
verified empirically before authoring.

Driving surface (Mandate-13 driving-port-only): every test drives the REAL
composition-root entry ``commit_slice.main(argv)`` IN-PROCESS end-to-end (a
direct call, no interpreter fork -- Layer 3 composition) over a REAL git
work-tree (real-IO, Pillar 3). The only faked surfaces are the
external/non-deterministic ports: the heavy arch-invariant runner
(``run_contract_gate._run_arch_invariant_set``, monkeypatched to a recording
spy -- the AT observes exactly what ``build_tier_exit_verdict`` selected,
without ever spawning the real 646-test tree) and the pre-launch resource
window (``run_contract_gate._await_resource_window``, monkeypatched to an
always-open stub -- deterministic, no real ``/proc`` reads or sleeps on the
shared box; that machinery is C3's own concern, already ATed there).

CONTRACT_SHAPE: bounded-change for every scenario -- ``des commit-slice``
maps a bounded set of inputs (``--regression-test-file`` present/absent) to
one of a closed set of ``build_tier_exit_verdict`` call shapes (scoped vs
whole-tree), plus the bounded side-effect of the LOUD deferral event.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.cli import run_contract_gate
from des.cli.commit_slice import main as commit_slice_main
from des.cli.record_examine_verdict import main as record_examine_verdict_main
from des.cli.run_contract_gate import _ArchVerdict, _ResourceWindowResult


_FEATURE_ID = "scoped-per-slice-build-tier-wiring"

# Head-tagged (# @feature-{id} / # @slice-01) so this file doubles as BOTH the
# build-tier's scoped regression target AND the E1/E2 pre-flight's real
# pytest-regression evidence (fold-in reorder, ADR-DES-001 slice-01) --
# `des commit-slice`'s Step-1.5 pre-flight now genuinely refuses a commit with
# ZERO observed AT evidence (no `.feature` file, no `--at-kind
# pytest-regression`, no examine PASS); mirrors
# ``tests/bugs/des/test_commit_slice_gates_run_before_commit.py``'s
# ``_write_regression_test`` convention.
_PASSING_TEST = (
    f"# @feature-{_FEATURE_ID}\n# @slice-01\n"
    "import pytest\npytestmark = pytest.mark.unit\n\n"
    "def test_behaviour():\n    assert True\n"
)

_MISSING_FUNCTIONALITY_HOW = (
    "Re-check with: uv run pytest "
    "tests/build/scoped_per_slice_build_tier_wiring/acceptance/"
    "test_commit_slice_scoped_wiring.py -q"
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo_with_build_tier(root: Path) -> None:
    """A real git work-tree carrying BOTH an ordinary unit-test package AND a
    ``tests/build`` arch tier with the entering slice's regression test --
    the exact layout ``_arch_invariant_paths``/``build_tier_exit_verdict``
    read as real-IO.
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
    (unit_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )

    build_dir = root / "tests" / "build"
    slice_dir = build_dir / "slice_01"
    slice_dir.mkdir(parents=True)
    (build_dir / "__init__.py").write_text("", encoding="utf-8")
    (slice_dir / "__init__.py").write_text("", encoding="utf-8")
    (slice_dir / "test_regression.py").write_text(_PASSING_TEST, encoding="utf-8")

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


def _drive_commit_slice(
    repo: Path,
    *,
    argv_extra: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> _WiringRun:
    """Drive the REAL ``des commit-slice`` composition root end-to-end.

    Fakes exactly the external/non-deterministic ports (Pillar 3): the
    arch-invariant runner (never spawns the real 646-test tree) and the
    pre-launch resource window (deterministic, no real ``/proc`` reads).
    Records every ``arch_paths`` selection the runner was asked to target --
    the observable this AT set pins.
    """
    arch_calls: list[list[Path]] = []

    def _fake_run_arch_invariant_set(
        repo_arg: Path, arch_paths: list[Path]
    ) -> _ArchVerdict:
        arch_calls.append(list(arch_paths))
        return _ArchVerdict(collected=1, passed=True, failed_node_ids=())

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


# ---------------------------------------------------------------------------
# T1 -- a commit-slice with a declared --regression-test-file drives
# build_tier_exit_verdict with the SCOPED kwargs (regression_test_file=<that
# file>), NOT zero-kwarg (= whole tree). RED today (commit_slice.py calls
# build_tier_exit_verdict(repo) unconditionally).
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_commit_slice_drives_scoped_build_tier_with_the_declared_regression_test_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outcome anchor: feature-delta Summary ("the per-slice commit-slice
    BuildTier call passes regression_test_file=<the slice's
    --regression-test-file>... so a per-slice seal is SCOPED").
    """
    repo = tmp_path / "repo"
    _init_repo_with_build_tier(repo)
    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    run = _drive_commit_slice(
        repo,
        argv_extra=[
            "--message",
            "feat(slice): scope the per-slice build tier\n\nSlice-Id: slice-01",
            "--regression-test-file",
            "tests/build/slice_01/test_regression.py",
            "--at-kind",
            "pytest-regression",
        ],
        monkeypatch=monkeypatch,
        capsys=capsys,
    )

    assert run.arch_paths_calls, (
        "the build-tier arch-invariant runner must be invoked exactly once "
        f"by des commit-slice -- got 0 calls, events={run.events}"
    )
    selected = {Path(p) for p in run.arch_paths_calls[-1]}
    expected = {repo / "tests" / "build" / "slice_01" / "test_regression.py"}
    whole_tree = repo / "tests" / "build"
    assert selected == expected, (
        "MISSING_FUNCTIONALITY: des commit-slice's build-tier call "
        "(commit_slice.py's build_tier_exit_verdict(repo) call, ~line 932) "
        "must forward the entering slice's --regression-test-file as "
        "build_tier_exit_verdict(repo, regression_test_file=repo / "
        "args.regression_test_file) so the per-slice seal SCOPES to it -- "
        f"expected {expected}, got {selected}. Today it calls "
        f"build_tier_exit_verdict(repo) zero-kwarg, so the whole {whole_tree} "
        f"tree is selected instead of the declared regression file. "
        f"{_MISSING_FUNCTIONALITY_HOW}"
    )
    assert whole_tree not in selected, (
        f"a declared --regression-test-file must never fall back to selecting "
        f"the bare whole-tree {whole_tree} directory -- got {selected}"
    )
    assert run.exit_code == 0, f"expected exit 0 -- got {run.exit_code}"


# ---------------------------------------------------------------------------
# T2 -- the per-slice seal LOUDLY emits BuildTierWholeTreeDeferred (naming
# feature-end) -- proof the SCOPED path actually ran, not the whole-tree
# default. RED today (zero-kwarg call never requests scope, so C1's deferral
# event is never emitted on a real commit-slice seal).
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_commit_slice_scoped_seal_emits_whole_tree_deferred_event_naming_feature_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outcome anchor: feature-delta Architecture & Contract ("The LOUD
    deferral event (C1 slice-01) now fires on real seals.").
    """
    repo = tmp_path / "repo"
    _init_repo_with_build_tier(repo)
    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 3 + 3 == 6\n", encoding="utf-8"
    )

    run = _drive_commit_slice(
        repo,
        argv_extra=[
            "--message",
            "feat(slice): scope the per-slice build tier\n\nSlice-Id: slice-01",
            "--regression-test-file",
            "tests/build/slice_01/test_regression.py",
            "--at-kind",
            "pytest-regression",
        ],
        monkeypatch=monkeypatch,
        capsys=capsys,
    )

    deferral_events = [
        event
        for event in run.events
        if event.get("event") == "BuildTierWholeTreeDeferred"
    ]
    assert deferral_events, (
        "MISSING_FUNCTIONALITY: a real des commit-slice seal with a declared "
        "--regression-test-file must LOUDLY emit BuildTierWholeTreeDeferred "
        "(naming feature-end) -- proof the SCOPED build-tier path actually "
        f"ran instead of the whole-tree default. Got events={run.event_names()}. "
        f"{_MISSING_FUNCTIONALITY_HOW}"
    )
    assert deferral_events[0].get("deferred_to") == "feature-end", (
        "the deferral record must name feature-end as where the whole-tree "
        f"run moves to -- got {deferral_events[0]}"
    )
    assert run.exit_code == 0, f"expected exit 0 -- got {run.exit_code}"


# ---------------------------------------------------------------------------
# T3 (negative_at) -- Design B (design owner LOCKED 2026-07-17, supersedes
# this test's original "preserve whole-tree" invariant -- see
# tests/bugs/des/test_gherkin_commit_slice_defers_whole_tree_build_tier.py
# for the RCA + full Design B rationale): a commit-slice with NO declared
# --regression-test-file has a legitimately EMPTY per-slice arch scope (a
# Gherkin slice owns no arch test of its own). That empty scope must resolve
# to a no-op BuildTierNotApplicable AND LOUDLY emit BuildTierWholeTreeDeferred
# naming feature-end -- it must NEVER select/execute the whole-tree
# build_tier_exit_verdict(repo) call per-slice. The whole-tree floor is the
# feature-end/--full safety net (T-full-mode in the sibling RCA file pins
# that leg unchanged), not a per-slice cost every Gherkin seal pays. RED
# until the crafter wires commit_slice.py to opt the no-regression-test-file
# path into the SCOPED tier too (currently it still calls
# build_tier_exit_verdict(repo) zero-kwarg -> whole tree).
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_commit_slice_without_regression_test_file_defers_whole_tree_build_tier_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outcome anchor (Design B, supersedes the pre-2026-07-17 anchor): a
    commit-slice seal with NO --regression-test-file has a legitimately
    EMPTY per-slice arch scope -- it must resolve to a no-op
    ``BuildTierNotApplicable`` and LOUDLY emit ``BuildTierWholeTreeDeferred``
    naming feature-end, never execute the whole-tree
    ``build_tier_exit_verdict(repo)`` call per-slice. The whole-tree floor
    moves to feature-end (``--full``) -- deferred, never lost.

    This slice (slice-02) deliberately declares NO --regression-test-file --
    that absence IS the invariant under test (an empty per-slice scope must
    defer, never silently widen to whole-tree). So the E1/E2 pre-flight
    evidence this slice needs cannot come from the pytest-regression route
    (which itself REQUIRES --regression-test-file) -- it comes from the
    examine-verdict carve-out instead (a real, distinct evidence source;
    ADR-DES-001 addendum Rule 1): a charter + a fresh matching-seal PASS
    ``ExamineVerdict`` clears the otherwise-vacuous ``zero-collected`` E2 leg
    for slice-02, mirroring
    ``tests/des/integration/test_commit_slice_examine_gate.py``'s
    ``_write_charter``/``_record_examine_verdict`` convention.
    """
    repo = tmp_path / "repo"
    _init_repo_with_build_tier(repo)
    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )
    charter_dir = repo / "docs" / "product" / "expectations" / _FEATURE_ID
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_file = charter_dir / "slice-02.md"
    charter_file.write_text(
        "# Charter\n\nWalk the deferred-to-feature-end build-tier seal.\n",
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
            "slice-02",
            "--charter",
            charter_relpath,
            "--verdict",
            "PASS",
            "--observations",
            "observed during slice-02 walkthrough",
            "--examiner",
            "nw-user-examiner",
        ]
    )
    capsys.readouterr()  # drain -- the producer's own JSON is not under test here
    assert examine_exit_code == 0, (
        "fixture precondition: recording the examine PASS verdict must "
        f"itself succeed -- got exit {examine_exit_code}"
    )

    run = _drive_commit_slice(
        repo,
        argv_extra=[
            "--message",
            "feat(slice): no declared regression file\n\nSlice-Id: slice-02",
        ],
        monkeypatch=monkeypatch,
        capsys=capsys,
    )

    assert run.exit_code == 0, (
        "des commit-slice with NO --regression-test-file must still succeed "
        f"(no crash) -- got exit {run.exit_code}, events={run.events}"
    )
    whole_tree = repo / "tests" / "build"
    calls_as_sets = [{Path(p) for p in call} for call in run.arch_paths_calls]
    for selected in calls_as_sets:
        assert selected == set(), (
            "MISSING_FUNCTIONALITY (Design B): a commit-slice with NO "
            "declared --regression-test-file has a legitimately EMPTY "
            "per-slice arch scope -- it must resolve to a no-op "
            "BuildTierNotApplicable, never select/execute the whole-tree "
            f"build_tier_exit_verdict(repo) call -- expected an empty "
            f"selection (or no call at all), got selected={selected} "
            f"(the whole {whole_tree} tree). "
            f"{_MISSING_FUNCTIONALITY_HOW}"
        )

    not_applicable_events = [
        event for event in run.events if event.get("event") == "BuildTierNotApplicable"
    ]
    assert not_applicable_events, (
        "MISSING_FUNCTIONALITY (Design B): a commit-slice with NO declared "
        "--regression-test-file must LOUDLY emit BuildTierNotApplicable (a "
        "no-op) for its empty per-slice arch scope -- proof the empty scope "
        "was special-cased explicitly instead of executing the whole-tree "
        f"tier per-slice. Got events={run.event_names()}. "
        f"{_MISSING_FUNCTIONALITY_HOW}"
    )

    deferral_events = [
        event
        for event in run.events
        if event.get("event") == "BuildTierWholeTreeDeferred"
    ]
    assert deferral_events, (
        "MISSING_FUNCTIONALITY (Design B): a commit-slice with NO declared "
        "--regression-test-file must LOUDLY emit BuildTierWholeTreeDeferred "
        "naming feature-end -- proof the whole-tree tier was deferred, not "
        f"lost. Got events={run.event_names()}. {_MISSING_FUNCTIONALITY_HOW}"
    )
    assert deferral_events[0].get("deferred_to") == "feature-end", (
        "the deferral record must name feature-end as where the whole-tree "
        f"run moves to -- got {deferral_events[0]}"
    )
