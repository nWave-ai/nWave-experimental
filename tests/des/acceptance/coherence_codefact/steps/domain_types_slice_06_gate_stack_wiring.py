"""Typed domain vocabulary for the f-coherence-and-attestation slice-06 ATs.

slice-06 (the WIRING slice, JOB-028 / closing `catalogato ≠ cablato`): the three
already-built feature modules — the mechanical gate-G (slice-03,
``src/des/cli/gate_g.py``), the self-attest verdict layer (slice-04,
``src/des/domain/self_attest.py``), and the per-language test-runner port
(slice-05, ``src/des/cli/run_tests.py``) — are CONNECTED into the gate-stack so a
maintainer can actually REACH them and the closure scorecard sees the feature
WIRED. The modules SHIP; this slice makes them FIRE.

Three witnessing axes (the scorecard's two-leg ``_module_wired`` + behavioural drive):
  (1) REGISTRATION — each of ``gate-g`` / ``self-attest`` / ``verify-test-runner``
      is a registered ``des`` subcommand (a ``_SubcommandRow`` in
      ``src/des/cli/__main__.py:_REGISTRY``, advertised by ``des --help``); the
      catalog ``nWave/gates/_catalog.yaml`` carries the 1:1 mirror row.
  (2) GATE-STACK REFERENCE — each subcommand name is referenced in a
      ``nWave/flavors/*.yaml`` gate-stack surface, so the scorecard's
      ``_term_wired`` leg passes (the EXACT regex the goal-contract uses). This is
      the literal ``catalogato ≠ cablato`` closure: a catalogued-but-unreferenced
      module is NOT wired.
  (3) BEHAVIOURAL WIRING — invoking each ``des <subcommand>`` actually DRIVES the
      existing domain logic and emits a §17 ``GateVerdict``-shaped result (no
      domain re-implementation; the CLI wrapper is a thin driver over the
      slice-03/04/05 logic).

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-06
Gherkin names is expressed once here as a typed enum / frozen dataclass, so the
composition methods consume typed parameters (no raw ``str`` where an enum
exists). The DSL emerges from these typed concepts — the registration + reference
scenarios range over the ONE ``WiredModule`` enum (a ``@parametrize``-shaped
Scenario Outline), not over decorator proliferation.

slice-06 REUSES the §17 GateVerdict set (ADR-GV-001, CONSUMED unchanged, no sixth
— C6). These types are TEST-LOCAL (they never import production code) — the ATs
drive the SUT only through the real ``des`` subprocess / the shipped flavor YAML
artifact (Mandate-13 driving-port-only).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# §17 GateVerdict -- the FIVE verdicts (ADR-GV-001), CONSUMED unchanged. No
# sixth (C6). The AT-side mirror; the wire tokens are byte-identical to the
# production enum's `.value`s. The behavioural-wiring ATs assert the driven
# subcommand emits a verdict token in this LOCKED set.
# ---------------------------------------------------------------------------


class GateVerdict(Enum):
    """The §17 uniform-failure-machine verdict set (ADR-GV-001, 5 verdicts)."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"
    INDETERMINATE = "indeterminate"


# The LOCKED §17 verdict-token set -- a driven subcommand must emit ONE of these,
# never a sixth (C6).
LOCKED_GATE_VERDICTS: frozenset[str] = frozenset(v.value for v in GateVerdict)


# ---------------------------------------------------------------------------
# slice-06 scenario vocabulary -- the three feature modules being wired, keyed
# by the operator-visible `des` subcommand name + the scorecard `_term_wired`
# regex each must satisfy. ONE enum so the registration + reference Scenario
# Outlines range over the modules, not decorators (Mandate-12 DSL emergence).
# ---------------------------------------------------------------------------


