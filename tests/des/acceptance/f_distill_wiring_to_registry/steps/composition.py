"""Composition root for the f-distill-wiring-to-registry slice-01 ATs.

Mandate-13 driving-port-only. slice-01 witnesses the DISTILL gate-out boundary
resolving ALL FOUR gates from the LIVE registry, the dormant flavor co-tenant
removed, and the GOAL-CONTRACT scorecard tightened so no dead flavor block can
false-credit a wired-module. Two REAL driving surfaces, no fixture authoring of
the expected stack (the shipped artifact, or its absence, IS the contract):

  * Layer 3 composition (CT-1 / CT-2 / CT-3) -- the REAL spine
    ``wave_gate_stack_dispatch.resolve_stack("distill","gate-out")`` reading the
    SHIPPED canonical registry ``nWave/waves/distill.yaml`` (the SOLE gate-stack
    source, ADR-FLOW-006 D6), PLUS a read of the shipped flavor
    ``nWave/flavors/atdd_pure.yaml`` as DATA to witness the dormant co-tenant's
    removal. The observable is the ordered gate-id sequence + the per-row
    ``on_failure`` + the flavor block's absence.
  * Layer 3 composition (CT-4 / CT-5) -- the REAL GOAL-CONTRACT scorecard module
    ``scripts/flow_v2_closure_scorecard.py``, loaded by path (it is a ``scripts/``
    module, not an importable package -- ``from scripts.*`` is forbidden per the
    feature-delta Reuse Analysis F-D-09). The observable is the scorecard's
    ``_module_wired`` verdict for f-coherence's three modules (CT-4) and for a
    synthetic dormant-flavor-only gate id (CT-5, the tightening regression-pin).

GROUND-TRUTH at HEAD (verified live this session -- the active-RED):
  * ``resolve_stack("distill","gate-out") == ["check-slice-at-completeness",
    "gate-design-at-coherence"]`` -- ``self-attest`` + ``verify-test-runner`` ABSENT
    -> CT-1 / CT-2 RED. (Post-DELIVER the live stack also carries the unrelated
    advisory gate ``verify-spec-coverage``, wired later by the evolution-plan P3.1
    spec-coverage feature -- CT-1 checks presence + THIS feature's relative order
    of its four gates, tolerating that and any other legitimately-added advisory
    gate; it never re-asserts an exact, closed gate-out list.)
  * ``atdd_pure.yaml`` STILL carries the ``wave_gate_stacks.distill`` co-tenant
    block -> CT-3 RED.
  * the scorecard ``_module_wired`` matches flavor strings, not live-resolution:
    ``gate-g`` -> False (subcommand renamed away, the stale key); ``self-attest`` /
    ``test-runner`` -> True ONLY via the dormant flavor block (the false-credit) ->
    CT-4 RED (not all three honestly live-resolve under a tightened check).
  * the scorecard exposes NO ``_live_resolved`` helper and ``_module_wired`` has no
    live-resolution AND -> a synthetic dormant-flavor-only gate id evaluates wired
    True today -> CT-5 RED (the false-credit can still happen).

GREEN once DELIVER (1) appends the two registry rows to ``distill.yaml``, (2)
removes the dormant flavor block, (3) renames the scorecard ``gate-g`` key to
``gate-design-at-coherence`` + adds the ``_live_resolved`` tightening (DDD-5/DDD-7).

Each composition method reaches the production seam through a LAZY import inside
the driving-port invocation, so an absent/renamed seam degrades to a captured
observable the ``Then`` turns into a NAMED semantic ``AssertionError`` -- never a
collection / import / setup error. The suite COLLECTS cleanly at HEAD.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .domain_types import (
    COHERENCE_WIRED_MODULES,
    DEAD_SCHEMA_PROPERTY,
    DISTILL_GATE_OUT_DECLARED_ORDER,
    FLAVOR_ONLY_WITNESS_GATE_ID,
    NEW_ROW_ON_FAILURE,
    SchemaPropertyObservable,
    StackObservable,
    WiredModuleObservable,
)


# tests/des/acceptance/f_distill_wiring_to_registry/steps/composition.py
#   parents[5] == repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_FLAVOR_PATH = _REPO_ROOT / "nWave" / "flavors" / "atdd_pure.yaml"
_FLAVOR_SCHEMA_PATH = _REPO_ROOT / "nWave" / "flavors" / "_schema.yaml"
_SCORECARD_PATH = _REPO_ROOT / "scripts" / "flow_v2_closure_scorecard.py"
_COHERENCE_FEATURE_ID = "f-coherence-and-attestation"

_DISTILL_WAVE = "distill"
_GATE_OUT_BOUNDARY = "gate-out"


def _load_scorecard():
    """Load the GOAL-CONTRACT scorecard module by path (driving port).

    The scorecard is a ``scripts/`` module (NOT an importable package -- the
    feature-delta Reuse Analysis F-D-09 forbids ``from scripts.*``). Loading it by
    path is the same in-repo, pure-stdlib mechanism the scorecard itself uses to
    shell ``des --help``; it stays target-machine-independent.
    """
    spec = importlib.util.spec_from_file_location(
        "flow_v2_closure_scorecard_at", _SCORECARD_PATH
    )
    assert spec is not None and spec.loader is not None, (
        f"the GOAL-CONTRACT scorecard must be loadable from {_SCORECARD_PATH} "
        "(it is the driving surface for CT-4 / CT-5)."
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class DistillWiringComposition:
    """Witnesses the DISTILL gate-out wiring across the live spine + the GOAL CONTRACT.

    CT-1 / CT-2 / CT-3: the registry-resolved gate-out stack (via the REAL
    ``resolve_stack``) + the flavor block's removal. CT-4 / CT-5: the scorecard's
    tightened ``_module_wired`` verdict (via the REAL GOAL-CONTRACT module).
    """

    _stack: StackObservable | None = field(default=None)
    _flavor_has_distill_block: bool | None = field(default=None)
    _module_observables: list[WiredModuleObservable] = field(default_factory=list)
    _synthetic_observable: WiredModuleObservable | None = field(default=None)
    _schema_observable: SchemaPropertyObservable | None = field(default=None)

    # =====================================================================
    # When -- drive the REAL spine / read the shipped flavor / drive the scorecard
    # =====================================================================

    def when_the_distill_gate_out_stack_is_resolved(self) -> None:
        """Resolve the LIVE DISTILL gate-out stack via the REAL spine (CT-1 / CT-2)."""
        self._stack = self._resolve_live_gate_out_stack()

    def when_the_flavor_file_is_inspected_for_the_dormant_block(self) -> None:
        """Read the shipped ``atdd_pure.yaml`` for the dormant distill co-tenant (CT-3)."""
        self._flavor_has_distill_block = self._flavor_carries_distill_co_tenant()

    def when_the_scorecard_evaluates_coherence_wired_modules(self) -> None:
        """Evaluate the scorecard's ``_module_wired`` for f-coherence's modules (CT-4)."""
        self._module_observables = self._evaluate_coherence_modules()

    def when_the_scorecard_evaluates_a_dormant_flavor_only_gate(self) -> None:
        """Evaluate ``_module_wired`` for a synthetic flavor-only gate id (CT-5)."""
        self._synthetic_observable = self._evaluate_synthetic_dormant_gate()

    def when_the_flavor_schema_is_inspected_for_the_dead_property(self) -> None:
        """Read the shipped ``_schema.yaml`` for the dead gate-stack property (CS-1)."""
        self._schema_observable = self._read_flavor_schema_dead_property()

    # =====================================================================
    # Then -- observable readers (NAMED semantic AssertionError on the active-RED)
    # =====================================================================

    def then_the_four_gates_resolve_in_declared_order(self) -> None:
        """The four DISTILL-OUT gates THIS feature wires are ALL present, in their
        declared RELATIVE order (CT-1) -- a subsequence check, not an exact-``==``
        full-stack match. Extra advisory gates legitimately added by other
        features (e.g. ``verify-spec-coverage``) are TOLERATED; the assertion
        proves only that this feature's four gates are live-resolved AND in the
        right relative order among themselves.
        """
        assert self._stack is not None, "the gate-out stack must be resolved first."
        resolved = list(self._stack.gate_ids_in_order)
        required = list(DISTILL_GATE_OUT_DECLARED_ORDER)
        present_indices = {
            gate_id: (resolved.index(gate_id) if gate_id in resolved else None)
            for gate_id in required
        }
        missing = [gate_id for gate_id, idx in present_indices.items() if idx is None]
        assert not missing, (
            "the DISTILL gate-out stack must LIVE-resolve all four gates this "
            f"feature wires {required!r}; missing from the resolved stack "
            f"{resolved!r}: {missing!r}. At HEAD self-attest + verify-test-runner "
            "are ABSENT (active-RED); DELIVER appends the two GateInvocation rows "
            "to nWave/waves/distill.yaml."
        )
        found_indices = [present_indices[gate_id] for gate_id in required]
        assert found_indices == sorted(found_indices), (
            "the four DISTILL-OUT gates this feature wires must LIVE-resolve in "
            f"their declared relative order {required!r}; resolved positions "
            f"{dict(zip(required, found_indices, strict=True))!r} in stack "
            f"{resolved!r} are out of order."
        )

    def then_both_new_rows_are_warn(self) -> None:
        """The two NEW gate rows each carry ``on_failure: warn`` (CT-2)."""
        assert self._stack is not None, "the gate-out stack must be resolved first."
        for gate_id, expected in NEW_ROW_ON_FAILURE.items():
            actual = self._stack.on_failure_by_gate.get(gate_id)
            assert actual == expected, (
                f"the {gate_id!r} DISTILL-OUT row must carry on_failure={expected!r} "
                "(the no-objection boundary -- a record-/runner-absent DISTILL return "
                f"is never vetoed, DDD-2); resolved on_failure={actual!r}. "
                "At HEAD the row is ABSENT from the registry (active-RED)."
            )

    def then_the_dormant_flavor_block_is_absent(self) -> None:
        """The ``wave_gate_stacks.distill`` co-tenant is GONE from the flavor (CT-3)."""
        assert self._flavor_has_distill_block is not None, (
            "the flavor file must be inspected first."
        )
        assert self._flavor_has_distill_block is False, (
            "the dormant wave_gate_stacks.distill co-tenant must be REMOVED from "
            f"{_FLAVOR_PATH} -- it is the false-credit source the spine never reads "
            "(MOVE-not-COPY completion, DDD-3). At HEAD the block is STILL present "
            "(active-RED); DELIVER deletes it AFTER the registry rows land."
        )

    def then_all_coherence_modules_live_resolve(self) -> None:
        """f-coherence's three wired_modules all evaluate ``_module_wired`` True (CT-4)."""
        assert self._module_observables, (
            "the scorecard must evaluate the coherence modules first."
        )
        not_wired = [o.module for o in self._module_observables if o.wired is not True]
        assert not not_wired, (
            "f-coherence-and-attestation's three wired_modules "
            f"{list(COHERENCE_WIRED_MODULES)!r} must ALL evaluate _module_wired == "
            "True against the LIVE state (each subcommand registered AND its gate_id "
            f"live-resolved in the DISTILL gate-out registry); not-wired: {not_wired!r}. "
            "At HEAD the stale 'gate-g' key is unregistered and self-attest/"
            "test-runner only false-credit via the dormant flavor block (active-RED); "
            "DELIVER renames the key (DDD-5) + tightens _module_wired to live-resolution "
            "(DDD-7)."
        )

    def then_the_dormant_flavor_only_gate_is_not_wired(self) -> None:
        """A flavor-stringed gate absent from the live stack is NOT wired (CT-5, pin)."""
        assert self._synthetic_observable is not None, (
            "the scorecard must evaluate the flavor-only witness gate first."
        )
        assert self._synthetic_observable.wired is False, (
            f"a gate id present as a flavor-YAML string ({FLAVOR_ONLY_WITNESS_GATE_ID!r}) "
            "but ABSENT from the live resolve_stack('distill','gate-out') output must "
            f"evaluate NOT wired; got {self._synthetic_observable.wired!r}. At HEAD the "
            "scorecard has no _live_resolved tightening, so the flavor-string regex "
            "false-credits the witness wired True (the demonstrated defect); DELIVER "
            "adds the live-resolution tightening (DDD-7) so a flavor-only gate can no "
            "longer be false-credited."
        )

    def then_the_dead_schema_property_is_absent(self) -> None:
        """The flavor SCHEMA no longer declares ``properties.wave_gate_stacks`` (CS-1)."""
        assert self._schema_observable is not None, (
            "the flavor schema must be inspected first."
        )
        assert self._schema_observable.schema_carries_dead_property is False, (
            f"the dead flavor gate-stack $defs property {DEAD_SCHEMA_PROPERTY!r} must "
            f"be REMOVED from {_FLAVOR_SCHEMA_PATH} properties -- completing the "
            "MOVE-not-COPY (DDD-9) so the registry (nWave/waves/*.yaml) is the SOLE "
            "gate-stack source and no dead flavor schema property survives. At HEAD "
            "_schema.yaml STILL declares properties.wave_gate_stacks (active-RED); "
            "DELIVER deletes it AFTER every flavor instance drops the block."
        )

    # =====================================================================
    # Private -- the REAL driving-port invocations (lazy seam reach)
    # =====================================================================

    def _resolve_live_gate_out_stack(self) -> StackObservable:
        """Drive the REAL spine ``resolve_stack`` (the SOLE resolved surface)."""
        from des.application.wave_gate_stack_dispatch import resolve_stack

        rows = resolve_stack(_DISTILL_WAVE, _GATE_OUT_BOUNDARY).rows
        gate_ids = tuple(str(r.get("gate_id")) for r in rows)
        on_failure = {str(r.get("gate_id")): str(r.get("on_failure")) for r in rows}
        return StackObservable(
            gate_ids_in_order=gate_ids, on_failure_by_gate=on_failure
        )

    def _flavor_carries_distill_co_tenant(self) -> bool:
        """True iff ``atdd_pure.yaml`` still carries ``wave_gate_stacks.distill``."""
        data = yaml.safe_load(_FLAVOR_PATH.read_text(encoding="utf-8")) or {}
        stacks = data.get("wave_gate_stacks") or {}
        return _DISTILL_WAVE in stacks

    def _read_flavor_schema_dead_property(self) -> SchemaPropertyObservable:
        """True iff ``_schema.yaml`` still declares ``properties.wave_gate_stacks``.

        Reads the SHIPPED flavor schema as DATA (the artifact IS the contract) --
        the same pure-stdlib YAML read slice-01 CT-3 uses on the flavor instance.
        """
        data = yaml.safe_load(_FLAVOR_SCHEMA_PATH.read_text(encoding="utf-8")) or {}
        props = data.get("properties") or {}
        return SchemaPropertyObservable(
            schema_carries_dead_property=DEAD_SCHEMA_PROPERTY in props
        )

    def _evaluate_coherence_modules(self) -> list[WiredModuleObservable]:
        """Drive the REAL scorecard ``_module_wired`` for f-coherence's modules.

        The module names are read from the scorecard's OWN f-coherence ``FEATURES``
        row -- the GOAL-CONTRACT source of truth DELIVER mutates (DDD-5 renames the
        stale ``gate-g`` key). Reading the live row (not a hardcoded list) binds CT-4
        to the actual contract: at HEAD the row still names ``gate-g`` (unregistered,
        ``_module_wired`` False) -> not all three live-resolve -> active-RED.
        """
        sc = _load_scorecard()
        subs = sc._des_subcommands()
        modules = self._coherence_wired_modules(sc)
        return [
            WiredModuleObservable(module=m, wired=bool(sc._module_wired(subs, m)))
            for m in modules
        ]

    @staticmethod
    def _coherence_wired_modules(sc) -> list[str]:
        """The f-coherence ``wired_modules`` as the live scorecard declares them."""
        for feat in sc.FEATURES:
            if feat.get("id") == _COHERENCE_FEATURE_ID:
                return list(feat.get("wired_modules") or [])
        return []

    def _evaluate_synthetic_dormant_gate(self) -> WiredModuleObservable:
        """Drive the REAL scorecard's live-resolution check for a flavor-only gate.

        The regression-pin (CT-5, DDD-7) isolates the false-credit MECHANISM, not
        the wiring: the witness gate id is registered as a real subcommand AND whose
        name appears in a WIRING_FILES HOOK (``scripts/hooks/run_wave_contract_
        coherence.py`` -- NOT the flavor block), yet ABSENT from the live
        ``resolve_stack`` output at HEAD. Under the OLD ``_module_wired`` (regex over
        WIRING_FILES = flavors + hooks) it is false-credited wired True; under the
        tightened ``_live_resolved`` (DDD-7) it must be wired False because it does
        not live-resolve.

        The scorecard MUST expose a ``_live_resolved(wave, boundary, gate_id)``
        helper returning the un-gameable answer. At HEAD that helper is ABSENT (no
        tightening), so this scaffold falls back to the OLD ``_module_wired`` -- which
        false-credits the witness wired True at HEAD -> the ``Then`` fires the NAMED
        active-RED. Post-DELIVER the helper exists and returns False (the gate is
        registered + flavor-stringed but never live-resolves), turning CT-5 GREEN --
        the false-credit can no longer happen.
        """
        sc = _load_scorecard()
        subs = sc._des_subcommands()
        live = getattr(sc, "_live_resolved", None)
        if callable(live):
            wired = bool(
                live(_DISTILL_WAVE, _GATE_OUT_BOUNDARY, FLAVOR_ONLY_WITNESS_GATE_ID)
            )
        else:
            # No tightening at HEAD -> the old flavor-string check false-credits the
            # registered + flavor-stringed witness wired True (the active-RED).
            wired = bool(sc._module_wired(subs, FLAVOR_ONLY_WITNESS_GATE_ID))
        return WiredModuleObservable(module=FLAVOR_ONLY_WITNESS_GATE_ID, wired=wired)
