"""Clause witness port (driven) -- behavioral witness-check seam (slice-03).

WHY-NEW-FILE: src/des/ports/clause_witness_port.py
  CLOSEST-EXISTING: src/des/ports/driven_ports/audit_log_writer.py
  EXTENSION-COST: audit_log_writer models an append-only event sink; this port
    models a behavioral differential (run a claimed AT against an unperturbed
    and a perturbed isolated copy, discriminate the failure reason). The two
    share nothing beyond being driven Protocols -- folding a witness method into
    the audit writer would couple two unrelated driven concerns.
  PARALLEL-RATIONALE: architecture.md sec.4 "Port contract" adjudicated this as
    a CREATE_NEW driven port (`ClauseWitnessPort.witness` + `.probe`) with its
    own value-shape (`WitnessReport`); it has an incompatible signature
    (clause + at_refs -> WitnessReport) and a distinct lifecycle (the gate
    injects it; the adapter holds a sandbox-root capability the audit writer
    never has).

The port is the language-agnostic seam (ADR-001 / architecture.md sec.4):
only the AST-perturbation + test-run steps are language-bound, and they sit
behind this Protocol. The Python realization is ``PerturbationWitnessAdapter``;
future ``nwave-lang-{ts,go,rust}`` plugins implement the same Protocol so D8
coverage grows without touching the gate logic.

The port is read+probe only -- it exposes NO method that mutates the live tree.
"The gate corrupted my source" is non-representable: the adapter holds only a
sandbox root capability (ADR-001 §Consequences, effect-isolation principle 12).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ATRef:
    """A claimed witnessing acceptance test for a clause (a Plan-value).

    ``scenario`` names the enclosing ``Scenario:`` carrying the ``# clause:``
    comment; ``target`` is the co-located ``# target: module::symbol`` carrier;
    ``at_path`` is the executable AT module the witness-check actually runs
    (baseline + perturbed).
    """

    scenario: str
    target: str
    at_path: str


@dataclass(frozen=True)
class WitnessReport:
    """The behavioral witness verdict for one clause (a Plan-value).

    ``evidence`` is one of ``witnessed`` | ``survived`` |
    ``red-for-wrong-reason:<exc>`` | ``baseline-not-green`` |
    ``target-unresolved`` -- every ``unwitnessed`` verdict tells the operator
    WHY, and the gate report surfaces it (ADR-001 §Decision).

    ``sandbox_observed`` is the earned-trust observable (binding residue R1):
    True iff the adapter actually made an isolated copy + ran the differential.
    A no-perturbation impl that passed DT-8 byte-identity trivially would leave
    this False -- so byte-identity is non-trivially witnessed (the copy WAS
    made; the live source WAS untouched because perturbation hit the copy).
    """

    clause_id: str
    witnessed: bool
    evidence: str
    sandbox_observed: bool = False


@dataclass(frozen=True)
class ProbeReport:
    """The earned-trust self-test verdict (principle 13).

    ``ok`` is True iff the adapter classifies its four toy ATs correctly (the
    discrimination ceiling, not just the floor). On ``ok == False`` the gate
    degrades to a loud INDETERMINATE syntactic-only warning, never silent-pass.
    """

    ok: bool
    detail: str


@runtime_checkable
class ClauseWitnessPort(Protocol):
    """Behavioral witness-check seam (ADR-001 isolated-copy differential).

    The verdict logic in ``DecisionTableTraceabilityGate`` depends on this
    Protocol, never on a concrete adapter -- keeps the witness mechanism
    swappable per language and the gate pure + language-neutral.
    """

    def witness(self, clause_id: str, at_refs: list[ATRef]) -> WitnessReport:
        """Return the behavioral witness verdict for ``clause_id``.

        ``witnessed`` REQUIRES the three-condition differential (ADR-001 §6):
        baseline GREEN AND perturbed FAILING AND the failure is a semantic
        AssertionError raised in the AT body (not an import/setup/runtime error
        from the perturbation site). Anything else is ``unwitnessed`` with a
        reason-specific evidence string.
        """
        ...

    def probe(self) -> ProbeReport:
        """Self-test the adapter's discrimination (earned-trust, principle 13)."""
        ...
