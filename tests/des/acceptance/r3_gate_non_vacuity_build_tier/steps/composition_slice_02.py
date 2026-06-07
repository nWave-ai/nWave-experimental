"""Composition root for r3-gate-non-vacuity-build-tier slice-02 (Mandate-12 SSOT).

slice-02 closes the two silent-narrowing holes slice-01 left open. The driving
port and the clean-feature-scope harness are REUSED VERBATIM from slice-01
(~95% reuse): `R3GateComposition2` SUBCLASSES `R3GateComposition`, inheriting
`run_feature_scoped_gate` (the Layer-3 subprocess black-box driving port),
`GateRun`/`verdict`/`event` derivation, `_write_pyproject`, and
`_write_clean_feature_scope`. Only the slice-02-specific fixture builders
(the two VACUOUS arch-scope shapes + the PRESENT control) are NEW.

Mandate-13 (driving-port-only boundary): inherited from slice-01 -- every run
drives the REAL `des run-contract-gate --feature-id <f> --entering-slice <s>`
CLI as a Layer-3 SUBPROCESS black-box. `_arch_invariant_paths` /
`_run_arch_invariant_set` / `_mode_feature_scoped` are NEVER imported; the AT
observes ONLY the CLI's exit code + stdout JSON verdict event. Genericità
(`python_for(None)`) + env-parity (`NWAVE_FRESHNESS=""` +
`PIPENV_DONT_LOAD_ENV=1`) inherited.

TWO DISTINCT PLANES (inherited):
  * Plane (a) -- THIS AT's `.feature` lives in the real repo, tagged
    `@feature-r3-gate-non-vacuity-build-tier`.
  * Plane (b) -- the SUT targets a SYNTHETIC tmp repo with its OWN feature id
    (`arch-probe-fixture`, tagged `@feature-arch-probe-fixture`) whose feature
    scope is ALWAYS clean. slice-02 varies the VACUITY of the arch SCOPE around
    that clean feature scope.

THE TWO HOLES (verified-from-source at `run_contract_gate.py:1039-1062`):
  * Hole A (`:1041` `if arch_paths:`): when `_arch_invariant_paths(repo)`
    returns `[]` (no `tests/build/`), the whole arch block is SKIPPED and the
    gate falls through to `FeatureScopeCleared` exit 0. ABSENT shape pins it.
  * Hole B (`:1053` `if arch.collected > 0 and not arch.passed`): when the arch
    set collects ZERO (a `tests/build/` dir whose only test carries NO
    `unit`/`integration`/`acceptance` mark, so the `--run` worker's
    `-m "unit or integration or acceptance"` filter collects nothing), the
    condition is false and the gate falls through to `FeatureScopeCleared`
    exit 0. ZERO_COLLECTED shape pins it.

Python + filesystem only: no git, no external tool, hooks-only tier.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .composition_slice_01 import (  # noqa: F401 (GateRun re-export)
    GateRun,
    R3GateComposition,
)
from .domain_types_slice_02 import ArchScopeShape


@dataclass
class R3GateComposition2(R3GateComposition):
    """slice-02 composition root -- reuses the slice-01 driving port verbatim.

    Inherits `run_feature_scoped_gate`, `_write_pyproject`,
    `_write_clean_feature_scope`, and the `GateRun` observable. Adds the
    arch-SCOPE-vacuity fixture builders.
    """

    # --- fixture builder: vary the arch SCOPE vacuity around a clean feature
    #     scope (slice-02; reuses the inherited clean-feature-scope writer) ----

    def make_arch_scope_repo(self, root: Path, arch_scope: ArchScopeShape) -> Path:
        """Materialise a synthetic repo: clean feature scope + a chosen arch SCOPE.

        The feature scope is ALWAYS clean (inherited `_write_clean_feature_scope`)
        -- the whole point of slice-02 is that a clean-feature-scope slice must
        STILL be refused when its arch SCOPE is vacuous. `arch_scope` selects:

          * ABSENT          -> NO `tests/build/` dir at all (Hole A).
          * ZERO_COLLECTED  -> a `tests/build/` dir holding only an UNMARKED
                               test (Hole B).
          * PRESENT         -> a non-vacuous `tests/build/` tier whose invariant
                               holds (control -- must still CLEAR).
        """
        self._write_pyproject(root)
        self._write_clean_feature_scope(root)
        self._write_arch_scope(root, arch_scope)
        return root

    def _write_arch_scope(self, root: Path, arch_scope: ArchScopeShape) -> None:
        """Write the requested arch SCOPE shape (dispatch over the typed enum).

        Clears any pre-existing `tests/build/` FIRST so the chained Given is
        authoritative: the clean-feature-scope Given seeds a default PRESENT arch
        tier, then the shape Given overwrites it. Without the clear, a prior
        PRESENT marked test would linger and corrupt the ABSENT (Hole A) and
        ZERO_COLLECTED (Hole B) shapes.
        """
        shutil.rmtree(root / "tests" / "build", ignore_errors=True)
        if arch_scope is ArchScopeShape.ABSENT:
            self._write_no_arch_tier(root)
        elif arch_scope is ArchScopeShape.ZERO_COLLECTED:
            self._write_unmarked_arch_tier(root)
        else:
            self._write_present_arch_tier(root)

    def _write_no_arch_tier(self, root: Path) -> None:
        """Genericità clear-control: guarantee the repo has NO `tests/build/` dir.

        `_arch_invariant_paths(repo)` returns `[]` for this repo. PO-revised
        contract: the gate must CLEAR (exit 0 `FeatureScopeCleared`) -- a target
        with no arch tier carries no arch invariant to enforce (an external
        TS/Go/minimal-Python target is the motivating case). The dispatcher
        already cleared any pre-existing `tests/build/`; this guards it again
        idempotently (a no-op when none exists). The clean feature scope (under
        `tests/arch_probe_fixture/`) is untouched -- it is the only test surface.

        NOTE: current production over-refuses this with `arch-scope-empty` exit 2
        -- the ABSENT control is the RED witness for the "remove the Hole A
        branch" production change.
        """
        shutil.rmtree(root / "tests" / "build", ignore_errors=True)

    def _write_unmarked_arch_tier(self, root: Path) -> None:
        """Hole B: a `tests/build/` dir holding ONLY an UNMARKED test.

        The `--run` worker filters on `-m "unit or integration or acceptance"`
        (`_collect_scope_worker.py:54`). A test carrying NO such mark collects
        ZERO under that filter -- so `_run_arch_invariant_set` reports
        `collected == 0`. Today `if arch.collected > 0 and not arch.passed`
        falls through and the gate clears; slice-02 refuses LOUD
        (`arch-scope-zero-collected`).

        The test BODY passes (`assert True`) -- the vacuity is in the COLLECTION
        (the `-m` filter excludes it), NOT in a run-time failure. This isolates
        Hole B from the slice-01 keystone (a non-vacuous tier that FAILS at
        run-time): here the tier collects zero, so a run-time outcome never
        applies.
        """
        build = root / "tests" / "build"
        build.mkdir(parents=True, exist_ok=True)
        # NO @pytest.mark.{unit,integration,acceptance} -> excluded by the
        # worker's `-m` filter -> the arch set collects zero node-ids.
        (build / "test_arch_unmarked.py").write_text(
            "def test_arch_invariant_unmarked():\n"
            "    # No unit/integration/acceptance mark: the --run worker's\n"
            '    # `-m "unit or integration or acceptance"` filter excludes this,\n'
            "    # so the arch set collects ZERO node-ids (Hole B).\n"
            "    assert True\n"
        )

    def _write_present_arch_tier(self, root: Path) -> None:
        """Control: a non-vacuous `tests/build/` tier whose invariant HOLDS.

        A `tests/build/` test carrying the load-bearing `unit` mark (so the
        `--run` worker collects it) that runs GREEN. The gate must STILL CLEAR
        (exit 0 `FeatureScopeCleared`) -- guarding against over-refusal
        regression: slice-02 must refuse ONLY the vacuous arch scopes, never a
        genuinely non-vacuous green one.
        """
        build = root / "tests" / "build"
        build.mkdir(parents=True, exist_ok=True)
        (build / "test_arch_present.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.unit\n"
            "def test_arch_invariant_holds():\n"
            "    assert True\n"
        )