class WiredModule(Enum):
    """A feature module slice-06 connects into the gate-stack.

    The wire token is the operator-visible ``des`` subcommand name the scorecard's
    ``_module_wired`` first leg demands (the registry SSOT
    ``src/des/cli/__main__.py:_REGISTRY``). Each value is the EXACT subcommand
    name the closure scorecard maps the module to (``scripts/flow_v2_closure_
    scorecard.py:_module_wired``): ``gate-design-at-coherence`` / ``self-attest`` /
    ``verify-test-runner`` (f-distill-wiring-to-registry slice-02 reconciles the
    ``gate-g -> gate-design-at-coherence`` rename f-code-design-manifest-and-gate-g
    slice-04 shipped; the live ``des`` dispatcher carries ``gate-design-at-coherence``).

    GATE_G            -- the mechanical design↔AT coherence gate (slice-03 module
                         ``src/des/cli/gate_g.py``, the ``evaluate_gate_g``
                         callable; subcommand RENAMED to ``gate-design-at-coherence``
                         by f-code-design-manifest-and-gate-g slice-04, module path
                         unchanged). DISTILL gate-OUT #5 (flow-v2-design §12).
    SELF_ATTEST       -- the self-attest verdict layer (slice-04 module
                         ``src/des/domain/self_attest.py``, the ``classify``
                         callable). The verdict-validity layer (D9).
    VERIFY_TEST_RUNNER -- the per-language test-runner port driver (slice-05
                         module ``src/des/cli/run_tests.py``, the ``main`` entry).
                         The test-execution port (§V / D8).
    """

    GATE_G = "gate-design-at-coherence"
    SELF_ATTEST = "self-attest"
    VERIFY_TEST_RUNNER = "verify-test-runner"


@dataclass(frozen=True)
class WiredModuleSpec:
    """The full wiring contract for one module: subcommand name + the scorecard
    ``_term_wired`` regex it must satisfy in a flavor gate-stack surface.

    ``subcommand``    -- the operator-visible ``des`` subcommand name (the
                         registry first leg).
    ``term_pattern``  -- the EXACT regex the closure scorecard's ``_term_wired``
                         leg searches each ``WIRING_FILES`` entry for
                         (``scripts/flow_v2_closure_scorecard.py:218-222``). A
                         catalogued subcommand whose name (or a ``_term_wired``-
                         matching token) appears in NO flavor gate-stack is NOT
                         wired — the ``catalogato ≠ cablato`` failure this slice
                         closes.
    """

    module: WiredModule
    subcommand: str
    term_pattern: str


# The slice-06 wiring table -- CONTENT-DISTINCT per row. The term_pattern strings
# are byte-identical to the closure scorecard's `_module_wired` patterns
# (scripts/flow_v2_closure_scorecard.py:301-303) so the reference AT witnesses the
# EXACT closure leg the goal-contract measures, not a paraphrase. The gate-G row
# carries the POST-RENAME pattern `gate.?design.?at.?coherence` (the live
# `des gate-design-at-coherence` subcommand) -- f-distill-wiring-to-registry
# slice-02 reconciliation of the f-code-design slice-04 rename.
WIRED_MODULE_SPECS: tuple[WiredModuleSpec, ...] = (
    WiredModuleSpec(
        module=WiredModule.GATE_G,
        subcommand="gate-design-at-coherence",
        term_pattern=r"gate.?design.?at.?coherence",
    ),
    WiredModuleSpec(
        module=WiredModule.SELF_ATTEST,
        subcommand="self-attest",
        term_pattern=r"self.?attest|self_attest",
    ),
    WiredModuleSpec(
        module=WiredModule.VERIFY_TEST_RUNNER,
        subcommand="verify-test-runner",
        term_pattern=r"test.?runner|test_runner",
    ),
)

# Lookup by the Gherkin Scenario-Outline parameter token (the subcommand name).
SPEC_BY_SUBCOMMAND: dict[str, WiredModuleSpec] = {
    spec.subcommand: spec for spec in WIRED_MODULE_SPECS
}


