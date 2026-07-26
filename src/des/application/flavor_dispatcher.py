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
literal/folded block scalars (`|`/`>`), simple lists, the `skill_load_set`
per-agent nested mapping, and the `lifecycle_events` two-level mapping with
gate-spec dicts. It is NOT a general YAML parser — feeding it richer YAML
constructs raises ValueError.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from des._internal import subset_parser
from des.application.workflow_mode import ACTIVE_MODES, CLASSIC_MODE


if TYPE_CHECKING:
    from pathlib import Path
    from typing import TypeGuard


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
        recovery_suggestions: The gate's specific recovery hints, parsed from
            its JSON-stdout line's `recovery_suggestions` field (OB-2 parity:
            each declared gate carries its OWN tailored recovery through the
            generic iteration, never a generic "a gate blocked"). Fail-closed
            to the empty tuple when the gate emitted non-JSON stdout or no
            `recovery_suggestions` key — an absent/unparseable recovery is a
            real empty answer, never an exception.
    """

    gate_id: str
    exit_code: int
    stdout: str
    on_failure_policy: str
    warning_annotation: str | None = None
    recovery_suggestions: tuple[str, ...] = ()

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


def _not_executable(flavor_id: str) -> str:
    """The refusal for a flavor this build cannot dispatch.

    It states the condition that is actually true -- the flavor is not among the
    executable modes -- and mentions the classic migration ONLY when the caller
    really did ask for classic. The single message this replaces named classic
    for every caller, so a synthetic or mistyped flavor id was told to migrate
    off a mode it had never used, and the reader went looking for a history that
    was not theirs. Naming the frequent case for every case is how a diagnostic
    stops carrying information.
    """
    active = ", ".join(sorted(ACTIVE_MODES))
    if flavor_id == CLASSIC_MODE:
        return (
            f"WHAT: flavor {flavor_id!r} is not executable. "
            "WHY: classic was removed; a declaration, a copied config or an "
            "environment default cannot bring it back. "
            f"HOW: migrate the project to atdd_pure with `des "
            f"convert-to-atdd-pure --workspace <project-dir>` (executable "
            f"modes: {active})."
        )
    return (
        f"WHAT: flavor {flavor_id!r} is not among this build's executable "
        "modes. "
        "WHY: only a mode the product ships can be dispatched -- an unknown id "
        "is refused rather than resolved to a default, because silently "
        "dispatching the wrong composition is worse than refusing. "
        f"HOW: dispatch one of the executable modes ({active}), or -- if this "
        "id is a test-authored flavor meant to exercise gate COMPOSITION rather "
        "than a product mode -- see the open design question on separating "
        "those two responsibilities before widening this set."
    )


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

    flavor_file = resolve_executable_flavor_path(flavor_id, flavors_dir)
    return compose_lifecycle_event(
        flavor_file,
        event_id=event_id,
        flavor_id=flavor_id,
        context=context,
        gate_invoker=gate_invoker,
    )


class FlavorNotExecutable(ValueError):
    """A mode IDENTITY this build does not dispatch.

    A subclass of ValueError so existing callers catching the base class keep
    working; distinct as a type so an oracle can decide on the property rather
    than on message text.
    """


class FlavorFileAbsent(ValueError):
    """The flavor DOCUMENT is missing at the resolved path.

    Deliberately distinct from `FlavorNotExecutable`: "this mode was retired"
    and "this file was deleted" ask for two different repairs, and one message
    covering both sends the reader down the wrong one.
    """


def resolve_executable_flavor_path(flavor_id: str, flavors_dir: Path) -> Path:
    """Identity -> document. THE single owner of the ACTIVE_MODES guard.

    Every caller holding a mode IDENTITY resolves it here, so the guard has one
    home instead of three inline copies. The guard is not weakened by the move --
    it is the same check, in one place, with the same refusal text.
    """
    if flavor_id not in ACTIVE_MODES:
        raise FlavorNotExecutable(_not_executable(flavor_id))
    path = flavors_dir / f"{flavor_id}.yaml"
    if not path.is_file():
        raise FlavorFileAbsent(
            f"WHAT: flavor {flavor_id!r} is executable but its declaration is "
            f"missing at {path}. "
            "WHY: an executable mode with no document cannot be composed, and "
            "reporting this as 'not executable' would send you to migrate a mode "
            "that is perfectly current. "
            "HOW: restore the flavor file, or point --flavors-dir at the "
            "directory that carries it."
        )
    return path


def compose_lifecycle_event(
    flavor_file: Path,
    *,
    event_id: str,
    flavor_id: str,
    context: dict[str, str],
    gate_invoker: GateInvoker,
) -> CompositionResult:
    """Document -> composition. Blind to the mode registry, BY SIGNATURE.

    This entry takes a DOCUMENT, never an identity, which is what makes the
    fusion this separation removes non-representable rather than merely
    discouraged: re-adding the guard here would mean adding a parameter the
    function does not use -- visible in review, unlike an `if` at the top of a
    body. It therefore cannot execute a retired mode: it is never handed one.

    `flavor_id` is still accepted, but only as a LABEL threaded into results for
    reporting. It is never compared against the registry here.
    """
    if not flavor_file.is_file():
        raise FlavorFileAbsent(
            f"WHAT: no flavor document at {flavor_file}. "
            "WHY: composition reads a declaration; without the file there is "
            "nothing to compose and nothing to report. "
            "HOW: pass the path of an existing flavor file."
        )
    flavor_doc = _parse_flavor_file(flavor_file)
    lifecycle_events = flavor_doc["lifecycle_events"]
    assert isinstance(lifecycle_events, dict), (
        f"flavor document {flavor_file} `lifecycle_events` must be a mapping"
    )
    if event_id not in lifecycle_events:
        declared = ", ".join(sorted(lifecycle_events)) or "(none)"
        raise LifecycleEventUndeclared(
            f"WHAT: {flavor_file} declares no composition for lifecycle event "
            f"{event_id!r}. "
            "WHY: an undeclared event has no gate order to run, and a bare "
            "KeyError naming only the event leaves you guessing what the file "
            "does declare. "
            f"HOW: declare {event_id!r} under `lifecycle_events`, or dispatch "
            f"one that is declared -- this file declares: {declared}."
        )
    return iterate_composition(
        lifecycle_events[event_id],
        event_id=event_id,
        flavor_id=flavor_id,
        context=context,
        gate_invoker=gate_invoker,
    )


class LifecycleEventUndeclared(KeyError):
    """The document declares no composition for the requested event.

    A KeyError subclass so callers catching KeyError still work; its message
    names the events the file DOES declare, which a bare KeyError never did.
    """


def iterate_composition(
    composition: list[dict[str, object]],
    *,
    event_id: str,
    flavor_id: str,
    context: dict[str, str],
    gate_invoker: GateInvoker,
) -> CompositionResult:
    """Iterate an ordered gate composition, halting at the first `block` veto.

    The load-bearing iterate/halt/recovery-parse core, extracted so BOTH the
    file-reading `dispatch_lifecycle_event` entry AND the per-wave gate-stack
    handlers (f-declarative-gate-composition: an already-resolved
    `wave_gate_stacks` stack) drive the SAME loop — one iterator, no second
    implementation. Invokes each gate in declared order, parses each gate's
    JSON-stdout `recovery_suggestions` into its `GateInvocationResult` (OB-2),
    and halts on the first `on_failure: block` failure (Invariant 4: a clean
    pass is "no objection", never an authorizing GO).
    """
    gate_results: list[GateInvocationResult] = []
    halted = False
    blocking_gate_id: str | None = None

    for gate_spec in composition:
        gate_id = gate_spec["gate_id"]
        on_failure = gate_spec["on_failure"]

        exit_code, stdout = gate_invoker(str(gate_id), dict(context))
        succeeded = exit_code == 0

        warning_annotation: str | None = None
        if not succeeded and on_failure == "warn":
            warning_annotation = (
                f"gate {gate_id!r} failed with exit_code={exit_code}; "
                "composition continued per on_failure=warn"
            )

        gate_results.append(
            GateInvocationResult(
                gate_id=str(gate_id),
                exit_code=exit_code,
                stdout=stdout,
                on_failure_policy=str(on_failure),
                warning_annotation=warning_annotation,
                recovery_suggestions=_parse_recovery_suggestions(stdout),
            )
        )

        if not succeeded and on_failure == "block":
            halted = True
            blocking_gate_id = str(gate_id)
            break

    return CompositionResult(
        lifecycle_event=event_id,
        flavor_id=flavor_id,
        gate_results=gate_results,
        halted=halted,
        blocking_gate_id=blocking_gate_id,
    )


def _parse_recovery_suggestions(stdout: str) -> tuple[str, ...]:
    """Parse a gate's JSON-stdout `recovery_suggestions` field, fail-closed.

    OB-2 parity carrier: each declared gate emits its specific recovery on its
    JSON-stdout line; the generic iteration parses it into the per-gate
    `GateInvocationResult.recovery_suggestions` so the handler surfaces THAT
    gate's tailored recovery, never a generic "a gate blocked". A non-JSON
    stdout, a JSON value that is not an object, or a `recovery_suggestions` that
    is not a list of strings yields the empty tuple — an absent/unparseable
    recovery is a real empty answer (fail-closed), never an exception.
    """
    if not stdout.strip():
        return ()
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return ()
    if not isinstance(payload, dict):
        return ()
    suggestions = payload.get("recovery_suggestions")
    if isinstance(suggestions, list) and all(
        isinstance(item, str) for item in suggestions
    ):
        return tuple(suggestions)
    # C6 fail-closed-named: a gate emitting the EXISTING `_gate_invoker_for`
    # `UnknownGateOnDispatchPre` fail-closed event (a declared-but-uncatalogued
    # gate_id) may carry no explicit recovery_suggestions — synthesize one that
    # NAMES the offending id so the maintainer sees the typo (never a silent
    # skip). The named recovery is the dispatcher's, derived from the gate's own
    # fail-closed JSON event, not invented out of band.
    if payload.get("event") == "UnknownGateOnDispatchPre":
        offending = payload.get("gate_id")
        if isinstance(offending, str) and offending:
            return (
                f"The declared gate_id {offending!r} is not a catalog gate "
                "(UnknownGateOnDispatchPre) -- fix the typo in the "
                "wave_gate_stacks composition so it names a gate from "
                "nWave/gates/_catalog.yaml; a declared-but-uncatalogued gate is "
                "refused fail-closed, never a silent enforcement skip.",
            )
    return ()


# --- f-declarative-gate-composition: per-wave gate-stack resolution ----------
#
# OB-1 option (a) / ADR-DGC-001: a wave's gate-IN / gate-OUT stack is declared
# as DATA in the flavor's `wave_gate_stacks.<wave>.{gate-in,gate-out}` block,
# reusing the SAME ordered `GateInvocation` row schema the existing
# `lifecycle_events` event compositions use. The generic PreToolUse /
# SubagentStop handlers resolve the active wave's declared stack off this read
# path (same SSOT subset parser as `resolve_skill_load_set`), then iterate it
# through the EXISTING `dispatch_lifecycle_event` (iterate-in-order,
# halt-at-first-block). An absent block is a declared-empty answer (the wave
# has no declarative stack -> only the wave-agnostic event compositions run),
# NOT a defect — additive coexistence (C8 non-regression).


def resolve_wave_gate_stack(
    flavor_id: str,
    wave: str,
    boundary: str,
    *,
    flavors_dir: Path,
) -> list[dict[str, object]]:
    """Resolve the active wave's declared gate stack for one boundary.

    Reads `flavors_dir/<flavor_id>.yaml` via the SSOT stdlib-only subset parser
    (same path as `dispatch_lifecycle_event` / `resolve_skill_load_set`) and
    returns `wave_gate_stacks[wave][boundary]` as an ordered list of
    `GateInvocation` rows (each a `{gate_id, on_failure, args?}` dict).

    Contract:
      * An absent `wave_gate_stacks` block, an absent `wave` entry, or an absent
        `boundary` sub-key returns the EMPTY list — a declared-empty answer
        (the wave carries no declarative stack), additive coexistence (C8), not
        a defect, not a raise.
      * `boundary` is one of "gate-in" / "gate-out" (the two wave boundaries).
      * The rows are returned as parsed — `dispatch_lifecycle_event` iterates
        them unchanged (reuse, not re-author).
    """
    flavor_doc = _parse_flavor_file(flavors_dir / f"{flavor_id}.yaml")
    wave_gate_stacks = flavor_doc.get("wave_gate_stacks")
    if not isinstance(wave_gate_stacks, dict):
        return []
    wave_block = wave_gate_stacks.get(wave)
    if not isinstance(wave_block, dict):
        return []
    boundary_stack = wave_block.get(boundary)
    if not isinstance(boundary_stack, list):
        return []
    return [row for row in boundary_stack if isinstance(row, dict)]


# --- f-wave-contract-coherence slice-01: registry-sourced gate-stack ---------
#
# ADR-FLOW-006 (D1 registry, D2 gate_stack, D6 dispatcher stack-source = registry
# default): a wave's gate stack is authored ONCE in the canonical, flavor-
# independent wave-contract registry `nWave/waves/<wave>.yaml` (the `gate_stack`
# SSOT-A), and the dispatcher resolves it FROM that registry as the DEFAULT
# source — instead of the flavor-private `wave_gate_stacks` block. Behaviour is
# byte-identical to the flavor-sourced read today (the rows are migrated verbatim,
# same `GateInvocation` row schema). This slice only ADDS the registry read path;
# the flavor `wave_gate_stacks` block is NOT deleted until slice-06.


def resolve_wave_gate_stack_from_registry(
    wave: str,
    boundary: str,
    *,
    waves_dir: Path,
) -> list[dict[str, object]]:
    """Resolve a wave's declared gate stack for one boundary FROM the registry.

    Reads `waves_dir/<wave>.yaml` via the SAME SSOT stdlib-only subset parser the
    flavor read path uses (`_parse_flavor_file` / `des._internal.subset_parser`)
    and returns `gate_stack[boundary]` as an ordered list of `GateInvocation`
    rows (each a `{gate_id, on_failure, args?}` dict).

    This is the flavor-independent SOURCE move (ADR-FLOW-006 D6): the gate-stack
    fact has one authoring locus (the registry) the prose can point at, and the
    rows returned are byte-identical to the flavor-sourced read in force today.

    Contract:
      * An absent registry file, an absent `gate_stack` block, or an absent
        `boundary` sub-key returns the EMPTY list — a declared-empty answer (the
        wave carries no declarative stack at that boundary), not a defect, not a
        raise (mirrors `resolve_wave_gate_stack`'s additive-coexistence contract).
      * `boundary` is one of "gate-in" / "gate-out" (the two wave boundaries).
      * The rows are returned as parsed — the spine iterates them unchanged
        through the SAME `iterate_composition` core (reuse, not re-author).
    """
    registry_file = waves_dir / f"{wave}.yaml"
    if not registry_file.is_file():
        return []
    contract = _parse_flavor_file(registry_file)
    gate_stack = contract.get("gate_stack")
    if not isinstance(gate_stack, dict):
        return []
    boundary_stack = gate_stack.get(boundary)
    if not isinstance(boundary_stack, list):
        return []
    return [row for row in boundary_stack if isinstance(row, dict)]


# --- mode-registry-single-locus slice-01: skill-load-set resolution ----------
#
# The DESIGN-declared D-inject seam (feature-delta `## Wave: DESIGN`, analysis
# §2.3.1): face (c) of the mode 4-tuple — the per-agent conditional skill-load
# set — resolved from the active flavor's `skill_load_set` registry block
# instead of the agent spec's inline table. The registry is the single locus;
# assets reference it, never re-state it.


def resolve_skill_load_set(
    agent_id: str,
    flavor_id: str,
    *,
    flavors_dir: Path,
) -> tuple[str, ...]:
    """Resolve the conditional skill set the active flavor declares for one agent.

    Contract (pinned by the slice-01 acceptance tests):

    * Reads `flavors_dir/<flavor_id>.yaml` via the SSOT stdlib-only subset
      parser (same path as `dispatch_lifecycle_event`) and returns
      `skill_load_set[agent_id].conditional` as a tuple of skill names.
    * A declared-empty entry returns the empty tuple (declared-empty is a
      real answer, distinct from absent).
    * Raises `ValueError` (refusal, fail-closed) when the flavor does not
      properly declare the agent's entry: the `skill_load_set` block or the
      agent row is missing, or `conditional` is not a list of skill names.
      The resolver NEVER improvises an empty answer for a defective
      declaration.
    """
    if flavor_id not in ACTIVE_MODES:
        raise ValueError(_not_executable(flavor_id))
    flavor_doc = _parse_flavor_file(flavors_dir / f"{flavor_id}.yaml")
    agent_row = _declared_agent_row(flavor_doc, agent_id, flavor_id)
    return _declared_conditional_skills(agent_row, agent_id, flavor_id)


def _declared_agent_row(
    flavor_doc: dict[str, object], agent_id: str, flavor_id: str
) -> dict[str, object]:
    """The agent's `skill_load_set` row, or a `ValueError` refusal when absent.

    A missing `skill_load_set` block and a missing agent row are the same
    declaration defect: the flavor does not declare an answer for this agent,
    so the resolver refuses (fail-closed) instead of improvising one.
    """
    skill_load_set = flavor_doc.get("skill_load_set")
    row = skill_load_set.get(agent_id) if isinstance(skill_load_set, dict) else None
    if isinstance(row, dict):
        return row
    raise ValueError(
        f"flavor {flavor_id!r} does not declare a skill_load_set row for "
        f"agent {agent_id!r} -- refusing to improvise a conditional-skill "
        "answer (declaration defect, fail-closed)"
    )


def _declared_conditional_skills(
    agent_row: dict[str, object], agent_id: str, flavor_id: str
) -> tuple[str, ...]:
    """The row's `conditional` list as a skill-name tuple, or a refusal."""
    conditional = agent_row.get("conditional")
    if _is_skill_name_list(conditional):
        return tuple(conditional)
    raise ValueError(
        f"flavor {flavor_id!r} skill_load_set row for agent {agent_id!r} must "
        "declare `conditional` as a list of skill names -- refusing to coerce "
        f"the declared {conditional!r} (declaration defect, fail-closed)"
    )


def _is_skill_name_list(value: object) -> TypeGuard[list[str]]:
    """True when ``value`` is a list whose every member is a skill-name string."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


# --- mode-registry-single-locus slice-02: mode-descriptor resolution ----------
#
# Face (d) of the mode 4-tuple (feature-delta D-project, analysis §2.2): the
# mode's human-readable descriptor + DELIVER phase shape — the factual core of
# the prose docgen projects into `GENERATED:mode-descriptor` regions. Same
# registry-read SSOT as `resolve_skill_load_set` (one read path, two
# consumers: gates + docgen); same fail-closed refusal contract.


@dataclass(frozen=True)
class ModeDescriptor:
    """The registry-declared prose core of one workflow mode.

    Attributes:
        descriptor: One-line human-readable mode description (registry
            `descriptor` field, folded scalar stripped to a single line).
        deliver_phase_shape: The DELIVER-wave phase shape rendered beside the
            descriptor (registry `deliver_phase_shape` field).
    """

    descriptor: str
    deliver_phase_shape: str


def resolve_mode_descriptor(flavor_id: str, *, flavors_dir: Path) -> ModeDescriptor:
    """Resolve the descriptor prose the registry declares for one mode.

    Reads `flavors_dir/<flavor_id>.yaml` via the SSOT stdlib-only subset
    parser (same path as `resolve_skill_load_set`). Raises `ValueError`
    (refusal, fail-closed) when the flavor does not declare `descriptor` or
    `deliver_phase_shape` as non-empty prose — the resolver NEVER improvises
    a descriptor for a defective declaration.
    """
    if flavor_id not in ACTIVE_MODES:
        raise ValueError(_not_executable(flavor_id))
    flavor_doc = _parse_flavor_file(flavors_dir / f"{flavor_id}.yaml")
    return ModeDescriptor(
        descriptor=_declared_prose(flavor_doc, "descriptor", flavor_id),
        deliver_phase_shape=_declared_prose(
            flavor_doc, "deliver_phase_shape", flavor_id
        ),
    )


def _declared_prose(
    flavor_doc: dict[str, object], field_name: str, flavor_id: str
) -> str:
    """The named field as stripped non-empty prose, or a refusal."""
    value = flavor_doc.get(field_name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(
        f"flavor {flavor_id!r} does not declare {field_name!r} as non-empty "
        "prose -- refusing to project an improvised mode descriptor "
        "(declaration defect, fail-closed)"
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
