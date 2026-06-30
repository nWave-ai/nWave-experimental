"""Composition root for the f-coherence-and-attestation slice-05 ATs (TestRunnerPort).

Mandate-13 driving-port-only: each behaviour is driven through the REAL seam
slice-05 introduces -- NO production module is imported-and-called at the step
boundary for its business logic; the step bodies (in ``test_slice_05_*``)
delegate to these composition methods (Mandate-12 -- no logic in step bodies).

slice-05 (the LAST slice, JOB-028 / OB-RUNNER) lands THREE net-new
driving-surface seams (DESIGN [REF] Code-Design "Contract surface 5" +
Reuse Analysis rows for ``test_runner_port`` / ``run_contract_gate`` /
``feature_end_cycle_service``):

  (S1) the per-language ``TestRunnerPort`` RESOLUTION REGISTRY --
       ``resolve(target_root) -> RunnerAdapter | Indeterminate`` -- resolves the
       runner by FILESYSTEM lockfile inspection of the installed target
       (``pyproject.toml``->pytest · ``package.json``->vitest · ``go.mod``->go
       test · ``Cargo.toml``->cargo); unrecognized -> INDETERMINATE (degrade
       LOUD, N=0, NEVER hardcoded-pytest). CREATE_NEW at
       ``src/des/ports/test_runner_port.py`` (+ resolution in
       ``src/des/adapters/driven/runner/``). [AT-16, AT-17]
  (S2) the slice-gate AT re-scope -- the slice gate
       (``des run-contract-gate``) RUNS ONLY that slice's ATs (resolved by
       ``Slice-Id``), SUPERSEDING the hardcoded
       ``pytest -m "unit or integration or acceptance"`` over the WHOLE tree at
       every commit-slice. EXTEND ``src/des/cli/run_contract_gate.py``. [AT-18]
  (S3) the feature-end full-suite leg -- a NEW distinct clean full-suite leg
       added to ``feature_end_cycle_service.run_feature_end_cycle`` (the cycle
       today runs env-e2e + coverage-map but NO full-suite leg); + the
       removal-of-obsolete (C10: the whole-tree-every-commit-slice pytest is
       REMOVED). EXTEND ``src/des/application/feature_end_cycle_service.py``. [AT-19]

DRIVING SURFACES (Mandate-13):
  * AT-16 / AT-17 -> Layer 3 composition: the REAL ``TestRunnerPort.resolve``
    over a REAL ``tmp_path`` target carrying a real lockfile (filesystem
    inspection of the INSTALLED target, §V.A). The observable is the resolved
    runner identity (AT-16) OR the §17 INDETERMINATE degrade + its reason
    (AT-17). The resolution-registry seam is driven at the COMPOSITION ROOT (a
    real ``resolve`` callable), NOT a subprocess ``des resolve-runner`` -- the
    ``des`` dispatcher has NO resolution-registry row at HEAD, so a subprocess
    dispatch would be a collection-stage failure, not a semantic RED (mirrors
    the slice-04 ASSUMPTION).
  * AT-18 -> Layer 3 SUBPROCESS: the REAL ``des run-contract-gate`` (a real
    dispatcher ``_REGISTRY`` row) over a REAL ``tmp_path`` repo, scoped to ONE
    slice. The observable is WHICH tests the gate RAN (the slice's ATs only)
    and whether it ran the whole tree -- NEVER a line number.
  * AT-19 -> Layer 3 composition: the REAL feature-end cycle full-suite leg
    (``feature_end_cycle_service.run_feature_end_cycle``) + the
    removal-absence of the obsolete whole-tree-every-commit-slice pytest. The
    observable is the full-suite-leg presence + the obsolete-marker absence in
    the SHIPPED slice-gate surface -- the discriminating phrase
    ``"unit or integration or acceptance"`` over the WHOLE tree at every
    commit-slice (Mandate-13 prose-surface discriminating-phrase rule).

active-RED scaffold (atdd_pure -- NOT @skip): at HEAD all THREE seams are
ABSENT / unbuilt:
  * ``src/des/ports/test_runner_port.py`` does NOT exist + ``src/des/adapters/
    driven/runner/`` package does NOT exist (verified) -> the lazy import fails
    -> AT-16/17 RED for the right reason. (NB: ``src/des/cli/run_tests.py``
    (ADR-042) exists but it is a per-runner ADAPTER taking ``--runner`` and
    ABSTAINing for non-pytest; it does NOT inspect lockfiles / resolve a runner
    from the installed env -- the slice-05 RESOLUTION REGISTRY is the net-new
    seam. Flagged as a DESIGN ambiguity below.)
  * ``run_contract_gate`` has NO slice-scoped RUN mode (its ``--feature-id``
    mode is COLLECT-ONLY + arch-tier RUN, NOT a slice-AT RUN; the only RUN mode
    is the whole-tree ``_mode_run_suite``) -> AT-18 RED.
  * ``feature_end_cycle_service.run_feature_end_cycle`` runs env-e2e +
    coverage-map but NO full-suite leg; the obsolete whole-tree pytest is STILL
    present -> AT-19 RED.
Each scenario RED-fails with a NAMED semantic ``AssertionError`` naming the
missing seam, never a collection / import / setup error.

CRITICAL DELIVER CARE (the slice-gate boundary -- flagged to DELIVER, the SEAM
not a line number): the slice-AT re-allocation (S2) MUST NOT break the EXISTING
``run-contract-gate --verify-gate-scope`` digest mechanism. ``--verify-gate-scope``
is COLLECT-ONLY (it derives the ``gate_scope_digest`` from collected node-ids and
compares against a commit's ``Gate-Scope:`` trailer); the hardcoded-pytest is the
EXECUTION leg (``_mode_run_suite`` / ``_run_contract_suite``). AT-18/AT-19 drive
the EXECUTION-allocation behavior (WHICH tests RUN), DISTINCT from the gate-scope
DIGEST. DELIVER MUST re-scope the RUN allocation WITHOUT touching the collect-only
digest path -- the digest mechanism is untouched by this slice.

DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (state-here-so-DELIVER-matches --
the SEAM, never a line number):
  A1 (resolution entry point): DESIGN Code-Design surface-5 pins
     ``TestRunnerPort.resolve(target_root) -> RunnerAdapter | Indeterminate`` at
     ``src/des/ports/test_runner_port.py`` (CREATE_NEW). This composition tries,
     in order, ``des.ports.test_runner_port``'s ``resolve`` /
     ``resolve_runner`` function -- or a ``TestRunnerPort`` /
     ``TestRunnerResolver`` class with a ``resolve`` method -- whichever DELIVER
     ships. Wire ``_drive_resolution`` to it. NB: the DESIGN Declared-Imports
     cell mis-cites ``des.cli.committed_scope_port`` for the ``Indeterminate``
     VO; the CORRECT path is ``des.ports.driven_ports.committed_scope_port``
     (verified) -- DELIVER uses the correct one.
  A2 (resolved-runner observable): the resolver returns a runner ADAPTER whose
     runner identity is observable (a ``.name`` / ``.runner`` / ``.id`` token,
     or a plain string). This composition reads the runner token from whatever
     envelope the resolver returns; if DELIVER names it differently, update
     ``_read_runner``.
  A3 (INDETERMINATE degrade): on an unrecognized lockfile the resolver returns
     the ``Indeterminate`` VO (``committed_scope_port.Indeterminate`` -- a
     ``reason`` field) OR a §17 INDETERMINATE verdict envelope. The reason MUST
     be non-empty and MUST NOT name a hardcoded-pytest fallback (C3 / §17).
     Update ``_read_resolution`` if the degrade envelope shape differs.
  A4 (slice-gate RUN scope): DESIGN surface-5 EXTENDs ``run_contract_gate.py``
     so the slice gate RUNS only the entering slice's ATs (resolved by
     ``Slice-Id``). This composition drives ``des run-contract-gate`` over a
     tmp repo and reads the RAN node-ids from the gate's machine-readable
     event. If DELIVER exposes the ran-scope differently (a new event field /
     flag), update ``_drive_slice_gate`` / ``_read_slice_scope``.
  A5 (feature-end full-suite leg + removal): DESIGN surface-5 EXTENDs
     ``feature_end_cycle_service.run_feature_end_cycle`` with a distinct clean
     full-suite leg AND removes the obsolete whole-tree-at-every-commit pytest.
     This composition reads the leg presence from the cycle's shipped surface +
     greps the SHIPPED ``run_contract_gate`` surface for the obsolete
     discriminating phrase's REMOVAL. If DELIVER lands the leg under a different
     cycle entry, update ``_read_feature_end_allocation``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_05_test_runner import (
    LOCKED_GATE_VERDICTS,
    OBSOLETE_WHOLE_TREE_MARKER,
    RECOGNIZED_BY_FILENAME,
    UNRECOGNIZED_LOCKFILE_CONTENT,
    UNRECOGNIZED_LOCKFILE_FILENAME,
    FeatureEndAllocation,
    GateVerdict,
    RunnerResolution,
    SliceGateScope,
    TargetRunner,
)


# Sentinel an absent seam invocation records, so the Then can name the missing
# mechanism instead of letting an ImportError escape as a collection error.
_SEAM_ABSENT = "__SEAM_ABSENT__"


@dataclass
class RunnerAllocationComposition:
    """Drives the slice-05 TestRunnerPort + allocation seams through their REAL surfaces."""

    _target_root: Path | None = field(default=None)
    _expected_runner: TargetRunner | None = field(default=None)
    _entering_slice: str | None = field(default=None)

    _resolution: RunnerResolution | None = field(default=None)
    _slice_scope: SliceGateScope | None = field(default=None)
    _allocation: FeatureEndAllocation | None = field(default=None)
    _seam_error: str | None = field(default=None)

    # =====================================================================
    # Given -- arm a REAL target carrying a real lockfile (AT-16 / AT-17)
    # =====================================================================

    def given_target_with_lockfile(
        self, tmp_path: Path, lockfile_filename: str
    ) -> None:
        """Plant a recognized lockfile into a fresh tmp target (real filesystem).

        Writes the CONTENT-DISTINCT lockfile fixture for the named lockfile into
        the tmp target so the resolver inspects a GENUINE file (§V.A filesystem
        inspection of the installed target). Records the runner the recognized
        lockfile must resolve to (the AT-16 expectation).
        """
        fixture = RECOGNIZED_BY_FILENAME.get(lockfile_filename)
        assert fixture is not None, (
            f"a recognized-runner scenario must name a lockfile in the "
            f"resolution table {sorted(RECOGNIZED_BY_FILENAME)!r} (§V.A) -- got "
            f"{lockfile_filename!r}, which the AT-side table does not cover."
        )
        target = tmp_path / "target"
        target.mkdir(parents=True, exist_ok=True)
        (target / fixture.filename).write_text(fixture.content, encoding="utf-8")
        self._target_root = target
        self._expected_runner = fixture.runner

    def given_target_with_unrecognized_lockfile(self, tmp_path: Path) -> None:
        """Plant an UNSUPPORTED-language manifest into a fresh tmp target (AT-17).

        The target carries a manifest no recognized-runner lockfile matches
        (``mix.exs`` -- elixir, the domain example 2 counter-case). The resolver
        MUST degrade LOUD to INDETERMINATE (N=0), never a hardcoded-pytest
        fallback.
        """
        target = tmp_path / "target"
        target.mkdir(parents=True, exist_ok=True)
        (target / UNRECOGNIZED_LOCKFILE_FILENAME).write_text(
            UNRECOGNIZED_LOCKFILE_CONTENT, encoding="utf-8"
        )
        self._target_root = target
        self._expected_runner = None

    # =====================================================================
    # Given -- arm a REAL repo + entering slice for the slice-gate RUN (AT-18)
    # =====================================================================

    def given_repo_entering_slice(self, tmp_path: Path, entering_slice: str) -> None:
        """Arm a tmp repo + the entering slice the contract gate scopes to (AT-18)."""
        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        self._target_root = repo
        self._entering_slice = entering_slice

    # =====================================================================
    # When -- drive the REAL seams
    # =====================================================================

    def when_resolving_the_runner(self) -> None:
        """Drive the REAL ``TestRunnerPort.resolve`` over the armed target (AT-16/17)."""
        assert self._target_root is not None, (
            "a runner-resolution scenario must arm an explicit target carrying a "
            "lockfile (given_target_with_lockfile / "
            "given_target_with_unrecognized_lockfile) -- got None (would resolve "
            "against an empty target, an unsatisfiable spec)."
        )
        self._resolution = self._drive_resolution(self._target_root)

    def when_slice_gate_runs(self) -> None:
        """Drive the REAL ``des run-contract-gate`` scoped to ONE slice (AT-18)."""
        assert self._target_root is not None and self._entering_slice is not None, (
            "a slice-gate scenario must arm a repo + an entering slice "
            "(given_repo_entering_slice) -- got None."
        )
        self._slice_scope = self._drive_slice_gate(
            self._target_root, self._entering_slice
        )

    def when_inspecting_feature_end_allocation(self) -> None:
        """Read the REAL feature-end full-suite-leg + removal-of-obsolete (AT-19)."""
        self._allocation = self._read_feature_end_allocation()

    # =====================================================================
    # Then -- observable readers
    # =====================================================================

    def then_resolved_runner_is(self, expected: TargetRunner) -> None:
        """The resolver resolved EXACTLY the runner the recognized lockfile names (AT-16)."""
        res = self._require_resolution()
        assert res.runner is not None, (
            f"the TestRunnerPort must RESOLVE a runner for a recognized lockfile "
            f"(filesystem inspection of the installed target, §V.A) -- it resolved "
            f"no runner. {self._observed()}"
        )
        assert res.runner == expected.value, (
            f"the TestRunnerPort must resolve {expected.value!r} from the "
            f"recognized lockfile in the target (§V.A / OB-RUNNER) -- got "
            f"{res.runner!r}. A resolver that always returns pytest fails the "
            f"vitest/go/cargo rows: pytest is the nWave-dev DOGFOOD runner behind "
            f"the port, NOT the universal executor (C3). {self._observed()}"
        )

    def then_resolution_is_indeterminate(self) -> None:
        """An unrecognized lockfile degrades LOUD to §17 INDETERMINATE (AT-17)."""
        res = self._require_resolution()
        assert res.verdict in LOCKED_GATE_VERDICTS, (
            f"an unrecognized-runner target must degrade to one of the §17 LOCKED "
            f"FIVE verdicts {sorted(LOCKED_GATE_VERDICTS)!r} (ADR-GV-001, no sixth "
            f"-- C6) -- got verdict={res.verdict!r}. {self._observed()}"
        )
        assert res.verdict == GateVerdict.INDETERMINATE.value, (
            f"an unrecognized runner / unsupported language must degrade LOUD to "
            f"INDETERMINATE (N=0, §17 / C3) -- NEVER a hardcoded-pytest fallback, "
            f"never a silent-pass -- got {res.verdict!r}. {self._observed()}"
        )

    def then_resolution_does_not_fall_back_to_pytest(self) -> None:
        """The INDETERMINATE reason names the degrade, never a hardcoded-pytest fallback (AT-17)."""
        res = self._require_resolution()
        assert res.reason, (
            f"the unrecognized-runner degrade must come back with a NON-EMPTY "
            f"reason naming WHY no runner resolved (Invariant 2 -- no silent "
            f"degrade) -- the resolver returned no reason. {self._observed()}"
        )
        # The degrade must NOT have silently fallen back to pytest: neither the
        # resolved runner nor the reason may name pytest as the chosen runner.
        assert res.runner != TargetRunner.PYTEST.value, (
            f"an unrecognized target MUST NOT silently fall back to the pytest "
            f"runner (C3 -- pytest is the dogfood, never the universal executor) "
            f"-- the resolver resolved pytest for a non-pytest target. "
            f"{self._observed()}"
        )

    def then_slice_gate_runs_slice_ats_only(self) -> None:
        """The slice gate RAN the slice's ATs only -- not the whole tree (AT-18)."""
        scope = self._require_slice_scope()
        assert scope.ran_node_ids is not None and len(scope.ran_node_ids) > 0, (
            f"the slice gate must RUN the entering slice's ATs (the §V.B "
            f"ATs@slice allocation -- fast, proportional) -- it ran no slice "
            f"node-ids. Today run_contract_gate has only a whole-tree RUN "
            f"(_mode_run_suite) + a collect-only --feature-id mode; the "
            f"slice-AT RUN is the net-new seam. {self._observed()}"
        )
        assert scope.ran_whole_tree is False, (
            f"the slice gate MUST NOT run the WHOLE-tree contract suite (the "
            f"obsolete ~40-min-every-commit behavior the §V.B re-allocation "
            f"supersedes, C10) -- the gate ran the whole tree. {self._observed()}"
        )
        assert not scope.out_of_slice_ran, (
            f"the slice gate ran tests OUTSIDE the entering slice "
            f"{self._entering_slice!r} (a leak past the slice scope) -- "
            f"out-of-slice node-ids ran: {scope.out_of_slice_ran!r}. "
            f"{self._observed()}"
        )

    def then_feature_end_runs_full_suite_once(self) -> None:
        """A distinct clean full-suite leg runs ONCE at feature-end (AT-19)."""
        alloc = self._require_allocation()
        assert alloc.full_suite_leg_present is True, (
            f"the feature-end cycle (feature_end_cycle_service.run_feature_end_"
            f"cycle) must run a DISTINCT clean full-suite leg ONCE at feature-end "
            f"(the §V.B full-suite-once allocation) -- the cycle today runs "
            f"env-e2e + coverage-map but NO full-suite leg. {self._observed()}"
        )

    def then_obsolete_whole_tree_at_slice_is_removed(self) -> None:
        """The hardcoded-pytest-over-whole-tree at every commit-slice is GONE (AT-19, C10)."""
        alloc = self._require_allocation()
        assert alloc.obsolete_whole_tree_at_slice_present is False, (
            f"the obsolete hardcoded-pytest-over-whole-tree at EVERY commit-slice "
            f"(the §V.B 'current divergence to correct' -- the discriminating "
            f"phrase {OBSOLETE_WHOLE_TREE_MARKER!r} over the WHOLE tree on the "
            f"slice-gate RUN path) must be REMOVED (C10 removal-of-obsolete; git "
            f"is the archive) -- it is still present on the shipped slice-gate "
            f"surface. {self._observed()}"
        )

    # =====================================================================
    # driving-port invocations (lazy seam import / subprocess -> sentinel)
    # =====================================================================

    def _drive_resolution(self, target_root: Path) -> RunnerResolution:
        """Drive the REAL TestRunnerPort.resolve over the target (A1-A3).

        At HEAD ``src/des/ports/test_runner_port.py`` + ``src/des/adapters/
        driven/runner/`` are ABSENT -> the lazy import fails -> the sentinel
        records the absent seam and the Then fires the named RED.
        """
        try:
            from des.ports import test_runner_port as runner_port_module
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return self._absent_resolution()

        resolver = self._resolve_resolution_callable(runner_port_module)
        if resolver is None:
            self._seam_error = _SEAM_ABSENT
            return self._absent_resolution()

        try:
            result = resolver(target_root)
        except Exception:
            self._seam_error = _SEAM_ABSENT
            return self._absent_resolution()

        return self._read_resolution(result)

    @staticmethod
    def _resolve_resolution_callable(module: object) -> object | None:
        """Resolve whichever resolution entry DELIVER ships (A1 -- the SEAM)."""
        for name in ("resolve", "resolve_runner"):
            candidate = getattr(module, name, None)
            if callable(candidate):
                return candidate
        for cls_name in ("TestRunnerPort", "TestRunnerResolver"):
            cls = getattr(module, cls_name, None)
            if cls is None:
                continue
            try:
                instance = cls()
            except Exception:
                continue
            method = getattr(instance, "resolve", None)
            if callable(method):
                return method
        return None

    def _read_resolution(self, result: object) -> RunnerResolution:
        """Read the port-exposed resolved-runner OR the INDETERMINATE degrade (A2/A3)."""
        # An Indeterminate VO / a §17 INDETERMINATE verdict envelope?
        verdict = self._token(self._field(result, "verdict"))
        reason = self._field(result, "reason", "diagnostic", "message")
        runner = self._read_runner(result)
        if runner is None and verdict is None:
            # An Indeterminate VO carries a reason but no verdict token; treat
            # presence-of-reason-without-runner as the INDETERMINATE degrade.
            if isinstance(reason, str) and reason:
                verdict = GateVerdict.INDETERMINATE.value
        return RunnerResolution(
            runner=runner,
            verdict=verdict,
            reason=reason if isinstance(reason, str) else None,
        )

    def _read_runner(self, result: object) -> str | None:
        """Read the resolved runner identity from the resolver envelope (A2)."""
        runner_field = self._field(result, "runner", "name", "id", "runner_id")
        token = self._token(runner_field)
        if isinstance(token, str):
            return token
        # A plain string runner identity.
        if isinstance(result, str):
            return result
        return None

    def _drive_slice_gate(self, repo: Path, entering_slice: str) -> SliceGateScope:
        """Drive the REAL ``des run-contract-gate`` scoped to one slice (A4).

        At HEAD ``run_contract_gate`` has NO slice-AT RUN mode (its --feature-id
        mode is collect-only + arch RUN; the only RUN mode is whole-tree
        _mode_run_suite). The slice-scoped RUN allocation is the net-new seam ->
        no machine-readable ran-slice-scope event is producible -> the sentinel
        records the absent seam and the Then fires the named RED. DELIVER wires
        this to the real slice-scoped RUN it ships (Layer 3 subprocess -- the
        ``run-contract-gate`` dispatcher row EXISTS, but the slice-AT RUN mode
        does not).
        """
        try:
            from des.cli import run_contract_gate as gate_module
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return self._absent_slice_scope()

        reader = self._resolve_slice_scope_reader(gate_module, repo, entering_slice)
        if reader is None:
            self._seam_error = _SEAM_ABSENT
            return self._absent_slice_scope()
        return reader

    def _resolve_slice_scope_reader(
        self, gate_module: object, repo: Path, entering_slice: str
    ) -> SliceGateScope | None:
        """Resolve the slice-scoped RUN observable, if DELIVER ships one (A4 -- the SEAM).

        Looks for a slice-scoped RUN entry on the gate module (a
        ``run_slice_ats`` / ``run_slice_scope`` callable returning the ran
        node-ids + a whole-tree flag). At HEAD this entry is ABSENT (the
        --feature-id mode is collect-only, not a slice-AT RUN), so this returns
        None -> the named RED. The dispatcher ``run-contract-gate`` row exists,
        but the slice-AT RUN allocation is the net-new behavior.
        """
        for name in ("run_slice_ats", "run_slice_scope", "run_slice"):
            candidate = getattr(gate_module, name, None)
            if not callable(candidate):
                continue
            try:
                result = candidate(repo, entering_slice)
            except Exception:
                continue
            ran = self._field(result, "ran_node_ids", "ran", "node_ids")
            whole_tree = self._field(result, "ran_whole_tree", "whole_tree")
            out_of_slice = self._field(result, "out_of_slice_ran", "out_of_slice")
            return SliceGateScope(
                ran_node_ids=tuple(ran) if ran else None,
                ran_whole_tree=bool(whole_tree) if whole_tree is not None else None,
                out_of_slice_ran=tuple(out_of_slice) if out_of_slice else (),
            )
        return None

    def _read_feature_end_allocation(self) -> FeatureEndAllocation:
        """Read the feature-end full-suite leg + removal-of-obsolete (A5).

        The full-suite leg is a net-new distinct clean leg on
        ``feature_end_cycle_service.run_feature_end_cycle`` (ABSENT at HEAD: the
        cycle runs env-e2e + coverage-map only). The removal-of-obsolete is the
        ABSENCE of the discriminating whole-tree marker on the slice-gate RUN
        path. Both are read from the SHIPPED surfaces (a real module-attribute
        probe + a real shipped-source read), never an inline test string.
        """
        full_suite_present = self._probe_full_suite_leg()
        obsolete_present = self._probe_obsolete_whole_tree_marker()
        return FeatureEndAllocation(
            full_suite_leg_present=full_suite_present,
            obsolete_whole_tree_at_slice_present=obsolete_present,
        )

    def _probe_full_suite_leg(self) -> bool | None:
        """Probe whether the feature-end cycle ships a distinct full-suite leg (A5)."""
        try:
            from des.application import (
                feature_end_cycle_service as cycle_module,
            )
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return None
        # DELIVER lands the leg as a named entry on the cycle module (a
        # ``_run_full_suite_leg`` helper or a ``FullSuite*`` result arm). At HEAD
        # none exists -> the leg is absent.
        for name in (
            "_run_full_suite_leg",
            "run_full_suite_leg",
            "FullSuiteLegRan",
            "FullSuiteVerified",
        ):
            if getattr(cycle_module, name, None) is not None:
                return True
        return False

    def _probe_obsolete_whole_tree_marker(self) -> bool | None:
        """Probe whether the obsolete whole-tree-at-every-slice pytest is still shipped (A5).

        Reads the REAL shipped ``run_contract_gate`` source (the slice-gate
        surface) and checks whether the whole-tree contract-suite marker is
        still wired into the per-commit-slice RUN EXECUTION path -- the
        ``_run_contract_suite`` / ``_mode_run_suite`` function bodies (the
        subprocess-pytest-over-whole-tree leg the slice gate invokes at every
        commit-slice). The signal is the per-slice RUN-leg REFERENCING the
        whole-tree contract marker -- either the ``_CONTRACT_MARKER`` NAME (how
        the leg wires it today: ``"-m", _CONTRACT_MARKER``) OR the literal
        discriminating phrase ``"unit or integration or acceptance"`` (the
        Mandate-13 prose-surface fallback).

        The probe is SCOPED to those functions' EXECUTABLE bodies (docstrings
        stripped via AST) so the C10 removal is GREEN-able: DELIVER removes the
        whole-tree subprocess RUN from the per-slice path WITHOUT the marker's
        mere appearance in a module-level docstring / constant / a legitimately-
        retained feature-end full-suite leg keeping the AT RED. Reads the
        shipped file, never an inline string.

        DESIGN-CONTRACT ASSUMPTION (flagged to DELIVER, the SEAM): the C10
        removal target is the whole-tree subprocess RUN the per-commit-slice
        gate path invokes (today ``_run_contract_suite`` -> ``_mode_run_suite``).
        If DELIVER relocates the per-slice EXECUTION leg to a differently-named
        function, update ``obsolete_run_funcs`` -- the SEAM, never a line number.
        """
        try:
            import des.cli.run_contract_gate as gate_module
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return None
        module_file = getattr(gate_module, "__file__", None)
        if not module_file:
            self._seam_error = _SEAM_ABSENT
            return None
        source = Path(module_file).read_text(encoding="utf-8")
        return self._whole_tree_marker_in_run_leg(source)

    @staticmethod
    def _whole_tree_marker_in_run_leg(source: str) -> bool:
        """True iff the whole-tree contract marker is wired into a per-slice RUN leg.

        Scopes the check to the EXECUTABLE body of the per-commit-slice RUN
        functions (docstrings stripped via AST) so the obsolete behavior is
        judged by what the per-slice gate EXECUTES, not by the marker's
        appearance in prose / a module-level constant / a retained feature-end
        leg. The wiring signal is the RUN-leg body referencing the whole-tree
        contract marker -- the ``_CONTRACT_MARKER`` NAME (today's wiring) or the
        literal phrase. Degrades LOUD: if the AST parse fails OR the named RUN
        functions are absent (a structural shift), fall back to a whole-file
        substring check (never a silent False that would fabricate a green
        removal).
        """
        import ast as _ast

        # The per-commit-slice RUN-execution functions the C10 removal targets.
        obsolete_run_funcs = {"_run_contract_suite", "_mode_run_suite"}
        # The whole-tree contract-marker NAME the RUN leg wires today.
        marker_name = "_CONTRACT_MARKER"
        try:
            tree = _ast.parse(source)
        except SyntaxError:
            return OBSOLETE_WHOLE_TREE_MARKER in source

        found_target = False
        for node in _ast.walk(tree):
            if not (
                isinstance(node, _ast.FunctionDef) and node.name in obsolete_run_funcs
            ):
                continue
            found_target = True
            body = list(node.body)
            # Strip the function docstring (a bare leading string expr) so a
            # marker mentioned only in prose is not counted as wiring.
            if (
                body
                and isinstance(body[0], _ast.Expr)
                and isinstance(getattr(body[0], "value", None), _ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            for stmt in body:
                # the literal discriminating phrase in this stmt's source ...
                if OBSOLETE_WHOLE_TREE_MARKER in _ast.unparse(stmt):
                    return True
                # ... or a reference to the whole-tree contract-marker NAME.
                for sub in _ast.walk(stmt):
                    if isinstance(sub, _ast.Name) and sub.id == marker_name:
                        return True
        if not found_target:
            # The named per-slice RUN functions are gone / renamed -- degrade
            # LOUD to the whole-file check rather than fabricate a green removal.
            return OBSOLETE_WHOLE_TREE_MARKER in source
        return False

    # =====================================================================
    # absent-seam observables + envelope helpers
    # =====================================================================

    def _absent_resolution(self) -> RunnerResolution:
        return RunnerResolution(runner=None, verdict=None, reason=None)

    def _absent_slice_scope(self) -> SliceGateScope:
        return SliceGateScope(
            ran_node_ids=None, ran_whole_tree=None, out_of_slice_ran=None
        )

    @staticmethod
    def _field(obj: object, *names: str) -> object:
        """Read the first present attribute (or dict key) from a result envelope."""
        for name in names:
            value = getattr(obj, name, None)
            if value is not None:
                return value
            if isinstance(obj, dict) and name in obj:
                return obj[name]
        return None

    @staticmethod
    def _token(value: object) -> object:
        """Coerce an enum-or-str value to its wire token (or pass through)."""
        if value is None:
            return None
        return getattr(value, "value", value)

    # =====================================================================
    # diagnostics
    # =====================================================================

    def _require_resolution(self) -> RunnerResolution:
        if self._resolution is None or self._seam_error == _SEAM_ABSENT:
            raise AssertionError(
                "the slice-05 TestRunnerPort RESOLUTION REGISTRY (resolve("
                "target_root) -> RunnerAdapter | Indeterminate -- it inspects the "
                "installed target's lockfile: pyproject.toml->pytest, "
                "package.json->vitest, go.mod->go test, Cargo.toml->cargo; "
                "unrecognized -> INDETERMINATE, never hardcoded-pytest) must exist "
                "and resolve a runner -- the resolution seam is ABSENT at HEAD "
                "(active-RED; DELIVER builds src/des/ports/test_runner_port.py + "
                "src/des/adapters/driven/runner/, REUSING backlog D8, the "
                "CodeFactPort test-execution sibling -- NB src/des/cli/run_tests.py "
                "(ADR-042) is a per-runner ADAPTER, NOT the resolution registry). "
                f"{self._observed()}"
            )
        return self._resolution

    def _require_slice_scope(self) -> SliceGateScope:
        if self._slice_scope is None or self._seam_error == _SEAM_ABSENT:
            raise AssertionError(
                "the slice-05 slice-gate AT re-scope (des run-contract-gate RUNS "
                "ONLY the entering slice's ATs, resolved by Slice-Id -- the §V.B "
                "ATs@slice allocation that SUPERSEDES the hardcoded "
                "pytest -m 'unit or integration or acceptance' over the WHOLE tree "
                "at every commit-slice) must exist -- the slice-AT RUN mode is "
                "ABSENT at HEAD (run_contract_gate's --feature-id mode is "
                "collect-only + arch RUN, NOT a slice-AT RUN; the only RUN mode is "
                "whole-tree _mode_run_suite). active-RED; DELIVER EXTENDs "
                "src/des/cli/run_contract_gate.py WITHOUT breaking the collect-only "
                "--verify-gate-scope digest mechanism. "
                f"{self._observed()}"
            )
        return self._slice_scope

    def _require_allocation(self) -> FeatureEndAllocation:
        if self._allocation is None or self._seam_error == _SEAM_ABSENT:
            raise AssertionError(
                "the slice-05 feature-end full-suite leg (a NEW distinct clean "
                "full-suite leg added to feature_end_cycle_service."
                "run_feature_end_cycle -- the §V.B full-suite-once@feature-end "
                "allocation) + the removal-of-obsolete (C10: the "
                "whole-tree-at-every-commit-slice pytest REMOVED) must be shipped "
                "-- the feature-end cycle today runs env-e2e + coverage-map but NO "
                "full-suite leg, and the obsolete whole-tree marker is still wired "
                "into the slice-gate RUN path. active-RED; DELIVER EXTENDs "
                "src/des/application/feature_end_cycle_service.py. "
                f"{self._observed()}"
            )
        return self._allocation

    def _observed(self) -> str:
        return (
            f"target_root={self._target_root!r}; "
            f"expected_runner={self._expected_runner!r}; "
            f"entering_slice={self._entering_slice!r}; "
            f"resolution={self._resolution!r}; slice_scope={self._slice_scope!r}; "
            f"allocation={self._allocation!r}; seam_error={self._seam_error!r}"
        )
