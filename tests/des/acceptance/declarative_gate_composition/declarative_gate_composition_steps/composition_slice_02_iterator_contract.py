"""Composition root for f-declarative-gate-composition slice-02 (iterator contract).

DRIVING SURFACE (Mandate-13 driving-port-only, Layer 3 composition): the REAL
``flavor_dispatcher.dispatch_lifecycle_event`` (the EXISTING substrate the DESIGN
[REF] Code-Design "generic-iterator behavior" mandates REUSE of) + the REAL
net-new ``flavor_dispatcher.resolve_wave_gate_stack`` pure seam, exercised over a
REAL flavor file (written to tmp_path in the supported subset) with a REAL
in-process ``gate_invoker`` Port. The dispatcher is the production composition the
real PreToolUse/SubagentStop callers use (``carpaccio_intercept`` calls it at :522).
The gate_invoker Port is the SAME injection point the real adapter uses (a
subprocess invoker in production; an in-process capture here, per the dispatcher's
own docstring "test fakes capture each invocation in-process").

DESIGN-SANCTIONED OBSERVABLES ONLY (Public Surface table, lines 754-776):
  * ``CompositionResult.{halted, blocking_gate_id}`` -- the existing aggregated
    halt surface.
  * per-gate ``GateInvocationResult.{exit_code, stdout, recovery_suggestions}`` --
    ``recovery_suggestions`` is the ONE declared result-shape delta (an optional
    field the dispatcher fills by parsing the gate's emitted JSON stdout line).
  * the UnknownGate / INDETERMINATE class is read from the GATE'S JSON-STDOUT event
    (``GateInvocationResult.stdout``), per OB-2 "the gate already emits a JSON line"
    -- NOT from any materialized ``CompositionResult.verdict`` field (that field is
    NOT in the Public Surface table; the §17 exit_code->GateVerdict map lives in the
    HANDLER, not as a result-shape delta -- DESIGN lines 748-752).

The four iterator-contract behaviors (all @contract-shape:bounded-change -- the
schema-add is additive; the verdict-map/order/recovery-carry are bounded changes):

  * AT-3 reorder = declared-order: the dispatcher iterates the resolved stack in
    declared order and HALTS at the first ``on_failure: block`` veto -- the existing
    halt-at-first-block contract over the resolved list. Parametrized over the order
    positions; assert on ``CompositionResult.blocking_gate_id``.
  * AT-5 unknown-gate fail-closed: a declared gate_id absent from the catalog ->
    the gate's JSON stdout carries the ``UnknownGateOnDispatchPre`` event, the
    composition HALTS (``halted``), names the offending id, never a silent skip.
  * AT-6 INDETERMINATE degrade-LOUD: a composed gate whose JSON stdout carries the
    INDETERMINATE signal HALTS the composition LOUD, never silent-pass / false green.
  * AT-7 non-regression: the already-wired event compositions (dispatch.pre /
    subagent.stop / commit.pre / session.init) + the classic flavor still resolve +
    iterate unchanged after the per-wave lift.

Active-RED scaffold (atdd_pure -- NOT @skip): the iterator-contract assertions are
RED at HEAD because the net-new seams are absent -- ``resolve_wave_gate_stack`` does
not exist (AT-3/AT-7 wave-stack resolution returns empty -> no blocking gate / the
atdd_pure stack is empty), and ``GateInvocationResult`` has no ``recovery_suggestions``
field, so the dispatcher does not yet PARSE the gate's JSON stdout into a per-gate
recovery payload (AT-5/AT-6 read the parsed UnknownGate/INDETERMINATE class + named
id from that net-new field). Each Then fires a semantic AssertionError naming the
missing DESIGN-sanctioned seam, never collection / import / setup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
_SHIPPED_FLAVORS_DIR = REPO_ROOT / "nWave" / "flavors"
_ATDD_PURE = "atdd_pure"
_CLASSIC = "classic"
_DISCUSS_WAVE = "discuss"

# A minimal flavor doc (within the stdlib subset) declaring a 2-gate gate-in stack
# whose declared ORDER fixes which gate vetoes first (AT-3). Both block-gates veto;
# reordering swaps which one halts the composition.
_FLAVOR_WITH_REORDERABLE_STACK = """\
flavor_id: probe_reorder
descriptor: probe
deliver_phase_shape: probe
lifecycle_events:
  dispatch.pre:
    - gate_id: alpha-gate
      on_failure: block
