"""Composition root for the at-in-process-port-default slice-04 path-genericity ATs.

Driving-port-only (Mandate-13). The path-discovery levers are driven through the
REAL gate entry ``main(argv)`` -- ``des.cli.verify_readiness_pre_dispatch.main`` --
called IN-PROCESS (a direct function call, stdout/stderr captured), NEVER a
``subprocess.run([sys.executable, ...])`` fork. This honours THIS feature's own
Locked Decision: subprocess-e2e is reserved for ``@walking_skeleton``; every other AT
drives in-process. None of the slice-04 scenarios is ``@walking_skeleton``, so none
forks.

THE DEFECT THE LEVERS MUST FIX (verified 2026-06-24, Tsunami atoms + grep on
``src/des/cli/axis_b_levers.py``):

  * ``_SRC_DES = _REPO_ROOT / "src" / "des"`` (line 53) and ``_TESTS = _REPO_ROOT /
    "tests"`` (line 54) HARDCODE nWave's OWN layout.
  * ``check_unwired_entry`` -> ``CodeFactChain(root=_SRC_DES)`` (line 114);
    ``check_integration_per_adapter`` / ``check_contract_per_port`` ->
    ``_enumerate_*`` over ``_SRC_DES`` (lines 219, 225); ``check_non_ws_spawn`` ->
    ``scan_spawn_sites(_TESTS, ...)`` (line 491); ``count_error_path_scenarios`` ->
    ``tests_dir = repo / "tests"`` (line 622).
  * The lever entry functions take NO source/tests-dir argument; no discovery
    mechanism (testpaths / .nwave / --source-dir / --tests-dir / resolve) exists.

So on a target project whose tests live in ``spec/`` and source in ``lib/``, every
lever scans the HOST nWave ``tests/`` / ``src/des`` (or finds nothing on an absent
``tests/``) -- never the target's ``spec/`` / ``lib/``.

THE FIX THE ATs PIN (DISCUSS slice-04, DESIGN DDD-4 pure resolvers): the readiness
gate RESOLVES the target's source + tests roots from (in precedence)
  1. explicit ``--source-dir`` / ``--tests-dir`` argv,
  2. the target ``pyproject.toml [tool.pytest.ini_options] testpaths``,
  3. a ``.nwave/`` layout config,
and threads the resolved roots into the levers (replacing the hardcoded globals);
when none resolves, it degrades LOUD (NOT_APPLICABLE / INDETERMINATE with a named
reason), never a false-PASS on a wrong/empty dir, never a crash.

THE ACTIVE-RED MECHANISM (DESIGN P1-P4, F1 collection-semantics premise):

  P1  This module imports ONLY the STABLE always-present entry
      ``verify_readiness_pre_dispatch.main`` at module top -- never the absent
      path-resolution seam / a not-yet-created resolver. Importing an absent name at
      module top would raise ``ImportError`` during COLLECTION => a BROKEN test.
  P2  The driving call is ``main(argv)`` -- a DIRECT in-process call. No fork.
      ``forked_interpreter`` is structurally False (this module imports no
      ``subprocess``, shells out to no ``git``).
  P3  The not-yet-built discovery is reached at RUNTIME inside the gate's own
      invariant dispatch: at HEAD the ``--source-dir`` / ``--tests-dir`` args are
      unrecognized argparse AND the levers read the host module-level globals, so the
      gate emits NO resolved-roots record (and on the sad path, no degrade-LOUD
      reason) -- a RUNTIME absence surfaced as a verdict, NOT a collection error.
  P4  Each Then asserts on the CAPTURED observable (``LayoutDiscoveryObservable`` --
      the resolved roots, the host-layout fallback flag, the degrade-LOUD reason).
      At HEAD the resolved-roots record is absent / the levers scan the host layout,
      so each assertion is a NAMED semantic ``AssertionError`` (failure-for-the-right-
      reason).

DELIVER-pinned assumptions (update HERE, not in the step bodies, if DELIVER picks a
different surface shape -- the OBSERVABLE contract is binding, the token spelling is
adjustable):

  B1 (discovery args): the readiness gate accepts ``--source-dir`` / ``--tests-dir``
     argv that thread RESOLVED roots into every axis-b lever (replacing the hardcoded
     ``_SRC_DES`` / ``_TESTS``). The gate emits a ``layout`` record on its JSON output
     naming the ``tests_root`` + ``source_root`` it actually scanned for the target.
  B2 (pyproject testpaths): absent explicit args, the gate resolves the tests root
     from the target ``pyproject.toml [tool.pytest.ini_options] testpaths`` (and the
     source root from a ``.nwave`` config or a conventional fallback).
  B3 (degrade-LOUD): when no layout resolves, the gate emits a ``layout`` record with
     ``resolution="not-resolvable"`` + a named ``reason`` (the health signal), never a
     ``"resolved"`` on a wrong/empty dir, never an unhandled exception.

The named ``layout`` record (B1..B3) is the structured observable the Then asserts on;
it is absent at HEAD, so every current-slice scenario RED-fails for the right reason.
DELIVER ships the path-discovery to turn these GREEN. Collection imports ONLY the
stable ``main`` entry (present) -- the absent resolver names appear nowhere at module
top, so the suite COLLECTS cleanly (DESIGN P1).
"""