# An UNKNOWN subcommand name — deliberately NOT in the gate-stack wiring set and
# unlikely to collide with any real `des` row — used by the C6 robustness AT-27 to
# pin the closed-set rejection contract (the dispatcher rejects it as invalid).
# Modelled as a WiredModuleSpec so the registration probe is REUSED unchanged; its
# term_pattern is a never-matching regex (the unknown name has no module, never
# wired by design).
UNKNOWN_SUBCOMMAND_SPEC: WiredModuleSpec = WiredModuleSpec(
    module=WiredModule.GATE_G,  # placeholder; AT-27 reads only `.subcommand`
    subcommand="__nwave_unregistered_subcommand__",
    term_pattern=r"(?!x)x",  # never matches — the unknown name is wired nowhere
)


# ---------------------------------------------------------------------------
# slice-06 observable vocabulary -- port-exposed snapshots the ATs assert on.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubcommandRegistration:
    """The observable slice of "is ``des <subcommand>`` registered?" (AT-20/21/22).

    Port-exposed names only (Mandate-8 universe discipline): the observable is
    WHETHER the real ``des`` dispatcher resolves the subcommand (exit 0 / the name
    advertised by ``des --help``) vs rejects it (argparse invalid-choice exit 2)
    — read from the REAL subprocess, never an internal ``_REGISTRY`` attribute.

    ``advertised``   -- the subcommand name appears in ``des --help`` stdout.
    ``resolvable``   -- ``des <subcommand> --help`` exits 0 (the dispatcher
                        resolved + delegated to the module) rather than argparse
                        exit 2 (invalid choice — unregistered).
    ``in_catalog``   -- the 1:1 catalog mirror row exists in
                        ``nWave/gates/_catalog.yaml`` (the registry-catalog parity
                        the single_entry_point arch test enforces).
    """

    advertised: bool
    resolvable: bool
    in_catalog: bool


@dataclass(frozen=True)
class GateStackReference:
    """The observable slice of "is ``<subcommand>`` referenced in a flavor
    gate-stack?" (AT-23) — the literal ``catalogato ≠ cablato`` closure leg.

    Port-exposed names only: WHETHER the scorecard's ``_term_wired`` regex for the
    module matches the text of at least one ``WIRING_FILES`` flavor surface
    (``nWave/flavors/*.yaml``) — read from the REAL shipped flavor YAML, never an
    inline test string (Mandate-13 prose-surface: assert a shipped artifact).

    ``term_wired``        -- the module's ``_term_wired`` regex matches ≥1 flavor
                             YAML (the EXACT scorecard leg).
    ``referenced_in``     -- the flavor file basenames the reference was found in
                             (diagnostic; ``()`` when unwired).
    """

    term_wired: bool
    referenced_in: tuple[str, ...]


@dataclass(frozen=True)
class DrivenVerdict:
    """The observable slice of driving ``des <subcommand>`` end-to-end (AT-24/25/26).

    Port-exposed names only: the §17 ``GateVerdict``-shaped result the driven
    subcommand emits — proving the thin CLI wrapper actually DRIVES the existing
    slice-03/04/05 domain logic (no re-implementation), and the result is one of
    the LOCKED five (no sixth, C6).

    ``verdict``      -- the §17 GateVerdict token the driven subcommand emitted
                        (from gate-G's envelope / self-attest's classification /
                        the runner port's test-result-or-unobserved status).
                        ``None`` when the subcommand is unregistered / emitted no
                        verdict-shaped result (the active-RED signal).
    ``exit_code``    -- the process exit code (verbatim passthrough, DDD-6) — a
                        secondary observable proving the dispatcher delegated.
    ``drove_domain`` -- the driven result is structurally the slice-03/04/05
                        domain output (a verdict token / a result envelope),
                        proving the wrapper is a thin driver over existing logic,
                        not a re-implementation.
    """

    verdict: str | None
    exit_code: int | None
    drove_domain: bool
