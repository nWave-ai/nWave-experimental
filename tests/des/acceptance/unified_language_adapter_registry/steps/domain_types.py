"""Domain types for the unified-language-adapter-registry slice-02 ATs.

SSOT-via-types (Mandate-12 criterion 1): the closed observables the 3
scenarios pin are expressed as typed value objects, not raw dict/str, so step
bodies stay typed lookups + a composition call (criterion 3).

This module imports NO not-yet-created production name (no
``scripts.install.plugins.nwave_lang_python``, no
``des.adapters.driven.{contract_gate,e2e,robustness}.*``) — pure value-object
declaration, collection-safe at HEAD.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractGateRunObservable:
    """Port-exposed observable captured from driving the REAL contract-gate CLI.

    ``exit_code`` / ``stdout`` / ``stderr`` are the raw captured child-process
    observables. The remaining fields are parsed FROM the gate's own emitted
    ``ContractGateResult`` JSON event (never fabricated by the test):

    * ``event_found`` -- True iff a well-formed ``ContractGateResult`` JSON
      event was found on the child's stdout.
    * ``routed_via_registered_adapter`` -- the DISTILL-pinned discriminating
      field (feature-delta ``[REF] Open questions`` resolution): True iff the
      gate routed through a REGISTERED ``ContractGatePort`` facet rather than
      falling through to the hardcoded pytest path. Absent at HEAD (the field
      does not exist yet on the fallback event) -> parsed as False.
    * ``runner`` -- the resolved tool-name the event names (mirrors
      ``RunVerdict.runner``), or ``None`` if the event carries none.
    * ``pytest_exit_code`` -- the underlying pytest exit code the event
      carries (present on both the fallback and the registered-adapter path
      once DELIVER extends the seam to emit it -- the behavior-parity oracle).
    * ``passed`` -- the event's own pass/fail judgement, or ``None`` if absent.
    * ``child_import_ok`` -- True iff the child process's import of
      ``nwave_lang_python`` (and, transitively, the 3 new adapter modules)
      succeeded. At HEAD this is False (module absent) -- the primary RED
      signal for Scenario 1/2.
    """

    exit_code: int
    stdout: str
    stderr: str
    event_found: bool
    routed_via_registered_adapter: bool
    runner: str | None
    pytest_exit_code: int | None
    passed: bool | None
    child_import_ok: bool


@dataclass(frozen=True)
class RegistrySlotResolution:
    """Which of the 3 new ``LanguageAdapterRegistry`` slots resolved after ONE
    ``register_adapters`` call (the unification pin, DDD-U2/DDD-U5).

    ``child_import_ok`` mirrors ``ContractGateRunObservable`` -- False at HEAD
    because ``nwave_lang_python`` does not exist yet.
    """

    child_import_ok: bool
    contract_gate_resolved: bool
    environmental_e2e_resolved: bool
    robustness_density_resolved: bool