from __future__ import annotations

import contextlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

# P1: import ONLY the stable, always-present gate entry. NEVER the absent
# path-resolution seam / a not-yet-created resolver.
from des.cli.verify_readiness_pre_dispatch import main as readiness_main

from .domain_types_slice_04 import LayoutDiscoveryObservable, LayoutResolution


@dataclass
class PathGenericityComposition:
    """Production-wired composition root driving the REAL readiness gate in-process.

    ``given_*`` materialise a real fixture PROJECT with a NON-standard layout (tests in
    ``spec/``, source in ``lib/``) -- the very layout the hardcoded globals cannot
    discover. ``drive_levers`` calls the REAL ``verify_readiness_pre_dispatch.main(argv)``
    IN-PROCESS, and ``observable()`` returns the captured layout-discovery observable a
    Then asserts on.
    """

    _project_root: Path | None = field(default=None)
    _tests_dirname: str = field(default="spec")
    _source_dirname: str = field(default="lib")
    _declare_via_args: bool = field(default=False)
    _declare_via_testpaths: bool = field(default=False)
    _unresolvable: bool = field(default=False)
    _observable: LayoutDiscoveryObservable | None = field(default=None)
    _feature_id: str = field(default="at-in-process-port-default")
    _slice_id: str = field(default="slice-04")
    _target_language: str = field(default="python")

    # --- Given: materialise a real fixture project with a non-standard layout -----

    def given_non_standard_layout(
        self, tmp_path: Path, tests_dirname: str, source_dirname: str
    ) -> None:
        """Build a real fixture project with tests in ``spec/`` + source in ``lib/``.

        A real on-disk project (real-IO) the gate can scan: a ``spec/`` tree with a
        production-covering test (so a CORRECT scan would find it) and a ``lib/`` source
        tree -- NEITHER under nWave's ``tests/`` nor ``src/des``. The hardcoded globals
        scan the host layout instead, so a correct scan of THIS project is the
        observable the fix must produce.
        """
        self._project_root = tmp_path
        self._tests_dirname = tests_dirname
        self._source_dirname = source_dirname
        tests_dir = tmp_path / tests_dirname
        source_dir = tmp_path / source_dirname
        tests_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)
        # A production-covering acceptance test in the NON-standard tests dir: a correct
        # scan of `spec/` finds it; a scan of the absent `tests/` (the defect) finds
        # nothing. `feature_id` in the path so the feature filter keeps it.
        feature_test_dir = tests_dir / "acceptance" / self._feature_id
        feature_test_dir.mkdir(parents=True, exist_ok=True)
        (feature_test_dir / "test_target_behaviour.py").write_text(
            "from target_lib import behaviour  # drives the real port\n"
            "def test_behaviour():\n    assert behaviour() is not None\n",
            encoding="utf-8",
        )
        (feature_test_dir / "target.feature").write_text(
            f"@feature-{self._feature_id}\nFeature: target behaviour\n\n"
            f"  @{self._slice_id} @error\n"
            "  Scenario: target rejects bad input\n"
            "    Given a target\n    When bad input\n    Then it is rejected\n",
            encoding="utf-8",
        )
        (source_dir / "behaviour.py").write_text(
            "def behaviour():\n    return object()\n", encoding="utf-8"
        )

    def given_declared_via_explicit_args(self) -> None:
        """The target declares its layout via explicit --source-dir / --tests-dir."""
        self._declare_via_args = True

    def given_declared_via_pyproject_testpaths(self) -> None:
        """The target declares its tests root in pyproject [tool.pytest.ini_options]."""
        self._declare_via_testpaths = True
        assert self._project_root is not None, (
            "the fixture project must be built (Given) before its pyproject is written."
        )
        (self._project_root / "pyproject.toml").write_text(
            f'[tool.pytest.ini_options]\ntestpaths = ["{self._tests_dirname}"]\n',
            encoding="utf-8",
        )

    def given_unresolvable_layout(self, tmp_path: Path) -> None:
        """Build a fixture project with NO conventional dir and NO layout config.

        No ``tests/``, no ``spec/``, no ``pyproject testpaths``, no ``.nwave`` config --
        the layout cannot be resolved. The fix must degrade LOUD (a named reason), never
        a false-PASS on a wrong/empty dir, never a crash.
        """
        self._project_root = tmp_path
        self._unresolvable = True
        # A bare project: a stray non-test file, no resolvable tests/source root.
        (tmp_path / "README.md").write_text("a project\n", encoding="utf-8")

    # --- In-process driving helper (P2/P3, no fork, no git) -----------------------

    def _drive_in_process(self, argv: list[str]) -> tuple[int, str, bool]:
        """Call the REAL ``readiness_main(argv)`` IN-PROCESS, capturing terminal output.

        A clean direct call -- NO interpreter fork (this module imports no
        ``subprocess``), NO ``git`` shell-out. An argparse rejection surfaces as a
        runtime ``SystemExit`` inside the call (caught + recorded). An UNHANDLED
        exception (a crash on an unresolvable layout -- the defect the sad path forbids)
        is caught here and reported via ``crashed``, never re-raised, so the Then can
        assert "did not crash".
        """
        assert self._project_root is not None, (
            "the fixture project must be built (Given) before the gate is driven."
        )
        out, err = io.StringIO(), io.StringIO()
        exit_code = 0
        crashed = False
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                exit_code = int(readiness_main(argv))
            except SystemExit as exc:  # argparse / explicit exit inside the call.
                exit_code = int(exc.code) if isinstance(exc.code, int) else 2
            except Exception as exc:
                crashed = True
                err.write(f"\nUNHANDLED: {type(exc).__name__}: {exc}\n")
        return exit_code, f"{out.getvalue()}\n{err.getvalue()}", crashed

    def _argv(self) -> list[str]:
        # DELIVER-updated (B1-B3 latitude): the axis-b levers + the layout-discovery are
        # opt-in via --enforce-axis-b so existing readiness callers stay byte-identical.
        argv = [
            "--feature-id",
            self._feature_id,
            "--slice-id",
            self._slice_id,
            "--repo-root",
            str(self._project_root),
            "--enforce-axis-b",
            "--target-language",
            self._target_language,
        ]
        if self._declare_via_args:
            # B1: explicit discovery args -- absent from the gate's argparse at HEAD
            # (unrecognized -> the levers fall back to the host globals -> the RED).
            argv += [
                "--source-dir",
                self._source_dirname,
                "--tests-dir",
                self._tests_dirname,
            ]
        return argv

    def _parse_layout(self, captured: str) -> dict | None:
        """Find the ``layout`` discovery record in the readiness gate's JSON output.

        Absent at HEAD (no layout-discovery surface), so this returns None -> the
        resolved-roots observable is empty / host-layout fallback is True -> the RED.
        """
        for line in captured.splitlines():
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            layout = record.get("layout")
            if isinstance(layout, dict):
                return layout
        return None

    # --- When: drive the REAL readiness gate IN-PROCESS ---------------------------

    def drive_levers(self) -> None:
        """Drive the readiness levers against the target project, capture the layout.

        At HEAD the gate emits NO ``layout`` record (no discovery surface) and the
        levers scan the host nWave layout via the hardcoded globals, so:
          * ``resolved_tests_root`` / ``resolved_source_root`` are empty,
          * ``scanned_host_layout`` is True (the defect),
          * on the sad path ``not_resolvable_reason`` is empty (a false silent pass).
        Each is the named RED. DELIVER ships the discovery to turn these GREEN.
        """
        exit_code, captured, crashed = self._drive_in_process(self._argv())
        layout = self._parse_layout(captured)
        resolved_tests = (layout or {}).get("tests_root", "") if layout else ""
        resolved_source = (layout or {}).get("source_root", "") if layout else ""
        resolution_str = (layout or {}).get("resolution", "") if layout else ""
        reason = (layout or {}).get("reason", "") if layout else ""
        # A resolved root that points INSIDE the target project (not the host repo) is
        # the observable the fix produces; absent the layout record, resolved_* is empty.
        target = str(self._project_root)
        scanned_host_layout = (
            bool(resolved_tests and target not in resolved_tests) or not layout
        )
        if self._unresolvable:
            resolution = (
                LayoutResolution.NOT_RESOLVABLE
                if resolution_str == "not-resolvable"
                else LayoutResolution.RESOLVED
            )
        else:
            resolution = (
                LayoutResolution.RESOLVED
                if resolution_str == "resolved"
                else LayoutResolution.NOT_RESOLVABLE
            )
        self._observable = LayoutDiscoveryObservable(
            resolution=resolution,
            resolved_tests_root=resolved_tests,
            resolved_source_root=resolved_source,
            scanned_host_layout=scanned_host_layout,
            not_resolvable_reason=reason,
            crashed=crashed,
            forked_interpreter=False,
            captured_output=captured,
            exit_code=exit_code,
        )

    # --- observable accessor ------------------------------------------------------

    def observable(self) -> LayoutDiscoveryObservable:
        assert self._observable is not None, (
            "the readiness levers must have been driven (When) before the layout "
            "observable is read."
        )
        return self._observable

    def diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "(no levers were driven)"
        return (
            f"(resolution={obs.resolution.value}, "
            f"resolved_tests_root={obs.resolved_tests_root!r}, "
            f"resolved_source_root={obs.resolved_source_root!r}, "
            f"scanned_host_layout={obs.scanned_host_layout}, "
            f"not_resolvable_reason={obs.not_resolvable_reason!r}, "
            f"crashed={obs.crashed}, exit_code={obs.exit_code}, "
            f"captured={obs.captured_output!r})"
        )