wave_gate_stacks:
  discuss:
    gate-in:
      - gate_id: {first}
        on_failure: block
      - gate_id: {second}
        on_failure: block
    gate-out:
      - gate_id: validate-feature-delta
        on_failure: block
"""

# A minimal flavor whose dispatch.pre carries an EXPLICIT composition the dispatcher
# iterates -- used for AT-5 (uncatalogued gate) and AT-6 (INDETERMINATE gate). The
# composition is the resolved stack written into the lifecycle_events block so the
# REUSED dispatch_lifecycle_event drives it (DESIGN reuse path), no invented entry.
_FLAVOR_WITH_SINGLE_GATE = """\
flavor_id: probe_single
descriptor: probe
deliver_phase_shape: probe
lifecycle_events:
  dispatch.pre:
    - gate_id: {gate_id}
      on_failure: block
"""

# The synthetic probe event the resolved stack is dispatched under (reusing
# dispatch_lifecycle_event over a real flavor whose lifecycle_events carries the
# resolved stack -- the DESIGN reuse path).
_PROBE_EVENT = "dispatch.pre"


@dataclass
class IteratorContractComposition:
    """Drives the REAL dispatcher + resolver seams for the iterator contract."""

    _flavors_dir: Path | None = field(default=None)
    _flavor_id: str | None = field(default=None)
    _vetoing_gate: str | None = field(default=None)
    _unknown_gate_id: str | None = field(default=None)
    _indeterminate_gate: str | None = field(default=None)
    # captured DESIGN-sanctioned CompositionResult observable surface
    _result_blocking_gate: str | None = field(default=None)
    _result_halted: bool | None = field(default=None)
    _result_order: list[str] | None = field(default=None)
    # per-gate GateInvocationResult of the blocking gate (sanctioned fields)
    _blocking_gate_stdout: str | None = field(default=None)
    _blocking_gate_recovery: list[str] | None = field(default=None)
    _gate_result_has_recovery_field: bool | None = field(default=None)
    _resolved_stack: list[dict[str, str]] | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_reorderable_stack(
        self, tmp_path: Path, first_gate: str, second_gate: str
    ) -> None:
        """Write a REAL flavor whose declared gate-in order is (first, second)."""
        self._flavors_dir = tmp_path
        self._flavor_id = "probe_reorder"
        self._vetoing_gate = first_gate
        flavor_text = _FLAVOR_WITH_REORDERABLE_STACK.format(
            first=first_gate, second=second_gate
        )
        (tmp_path / "probe_reorder.yaml").write_text(flavor_text, encoding="utf-8")

    def given_stack_declares_uncatalogued_gate(
        self, tmp_path: Path, gate_id: str
    ) -> None:
        """Arm a declared composition whose single gate_id is not in the catalog."""
        self._flavors_dir = tmp_path
        self._flavor_id = "probe_single"
        self._unknown_gate_id = gate_id
        (tmp_path / "probe_single.yaml").write_text(
            _FLAVOR_WITH_SINGLE_GATE.format(gate_id=gate_id), encoding="utf-8"
        )

    def given_gate_mechanism_cannot_run(self, tmp_path: Path, gate_id: str) -> None:
        """Arm a composed (catalogued) gate whose mechanism returns INDETERMINATE."""
        self._flavors_dir = tmp_path
        self._flavor_id = "probe_single"
        self._indeterminate_gate = gate_id
        (tmp_path / "probe_single.yaml").write_text(
            _FLAVOR_WITH_SINGLE_GATE.format(gate_id=gate_id), encoding="utf-8"
        )

    def given_shipped_flavor(self, flavor_id: str) -> None:
        """Target a SHIPPED flavor (atdd_pure / classic) for non-regression."""
        self._flavors_dir = _SHIPPED_FLAVORS_DIR
        self._flavor_id = flavor_id

    # ---- when ---------------------------------------------------------------

    def when_declared_stack_is_iterated(self) -> None:
        """Resolve the declared gate-in stack, then REUSE dispatch_lifecycle_event.

        The resolved stack (via the net-new resolve_wave_gate_stack seam) is written
        into a real flavor's lifecycle_events block and driven through the EXISTING
        dispatch_lifecycle_event -- the DESIGN reuse path (NOT an invented per-wave
        dispatch entry).
        """
        assert self._flavors_dir is not None and self._flavor_id is not None
        stack = self._resolve_stack(_DISCUSS_WAVE, "gate-in")
        self._resolved_stack = stack
        self._dispatch_resolved_stack(stack, vetoing=self._vetoing_gate)

    def when_unknown_gate_is_iterated(self) -> None:
        """Drive the REUSED dispatcher over the flavor carrying the uncatalogued gate."""
        assert self._unknown_gate_id is not None
        self._dispatch_event(unknown=self._unknown_gate_id)

    def when_indeterminate_gate_is_iterated(self) -> None:
        """Drive the REUSED dispatcher over the flavor whose gate is INDETERMINATE."""
        assert self._indeterminate_gate is not None
        self._dispatch_event(indeterminate=self._indeterminate_gate)

    def when_shipped_event_compositions_are_resolved(self) -> None:
        """Resolve the SHIPPED DISCUSS stack from the registry (non-regression).

        slice-06 retarget: the DISCUSS gate-stack SOURCE moved flavor -> registry,
        so the non-regression resolution reads the registry-sourced spine
        ``resolve_stack`` (wave-keyed, flavor-independent), not the flavor block.
        """
        assert self._flavors_dir is not None and self._flavor_id is not None
        self._resolved_stack = self._resolve_registry_stack(_DISCUSS_WAVE, "gate-in")

    # ---- then: AT-3 (reorder = declared-order) -------------------------------

    def then_first_declared_gate_vetoes_first(self) -> None:
        """The gate at declared position 1 halts the composition (sanctioned surface).

        DESIGN-sanctioned oracle: ``CompositionResult.blocking_gate_id`` is the gate
        the existing halt-at-first-block dispatcher stopped on. Reorder = iteration
        order: the FIRST declared gate is the blocker, with zero code change.

        RED at HEAD: resolve_wave_gate_stack does not exist -> the resolved stack is
        empty -> dispatch_lifecycle_event iterates nothing -> blocking_gate_id is
        None. GREEN once the resolver returns the declared list in order and the
        existing dispatcher iterates it.
        """
        assert self._result_blocking_gate == self._vetoing_gate, (
            "the gate at declared position 1 must be the one that vetoes first "
            "(reorder = iteration-order, zero code change -- the EXISTING "
            "dispatch_lifecycle_event halt-at-first-block over the resolved "
            f"resolve_wave_gate_stack list); expected first-declared "
            f"{self._vetoing_gate!r} to be CompositionResult.blocking_gate_id, got "
            f"{self._result_blocking_gate!r}. {self._observed()}"
        )

    # ---- then: AT-5 (unknown gate fail-closed, named) ------------------------

    def then_unknown_gate_fails_closed_named(self) -> None:
        """An uncatalogued gate_id fails closed, named, never a silent skip.

        DESIGN-sanctioned oracle: ``CompositionResult.halted`` is True (the
        composition stopped fail-closed) and the blocking gate's
        ``GateInvocationResult.stdout`` carries the ``UnknownGateOnDispatchPre`` event
        naming the offending id (the EXISTING _gate_invoker_for fail-closed shape) --
        the §17 UnknownGate class is read from the GATE'S JSON STDOUT, not an invented
        result.verdict field. The named id is surfaced via the parsed per-gate
        ``GateInvocationResult.recovery_suggestions`` (the net-new declared field).

        RED at HEAD: GateInvocationResult has no recovery_suggestions field, so the
        dispatcher does not yet PARSE the gate's JSON stdout into a per-gate recovery
        payload that names the offending id -> the named-recovery assertion fires.
        GREEN once DELIVER adds the field + the JSON-stdout parse.
        """
        assert self._result_halted is True, (
            "an uncatalogued declared gate_id must HALT the composition fail-closed "
            "(CompositionResult.halted, never a silent skip that drops enforcement); "
            f"halted={self._result_halted!r}. {self._observed()}"
        )
        stdout = self._blocking_gate_stdout or ""
        assert "UnknownGateOnDispatchPre" in stdout, (
            "the blocking gate's GateInvocationResult.stdout must carry the "
            "UnknownGateOnDispatchPre event (the EXISTING _gate_invoker_for "
            f"fail-closed shape, §17 read from the gate's JSON stdout); got "
            f"stdout={stdout!r}. {self._observed()}"
        )
        # The net-new declared field must exist AND name the offending id (parity).
        assert self._gate_result_has_recovery_field is True, (
            "OB-2 requires the dispatcher to PARSE the gate's JSON stdout into the "
            "net-new GateInvocationResult.recovery_suggestions field so the generic "
            "handler surfaces the named fail-closed recovery; the field does not "
            f"exist yet. {self._observed()}"
        )
        named = " ".join(self._blocking_gate_recovery or [])
        assert self._unknown_gate_id is not None and self._unknown_gate_id in named, (
            "the parsed fail-closed recovery must NAME the offending gate_id so the "
            f"maintainer sees the typo ({self._unknown_gate_id!r}); the parsed "
            f"recovery did not carry it. recovery={self._blocking_gate_recovery!r}. "
            f"{self._observed()}"
        )

    # ---- then: AT-6 (INDETERMINATE degrade-LOUD) -----------------------------

    def then_indeterminate_degrades_loud(self) -> None:
        """A composed gate's INDETERMINATE halts LOUD, never silent-pass.

        DESIGN-sanctioned oracle: ``CompositionResult.halted`` is True and the
        blocking gate's ``GateInvocationResult.stdout`` carries the INDETERMINATE
        signal + the parsed ``GateInvocationResult.recovery_suggestions`` carries the
        degrade-LOUD hint (the §17 INDETERMINATE class read from the gate's JSON
        stdout, not an invented result.verdict).

        RED at HEAD: GateInvocationResult has no recovery_suggestions field, so the
        INDETERMINATE signal the gate emits is not PARSED into a carried degrade-LOUD
        payload -> the field-presence assertion fires. GREEN once DELIVER adds the
        field + the JSON-stdout parse.
        """
        assert self._result_halted is True, (
            "a composed gate whose mechanism could not run (INDETERMINATE) must "
            "degrade LOUD -- HALT the composition (CompositionResult.halted), never "
            f"silent-pass / false green; halted={self._result_halted!r}. "
            f"{self._observed()}"
        )
        stdout = self._blocking_gate_stdout or ""
        assert "indeterminate" in stdout.lower(), (
            "the blocking gate's GateInvocationResult.stdout must carry the "
            "INDETERMINATE signal (§17 read from the gate's JSON stdout, degrade-"
            f"LOUD); got stdout={stdout!r}. {self._observed()}"
        )
        assert self._gate_result_has_recovery_field is True, (
            "the INDETERMINATE degrade-LOUD hint the gate emits must be PARSED into "
            "the net-new GateInvocationResult.recovery_suggestions field (OB-2); the "
            f"field does not exist yet. {self._observed()}"
        )

    # ---- then: AT-7 (non-regression of shipped compositions) -----------------

    def then_shipped_event_compositions_unregressed(self) -> None:
        """The shipped event compositions resolve unchanged + the lift is additive.

        Seam-named oracle (Mandate-15 seam #1 + #3): the per-wave lift is ADDITIVE.
        The resolver MUST exist (the registry-sourced spine seam) and the DISCUSS
        gate-stack lift landed:
          * the DISCUSS gate-in stack resolves to a NON-EMPTY declared stack from
            the canonical wave-contract registry (``nWave/waves/discuss.yaml``) --
            flavor-INDEPENDENT after the slice-06 MOVE (ADR-FLOW-006 D6): the stack
            is keyed by WAVE, not by flavor, so it is the same NON-EMPTY answer
            whichever shipped flavor is being non-regression-checked.
        In every case the shipped per-flavor dispatch.pre event composition still
        iterates via the EXISTING dispatch_lifecycle_event (the lift did not regress
        the wave-agnostic event compositions, C8).

        slice-06 retarget: the SOURCE moved flavor -> registry; the behavioral
        guarantee is UNCHANGED -- DISCUSS gate-in declared, NON-EMPTY, iterated.
        The seam asserted is the registry-sourced spine ``resolve_stack`` the REAL
        PreToolUse/SubagentStop callers now read (NOT weakened: still non-empty +
        the shipped dispatch.pre composition still iterates per flavor).

        RED at HEAD (pre-MOVE source still flavor-private): the flavor
        ``wave_gate_stacks.discuss`` block is deleted but the resolution still read
        the flavor path -> _resolved_stack is [] -> the NON-EMPTY assertion fires.
        GREEN once the resolution reads the registry (this retarget) returning the
        migrated DISCUSS stack, with the event compositions untouched.
        """
        from des.application import wave_gate_stack_dispatch

        resolver_present = (
            getattr(wave_gate_stack_dispatch, "resolve_stack", None) is not None
        )
        assert resolver_present, (
            "the registry-sourced resolver seam wave_gate_stack_dispatch.resolve_stack "
            "must exist to prove the per-wave lift coexists with the shipped event "
            f"compositions (C8); it does not. {self._observed()}"
        )
        assert self._resolved_stack, (
            "the DISCUSS gate-in stack must resolve to a NON-EMPTY declared stack "
            "from the canonical wave-contract registry (nWave/waves/discuss.yaml) -- "
            "the slice-06 MOVE migrated it verbatim, flavor-independent; "
            f"resolve_stack returned {self._resolved_stack!r}. {self._observed()}"
        )
        # The shipped event composition for this flavor must still iterate cleanly
        # via the EXISTING dispatch_lifecycle_event (the lift did not regress it).
        order = self._dispatch_shipped_event("dispatch.pre")
        assert order, (
            f"the shipped {self._flavor_id!r} dispatch.pre event composition must "
            "still resolve + iterate after the per-wave lift (C8 non-regression); "
            f"it resolved empty. {self._observed()}"
        )

    # ---- driving-port invocations (Layer 3 composition, DESIGN reuse path) ---

    def _resolve_stack(self, wave: str, boundary: str) -> list[dict[str, str]]:
        """Drive the REAL resolve_wave_gate_stack seam over the PROBE flavor file.

        AT-3 only: resolves the reorderable PROBE flavor written to tmp_path (the
        alpha/beta declared order). This is a SYNTHETIC tmp-flavor whose declared
        ORDER fixes which gate vetoes first -- it is NOT the shipped DISCUSS stack
        (that SOURCE moved to the registry, resolved by ``_resolve_registry_stack``).
        Returns [] when the seam is absent.
        """
        from des.application import flavor_dispatcher

        resolver = getattr(flavor_dispatcher, "resolve_wave_gate_stack", None)
        if resolver is None:
            return []
        try:
            return list(
                resolver(
                    self._flavor_id,
                    wave,
                    boundary,
                    flavors_dir=self._flavors_dir,
                )
            )
        except (KeyError, ValueError, FileNotFoundError):
            return []

    def _resolve_registry_stack(self, wave: str, boundary: str) -> list[dict[str, str]]:
        """Drive the REAL registry-sourced spine resolver; [] when the seam is absent.

        AT-7 only: slice-06 MOVE-completion (ADR-FLOW-006 D6) moved the DISCUSS
        gate-stack SOURCE from the flavor-private ``wave_gate_stacks.discuss`` block
        (deleted) to the canonical wave-contract registry ``nWave/waves/discuss.yaml``.
        The non-regression resolution is retargeted to the spine
        ``wave_gate_stack_dispatch.resolve_stack`` -- the registry-sourced entry the
        REAL PreToolUse/SubagentStop callers now read (pre_tool_use_service.py:327 /
        subagent_stop_service.py:311). Only the SOURCE moved; the resolved rows the
        dispatcher iterates are byte-identical (same GateInvocation row schema,
        verbatim migration). The stack is WAVE-keyed (flavor-independent).
        """
        from des.application import wave_gate_stack_dispatch

        resolver = getattr(wave_gate_stack_dispatch, "resolve_stack", None)
        if resolver is None:
            return []
        try:
            return list(resolver(wave, boundary).rows)
        except (KeyError, ValueError, FileNotFoundError):
            return []

    def _dispatch_resolved_stack(
        self, stack: list[dict[str, str]], *, vetoing: str | None
    ) -> None:
        """Write the resolved stack into a real flavor and REUSE dispatch_lifecycle_event.

        DESIGN reuse path: the resolved stack becomes the lifecycle_events composition
        the EXISTING dispatch_lifecycle_event iterates (halt-at-first-block). When the
        resolver returns [] (seam absent at HEAD), the probe event has an empty
        composition -> no blocking gate -> RED.
        """
        assert self._flavors_dir is not None
        probe_dir = self._flavors_dir
        composition_lines = "\n".join(
            f"    - gate_id: {row['gate_id']}\n      on_failure: {row['on_failure']}"
            for row in stack
        )
        flavor_text = (
            "flavor_id: probe_resolved\n"
            "descriptor: probe\n"
            "deliver_phase_shape: probe\n"
            "lifecycle_events:\n"
            f"  {_PROBE_EVENT}:\n"
            + (composition_lines + "\n" if composition_lines else "    []\n")
        )
        (probe_dir / "probe_resolved.yaml").write_text(flavor_text, encoding="utf-8")
        self._run_dispatch("probe_resolved", probe_dir, vetoing=vetoing)

    def _dispatch_event(
        self, *, unknown: str | None = None, indeterminate: str | None = None
    ) -> None:
        """Drive the REUSED dispatch_lifecycle_event over the armed single-gate flavor."""
        assert self._flavors_dir is not None and self._flavor_id is not None
        self._run_dispatch(
            self._flavor_id,
            self._flavors_dir,
            unknown=unknown,
            indeterminate=indeterminate,
        )

    def _run_dispatch(
        self,
        flavor_id: str,
        flavors_dir: Path,
        *,
        vetoing: str | None = None,
        unknown: str | None = None,
        indeterminate: str | None = None,
    ) -> None:
        """Invoke the EXISTING compose_lifecycle_event with a REAL in-process invoker.

        The invoker returns each declared gate's signal on its JSON stdout: the
        vetoing gate blocks (exit!=0 + FAIL), an unknown gate returns the
        UnknownGateOnDispatchPre fail-closed JSON, an INDETERMINATE gate returns the
        INDETERMINATE JSON. The dispatcher's OWN iterate-in-declared-order +
        halt-at-first-block is the load-bearing behavior; the net-new per-gate
        recovery parse (GateInvocationResult.recovery_suggestions) is the seam.

        Drives the DOCUMENT entry (``compose_lifecycle_event``), not the
        IDENTITY-gated ``dispatch_lifecycle_event``: the synthetic probe flavors
        (``probe_reorder`` / ``probe_single`` / ``probe_resolved``) are test-only
        documents that name no shipped mode, so they are never members of
        ``ACTIVE_MODES`` -- routing them through the identity-gated entry raises
        ``FlavorNotExecutable`` on every call, which the surrounding except clause
        silently swallowed into an empty/None result. ``compose_lifecycle_event`` is
        mode-registry-blind BY SIGNATURE (it takes a flavor FILE, never an identity),
        which is exactly the door a synthetic flavor document belongs through --
        mirrors the established pattern in
        ``tests/des/acceptance/d4_phase_3_flavor_dispatcher/conftest.py``
        (``FlavorDispatcherComposition.dispatch``).
        """
        from des.application.flavor_dispatcher import compose_lifecycle_event

        catalog = self._catalog_gate_ids()

        def invoker(gate_id: str, _ctx: dict[str, str]) -> tuple[int, str]:
            if unknown is not None and gate_id == unknown:
                return 1, json.dumps(
                    {"event": "UnknownGateOnDispatchPre", "gate_id": gate_id}
                )
            if gate_id not in catalog:
                return 1, json.dumps(
                    {"event": "UnknownGateOnDispatchPre", "gate_id": gate_id}
                )
            if indeterminate is not None and gate_id == indeterminate:
                return 1, json.dumps(
                    {
                        "verdict": "indeterminate",
                        "gate_id": gate_id,
                        "recovery_suggestions": [
                            f"the {gate_id} mechanism could not run; degrade LOUD"
                        ],
                    }
                )
            if vetoing is not None and gate_id == vetoing:
                return 1, json.dumps(
                    {
                        "verdict": "fail",
                        "gate_id": gate_id,
                        "recovery_suggestions": [f"fix the {gate_id} failure"],
                    }
                )
            return 0, json.dumps({"verdict": "pass", "gate_id": gate_id})

        try:
            result = compose_lifecycle_event(
                flavors_dir / f"{flavor_id}.yaml",
                event_id=_PROBE_EVENT,
                flavor_id=flavor_id,
                context={"feature_id": "probe", "slice_id": "slice-01"},
                gate_invoker=invoker,
            )
        except (KeyError, ValueError, FileNotFoundError):
            self._capture_result(None)
            return
        self._capture_result(result)

    def _dispatch_shipped_event(self, event_id: str) -> list[str]:
        """Drive the REAL dispatch_lifecycle_event over a SHIPPED event composition."""
        from des.application.flavor_dispatcher import dispatch_lifecycle_event

        def invoker(gate_id: str, _ctx: dict[str, str]) -> tuple[int, str]:
            return 0, json.dumps({"verdict": "pass", "gate_id": gate_id})

        try:
            result = dispatch_lifecycle_event(
                event_id,
                self._flavor_id,
                {"feature_id": "probe", "slice_id": "slice-01"},
                flavors_dir=self._flavors_dir,
                gate_invoker=invoker,
            )
        except (KeyError, ValueError, FileNotFoundError):
            return []
        return [r.gate_id for r in result.gate_results]

    def _capture_result(self, result: object | None) -> None:
        """Capture ONLY DESIGN-sanctioned CompositionResult + GateInvocationResult fields."""
        if result is None:
            self._result_blocking_gate = None
            self._result_halted = None
            self._result_order = []
            self._blocking_gate_stdout = None
            self._blocking_gate_recovery = []
            self._gate_result_has_recovery_field = None
            return
        self._result_blocking_gate = getattr(result, "blocking_gate_id", None)
        self._result_halted = getattr(result, "halted", None)
        gate_results = list(getattr(result, "gate_results", []))
        self._result_order = [r.gate_id for r in gate_results]
        blocking = next(
            (r for r in gate_results if r.gate_id == self._result_blocking_gate),
            gate_results[-1] if gate_results else None,
        )
        if blocking is None:
            self._blocking_gate_stdout = None
            self._blocking_gate_recovery = []
            self._gate_result_has_recovery_field = None
            return
        self._blocking_gate_stdout = getattr(blocking, "stdout", None)
        # The net-new declared field -- absent at HEAD (the RED seam for AT-5/AT-6).
        has_field = "recovery_suggestions" in type(blocking).__dataclass_fields__
        self._gate_result_has_recovery_field = has_field
        self._blocking_gate_recovery = (
            list(getattr(blocking, "recovery_suggestions", [])) if has_field else []
        )

    # ---- substrate ----------------------------------------------------------

    def _catalog_gate_ids(self) -> set[str]:
        """The catalog gate_ids the unknown-gate guard checks against (real catalog)."""
        catalog_path = REPO_ROOT / "nWave" / "gates" / "_catalog.yaml"
        ids: set[str] = set()
        for line in catalog_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("- gate_id:"):
                ids.add(stripped.split(":", 1)[1].strip())
        # Plus the synthetic alpha/beta probe gates the reorder flavor declares.
        ids |= {"alpha-gate", "beta-gate"}
        return ids

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"flavor={self._flavor_id!r}; resolved_stack={self._resolved_stack!r}; "
            f"blocking_gate={self._result_blocking_gate!r}; "
            f"halted={self._result_halted!r}; order={self._result_order!r}; "
            f"blocking_stdout={self._blocking_gate_stdout!r}; "
            f"has_recovery_field={self._gate_result_has_recovery_field!r}; "
            f"recovery={self._blocking_gate_recovery!r}"
        )


__all__ = ["IteratorContractComposition"]
