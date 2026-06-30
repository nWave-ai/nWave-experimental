"""Test-side composition for slice-05: PER-TEST .nwave STATE ISOLATION.

slice-05 of sustainable-test-suite (PARALLELISM RESTORATION — DESIGN Component
Decomposition row "Per-test `.nwave` state isolation harness"). Two honest driving
surfaces, both active-RED at HEAD:

  * WALKING SKELETON / NO-MASK (Mandate-13, Layer 3 subprocess): a hermetic
    `pytest -p xdist -n 2` run over a SMALL generated fixture test-set that
    deliberately writes `.nwave` state under the resolved root. The subprocess is the
    SUT — no production module is imported and called at the step boundary. WITH the
    per-test isolation harness the parallel run is `all-isolated-green`; WITHOUT it
    (harness disabled) the shared-cwd `.nwave` writes interfere across workers and a
    fixture test fails (`cross-test-interference`) — proving the isolation is
    load-bearing, not vacuously green.

  * ISOLATION-OBSERVABLE / STALE-FLOOR (Mandate-13, Layer 3 composition): the per-test
    `.nwave`-root RESOLVER entry point (`des.domain.nwave_root.resolve_nwave_root`),
    observed producing a per-test isolated `.nwave` root — two tests resolve DISTINCT
    roots, neither the shared repo `Path.cwd()`, and a stale real-repo
    `.nwave/wave-active/active.json` does not leak into an isolated test.

Active-RED at HEAD: the per-test `.nwave`-root resolver is a RED scaffold
(`resolve_nwave_root()` raises AssertionError) and the autouse per-test isolation
fixture does not exist, so:
  * the resolver-driven scenarios raise a clean AssertionError when they invoke the
    resolver (MISSING_FUNCTIONALITY — the resolver is unimplemented), and
  * the subprocess scenarios observe `cross-test-interference` where the WITH-isolation
    contract demands `all-isolated-green`, so the outcome assertion fires
    (MISSING_FUNCTIONALITY — the isolation harness is not yet wired).
Neither is an ImportError. DELIVER makes them GREEN by landing the
`DES_PROJECT_DIR`-preferring resolver + the autouse isolation fixture in
`tests/conftest.py`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.domain.nwave_root import resolve_nwave_root

from .slice_05_domain_types import IsolationVerdict, ParallelOutcome


if TYPE_CHECKING:
    from collections.abc import Sequence


# This file lives at tests/des/acceptance/sustainable-test-suite/acceptance/steps/, so
# parents[6] is the repo root (mirrors slice-03/04). The hermetic pytest subprocess
# runs with cwd=tmp_path so it never touches the real repo `.nwave`.
_REPO_ROOT = Path(__file__).resolve().parents[6]


@dataclass(frozen=True)
class ParallelRunResult:
    """The observable surface of a hermetic `pytest -n` subprocess over the fixture set."""

    exit_code: int
    stdout: str
    stderr: str

    def outcome(self) -> ParallelOutcome:
        """Classify the parallel run as all-isolated-green vs cross-test-interference.

        The classification reads the SHIPPED subprocess output discriminatingly so a
        resolver crash (HEAD scaffold) is NOT misread as either outcome:

          * `all-isolated-green` requires exit 0 over the fixture test-set — every test
            that wrote `.nwave` state passed under parallel workers (each root isolated).
          * `cross-test-interference` requires the inner suite's own sibling-leak marker
            (`shared `.nwave` root leaked sibling state`) on the failure output — a
            fixture test failed BECAUSE a sibling worker's shared-cwd `.nwave` write
            leaked across the worker boundary.

        At HEAD the resolver is a scaffold that raises before any `.nwave` write, so the
        inner failures carry NO leak marker and the exit is non-zero → neither outcome
        is met → `outcome()` raises AssertionError (MISSING_FUNCTIONALITY). Both the
        WITH-isolation and the NO-mask scenarios are therefore active-RED today: the
        harness + resolver must exist before EITHER outcome is observable.
        """
        leak_marker = "leaked sibling state across workers"
        if self.exit_code == 0:
            return ParallelOutcome.ALL_ISOLATED_GREEN
        if leak_marker in self.stdout or leak_marker in self.stderr:
            return ParallelOutcome.CROSS_TEST_INTERFERENCE
        raise AssertionError(
            "the hermetic parallel run is neither all-isolated-green (exit 0) nor a "
            "genuine cross-worker `.nwave` leak (no sibling-leak marker on output) — the "
            "per-test `.nwave`-root isolation harness + resolver are not yet implemented "
            f"(MISSING_FUNCTIONALITY); exit {self.exit_code}, stdout {self.stdout!r}"
        )


# ---------------------------------------------------------------------------
# Fixture test-set generator — a SMALL inner pytest module whose tests each write
# `.nwave` state under the RESOLVED root and assert no sibling state is present. Under
# parallel workers this is GREEN iff each test's `.nwave` root is per-test isolated.
# Test-arrangement only.
# ---------------------------------------------------------------------------

_INNER_TEST_SOURCE = textwrap.dedent(
    '''
    """Generated inner fixture test-set (slice-05). Each test writes `.nwave` state
    under the resolver-provided root and asserts NO sibling test's marker is present —
    GREEN under parallel workers iff each test's `.nwave` root is isolated."""
    import os
    from pathlib import Path

    import pytest

    from des.domain.nwave_root import resolve_nwave_root


    @pytest.mark.parametrize("marker", [f"m{i}" for i in range(8)])
    def test_each_writes_isolated_nwave_state(marker: str) -> None:
        root = resolve_nwave_root() / ".nwave" / "wave-active"
        root.mkdir(parents=True, exist_ok=True)
        mine = root / f"{marker}.json"
        mine.write_text(marker, encoding="utf-8")
        siblings = sorted(p.name for p in root.glob("*.json") if p.name != mine.name)
        assert siblings == [], (
            f"shared `.nwave` root leaked sibling state across workers: {siblings}"
        )
    '''
).strip()


class NwaveIsolationDriver:
    """Test-side driving facade over the per-test `.nwave`-root isolation harness (SUT).

    Surfaces:
      * a hermetic `pytest -n 2` subprocess over the generated fixture test-set
        (walking skeleton / no-mask), and
      * the per-test `.nwave`-root RESOLVER entry point (isolation-observable /
        stale-floor).
    """

    def __init__(self) -> None:
        self._workdir: Path | None = None
        self._harness_enabled: bool = True
        self._stale_floor_present: bool = False
        self._result: ParallelRunResult | None = None
        self._resolved_roots: list[Path] = []

    # -- arrange (Given) -----------------------------------------------------

    def given_parallel_fixture_set_with_isolation(self, tmp_path: Path) -> None:
        """A fixture test-set that writes `.nwave` state, run WITH the isolation harness.

        The walking-skeleton arrangement: the harness roots each test's `.nwave` under a
        per-test tmp dir, so the parallel run is expected all-isolated-green.
        """
        self._workdir = tmp_path
        self._harness_enabled = True
        self._scaffold_inner_suite(tmp_path, harness_enabled=True)

    def given_parallel_fixture_set_without_isolation(self, tmp_path: Path) -> None:
        """The SAME fixture test-set run WITHOUT the isolation harness (it is disabled).

        The no-mask arrangement: with the harness off, the fixture tests share the
        cwd-rooted `.nwave`, so a parallel run must surface cross-test interference —
        proving the isolation is load-bearing (the test is not vacuously green).
        """
        self._workdir = tmp_path
        self._harness_enabled = False
        self._scaffold_inner_suite(tmp_path, harness_enabled=False)

    def given_two_tests_under_the_isolation_harness(self, tmp_path: Path) -> None:
        """Two distinct per-test working dirs the resolver is asked to root `.nwave` in.

        Drives the resolver entry point twice with two different `DES_PROJECT_DIR`
        overrides — the per-test isolation observable.
        """
        self._workdir = tmp_path
        self._first_dir = tmp_path / "test_a"
        self._second_dir = tmp_path / "test_b"
        self._first_dir.mkdir(parents=True, exist_ok=True)
        self._second_dir.mkdir(parents=True, exist_ok=True)

    def given_no_per_test_override_configured(self, tmp_path: Path) -> None:
        """A test with NO `DES_PROJECT_DIR` override — the un-isolated fallback path.

        The resolver must fall back to the shared repo `Path.cwd()` root (the
        `shared-cwd-root` status that contaminates under `-n auto` when no per-test
        override is present).
        """
        self._workdir = tmp_path

    def given_a_stale_wave_floor_in_the_shared_repo(self, tmp_path: Path) -> None:
        """A stale `.nwave/wave-active/active.json` present at session start.

        The exact contamination vector from the RCA: a leftover real-repo floor must NOT
        leak into a per-test isolated root. The isolated test dir is a fresh tmp dir; the
        stale floor lives at a SEPARATE shared location and must stay invisible.
        """
        self._workdir = tmp_path
        self._stale_floor_present = True
        self._isolated_dir = tmp_path / "isolated_test"
        self._isolated_dir.mkdir(parents=True, exist_ok=True)
        self._stale_floor = tmp_path / "shared_repo" / ".nwave" / "wave-active"
        self._stale_floor.mkdir(parents=True, exist_ok=True)
        (self._stale_floor / "active.json").write_text(
            '{"wave": "design"}', encoding="utf-8"
        )

    # -- act (When) ----------------------------------------------------------

    def when_the_parallel_suite_runs(self) -> None:
        assert self._workdir is not None, "no fixture test-set was arranged"
        self._result = self._run_inner_pytest(self._workdir)

    def when_the_resolver_is_asked_for_each_tests_root(self) -> None:
        """Invoke the resolver entry point under each per-test DES_PROJECT_DIR override."""
        self._resolved_roots = [
            self._resolve_under(self._first_dir),
            self._resolve_under(self._second_dir),
        ]

    def when_the_resolver_runs_in_the_isolated_test(self) -> None:
        """Invoke the resolver in the isolated test dir while the stale floor exists."""
        self._resolved_roots = [self._resolve_under(self._isolated_dir)]

    def when_the_resolver_is_asked_with_no_override(self) -> None:
        """Invoke the resolver entry point with NO `DES_PROJECT_DIR` override set."""
        prior = os.environ.pop("DES_PROJECT_DIR", None)
        try:
            self._resolved_roots = [resolve_nwave_root()]
        finally:
            if prior is not None:
                os.environ["DES_PROJECT_DIR"] = prior

    # -- assert (Then) -------------------------------------------------------

    def then_parallel_outcome_is(self, expected: ParallelOutcome) -> None:
        result = self._require_result()
        actual = result.outcome()
        assert actual == expected, (
            f"the hermetic parallel run must be {expected.value!r}; got {actual.value!r} "
            f"(exit {result.exit_code}); the per-test `.nwave`-root isolation harness is "
            f"not yet wired (MISSING_FUNCTIONALITY). stdout {result.stdout!r}"
        )

    def then_isolation_verdict_is(self, expected: IsolationVerdict) -> None:
        roots = self._require_roots()
        if expected is IsolationVerdict.PER_TEST_ISOLATED:
            distinct = len({str(r) for r in roots}) == len(roots)
            none_shared_cwd = all(r.resolve() != _REPO_ROOT.resolve() for r in roots)
            assert distinct and none_shared_cwd, (
                "two tests must resolve DISTINCT `.nwave` roots, neither the shared repo "
                f"cwd ({_REPO_ROOT}); got {[str(r) for r in roots]} — the per-test "
                "`.nwave`-root resolver is not yet implemented (MISSING_FUNCTIONALITY)"
            )
        else:
            shared = any(r.resolve() == _REPO_ROOT.resolve() for r in roots)
            assert shared, f"expected a shared-cwd root; got {[str(r) for r in roots]}"

    def then_the_stale_floor_does_not_leak(self) -> None:
        """The isolated test's resolved root must not contain the stale floor."""
        (root,) = self._require_roots()
        leaked = (root / ".nwave" / "wave-active" / "active.json").exists()
        assert not leaked, (
            "the stale real-repo `.nwave/wave-active/active.json` leaked into the "
            f"isolated test's resolved root ({root}) — per-test `.nwave`-root isolation "
            "is not yet implemented (MISSING_FUNCTIONALITY)"
        )

    # -- internals -----------------------------------------------------------

    def _resolve_under(self, project_dir: Path) -> Path:
        """Drive the resolver entry point with DES_PROJECT_DIR set to a per-test dir.

        Active-RED: `resolve_nwave_root()` is a scaffold raising AssertionError, so this
        fires (MISSING_FUNCTIONALITY) — the right reason, not an ImportError.
        """
        prior = os.environ.get("DES_PROJECT_DIR")
        os.environ["DES_PROJECT_DIR"] = str(project_dir)
        try:
            return resolve_nwave_root()
        finally:
            if prior is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prior

    def _scaffold_inner_suite(self, tmp_path: Path, *, harness_enabled: bool) -> None:
        (tmp_path / "test_inner_isolation.py").write_text(
            _INNER_TEST_SOURCE, encoding="utf-8"
        )
        conftest = self._inner_conftest(harness_enabled=harness_enabled)
        (tmp_path / "conftest.py").write_text(conftest, encoding="utf-8")

    def _inner_conftest(self, *, harness_enabled: bool) -> str:
        if harness_enabled:
            # The inner suite relies on the per-test isolation harness wired in the REAL
            # tests/conftest.py (autouse per-test DES_PROJECT_DIR). The inner conftest
            # re-declares it so the hermetic run is self-contained; at HEAD the resolver
            # is unimplemented so even WITH this declaration the run is RED for the right
            # reason (the resolver raises) — DELIVER makes both the resolver and the real
            # conftest fixture real.
            return textwrap.dedent(
                """
                import os
                import pytest


                @pytest.fixture(autouse=True)
                def _isolate_nwave_root(tmp_path, monkeypatch):
                    monkeypatch.setenv("DES_PROJECT_DIR", str(tmp_path))
                    yield
                """
            ).strip()
        # No harness: tests share the cwd-rooted `.nwave` → interference under -n.
        return ""

    def _run_inner_pytest(self, workdir: Path) -> ParallelRunResult:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "xdist",
                "-n",
                "2",
                "-p",
                "no:cacheprovider",
                "-q",
                str(workdir),
            ],
            capture_output=True,
            text=True,
            cwd=str(workdir),
        )
        return ParallelRunResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def _require_result(self) -> ParallelRunResult:
        assert self._result is not None, "the parallel suite was not run"
        return self._result

    def _require_roots(self) -> Sequence[Path]:
        assert self._resolved_roots, "the resolver was not invoked"
        return self._resolved_roots
