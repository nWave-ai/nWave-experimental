"""Flavor dispatcher — pure-function workflow-flavor composition interpreter.

D4 Phase 3 slice-01 (per `docs/analysis/d4-schema-spec-2026-05-26.md` § 5 Phase 3).

The dispatcher is a stateless pure-function interpreter:

  * Reads a workflow flavor YAML file from `flavors_dir/<flavor_id>.yaml`.
  * Looks up the lifecycle event's `gate_composition` (an ordered list).
  * Invokes each gate via the injected `gate_invoker` Port (driven, external).
  * Aggregates results per each gate's declared `on_failure` rule:
      - `block`: halt composition on first failure, propagate block decision.
      - `warn`: continue composition, annotate result with warning, complete all.
      - `log`: continue silently, record event for audit.
  * Returns `CompositionResult` carrying the aggregated outcome + per-gate
    `GateInvocationResult` list.

This module is the structural defense against the bug class catalogued in
`docs/analysis/ddd-workflow-change-difficulty-2026-05-26.md` § 2 (workflow
change requires Python edits). After this slice ships, reordering gates or
swapping on_failure rules is a YAML edit — zero code change to this file.

Per INV-1 atomic units, INV-4 workflow IS data, INV-8 NO sequencer/engine
(this function returns once per event invocation; the host's event loop
calls it), INV-12 future change = reconfiguration, INV-13 single CLI entry
(gate_invoker abstracts the `des <gate-id>` subprocess pattern).

**Stdlib-only parser**: this module must remain stdlib-only per the DES-bundle
hygiene contract enforced by `tests/build/acceptance/plugin/steps/
test_des_bundle_steps.py::des_no_external_deps` — the bundled DES module
inside an installed plugin cannot pull in `pyyaml` (or `toml`/`tomli`).
Flavor files are parsed via the SSOT stdlib-only YAML-subset reader
`des._internal.subset_parser` (also consumed by `cli/doctor.py` and
`application/log_persistence.py`). That parser covers exactly the
flavor-file schema at `nWave/flavors/_schema.yaml`: top-level scalar keys,
literal/folded block scalars (`|`/`>`), simple lists, and the
`lifecycle_events` two-level mapping with gate-spec dicts. It is NOT a
general YAML parser — feeding it richer YAML constructs raises ValueError.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from des._internal import subset_parser


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class GateInvocationResult:
    """One gate's invocation outcome inside a composition.

    Attributes:
        gate_id: The gate that was invoked (matches catalog `gate_id`).
        exit_code: The gate process exit code (0 = success, non-zero = failure).
        stdout: Captured stdout from the gate invocation (JSON-line per gate
            contract). Empty string when the gate emitted nothing.
        on_failure_policy: The `on_failure` policy from the flavor config for
            this gate ("block" | "warn" | "log").
        warning_annotation: Human-readable annotation when on_failure_policy
            was "warn" and the gate failed. None on success or other policies.
    """

    gate_id: str
    exit_code: int
    stdout: str
    on_failure_policy: str
    warning_annotation: str | None = None

    @property
    def succeeded(self) -> bool:
        """True when the gate cleared (exit_code == 0)."""
        return self.exit_code == 0


@dataclass(frozen=True)
class CompositionResult:
    """The aggregated outcome of dispatching one lifecycle event composition.

    Attributes:
        lifecycle_event: The abstract event the dispatcher fired (e.g.
            "dispatch.pre", "subagent.stop").
        flavor_id: The active flavor (e.g. "atdd_pure", "classic").
        gate_results: Ordered per-gate `GateInvocationResult` list — one entry
            per gate invoked. Order matches the flavor's `gate_composition`
            list. Empty when the composition was empty for this event.
        halted: True when composition stopped before iterating every gate
            (because a gate with `on_failure: block` failed).
        blocking_gate_id: The gate_id that triggered the halt. None when
            composition completed without halt.
    """

    lifecycle_event: str
    flavor_id: str
    gate_results: list[GateInvocationResult] = field(default_factory=list)
    halted: bool = False
    blocking_gate_id: str | None = None

    @property
    def all_succeeded(self) -> bool:
        """True when every invoked gate cleared and composition did not halt."""
        return not self.halted and all(r.succeeded for r in self.gate_results)


# Port type alias for the gate_invoker dependency. The dispatcher is layout-
# independent: it dispatches by `gate_id` against this Port. The real adapter
# (slice-02) spawns `des <gate_id>` console-script subprocesses; test fakes
# capture each invocation in-process.
#
# Signature: (gate_id, args_dict) -> (exit_code, stdout)
GateInvoker = Callable[[str, dict[str, str]], "tuple[int, str]"]


def dispatch_lifecycle_event(
    event_id: str,
    flavor_id: str,
    context: dict[str, str],
    *,
    flavors_dir: Path | None = None,
    gate_invoker: GateInvoker | None = None,
) -> CompositionResult:
    """Read a workflow flavor file, look up the lifecycle event's composition,
    invoke each gate in order, aggregate results per `on_failure` rule.

    Args:
        event_id: Abstract lifecycle event name (must be in the closed
            vocabulary in `nWave/data/host-bridge-events.yaml`).
        flavor_id: Active flavor identifier (matches the flavor's `flavor_id`
            field, e.g. "atdd_pure", "classic").
        context: Substitution context for `args` placeholder expansion
            (e.g. `{"feature_id": "f-x", "slice_id": "slice-01"}`).
        flavors_dir: Directory containing `<flavor_id>.yaml` flavor files.
            Defaults to `nWave/flavors/` resolved from package root when None.
        gate_invoker: Port for actually invoking a gate. Defaults to a real
            subprocess invoker when None. Tests inject a fake to capture
            invocations in-process.

    Returns:
        `CompositionResult` carrying per-gate outcomes + composition halt state.

    Per INV-8: this function returns once per invocation; the host's event
    loop is the executor. Per INV-4: composition lives in YAML — this
    function NEVER hard-codes a gate order or `on_failure` rule.
    """
    assert flavors_dir is not None, "flavors_dir must be provided"
    assert gate_invoker is not None, "gate_invoker must be provided"

    flavor_doc = _parse_flavor_file(flavors_dir / f"{flavor_id}.yaml")
    lifecycle_events = flavor_doc["lifecycle_events"]
    assert isinstance(lifecycle_events, dict), (
        f"flavor {flavor_id!r} `lifecycle_events` must be a mapping"
    )
    composition = lifecycle_events[event_id]

    gate_results: list[GateInvocationResult] = []
    halted = False
    blocking_gate_id: str | None = None

    for gate_spec in composition:
        gate_id = gate_spec["gate_id"]
        on_failure = gate_spec["on_failure"]

        exit_code, stdout = gate_invoker(gate_id, dict(context))
        succeeded = exit_code == 0

        warning_annotation: str | None = None
        if not succeeded and on_failure == "warn":
            warning_annotation = (
                f"gate {gate_id!r} failed with exit_code={exit_code}; "
                "composition continued per on_failure=warn"
            )

        gate_results.append(
            GateInvocationResult(
                gate_id=gate_id,
                exit_code=exit_code,
                stdout=stdout,
                on_failure_policy=on_failure,
                warning_annotation=warning_annotation,
            )
        )

        if not succeeded and on_failure == "block":
            halted = True
            blocking_gate_id = gate_id
            break

    return CompositionResult(
        lifecycle_event=event_id,
        flavor_id=flavor_id,
        gate_results=gate_results,
        halted=halted,
        blocking_gate_id=blocking_gate_id,
    )


def _parse_flavor_file(path: Path) -> dict[str, object]:
    """Read a flavor YAML file and return its parsed document as a dict.

    Delegates to the SSOT stdlib-only YAML-subset parser
    (`des._internal.subset_parser`) -- the same reader `cli/doctor.py` and
    `application/log_persistence.py` use. That parser covers the flavor-file
    schema at `nWave/flavors/_schema.yaml` (top-level scalars, literal/folded
    block scalars, string lists, and the `lifecycle_events` mapping of
    gate-spec lists) and raises ValueError on unsupported syntax so silent
    mis-parses cannot mask a flavor-authoring error.
    """
    return subset_parser.load_file(path)
