"""L2 — the AUTHORED automation/driver layer for the slice-01 two-layer structure.

DESIGN CORRECTION (2026-06-22b, DDD-1C..DDD-5C/8C/10C). This is the lower of the two
authored layers (Gojko/GOOS canon): the L1 business-language scenarios (the WHAT)
sit ON TOP of this driver layer (the HOW). The driver owns EVERY implementation
specific — subprocess invocation, argv, exit code, JSON verdict parse — so the L1
scenarios name observable business outcomes only and survive an implementation
refactor untouched (DDD-1C/10C, Finding 1.2). There is NO generic engine and NO
vocabulary/bindings config (DDD-1R..4R superseded; `generic_framework.py` removed
by DELIVER, not imported here).

The two-layer seam is the `GatewayDriver` PROTOCOL (DDD-3C, GOOS ProtocolDriver
interface, Finding 1.10): the test DSL depends only on this INTERFACE, never on a
concrete. `SlicePlanGateDriver` is the per-language CONCRETE driver (the nWave-impl
is Python → a subprocess driver over the shipped `des` gate). A second concrete
driver could drive the same gate through a different invocation surface without
touching the L1 scenarios — exactly what the refactor-resilience scenario exercises.

DRIVING PORT (Mandate-13, Layer 3 subprocess composition root): the SHIPPED
`python -m des validate-feature-delta --require-slice-plan --format=json` gate is the
SUT, driven SUBCUTANEOUSLY (below any UI). The subprocess IS the SUT; no production
module is imported and called at the step boundary. Feature-delta fixtures are
hermetic under tmp_path; the assertions read a closed verdict token + exit code only
(git-free, Python-only).

Active-RED (ADR-025/028, atdd_pure): at HEAD the AUTHORED concrete driver
`SlicePlanGateDriver` is a SCAFFOLD — `_invoke_gate` raises AssertionError
(MISSING_FUNCTIONALITY) the moment a step drives the gate. The shipped gate already
exists, so DELIVER's A_GREEN AUTHORS the driver body (build the fixture → run the
real subprocess → parse the closed verdict) to turn the scaffold green; it does NOT
unskip anything and it does NOT change the L1 scenarios.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .domain_types import (
    PRODUCTION_VERDICT_FOR_SHAPE,
    SlicePlanShape,
    shape_is_accepted,
)


if TYPE_CHECKING:
    from collections.abc import Mapping


class GateVerdictObservation(Protocol):
    """The observable surface the L1 'Then' steps assert against (DDD-10C read-only).

    A read-only view of one gate run — the verdict TOKEN the gate spoke (a raw `str`
    PARSED from real gate output, drawn from the gate's production verdict Universe)
    and whether it accepted. It exposes NO mutation method (a query step cannot mutate
    gate state): the driver splits drive (When) from observe (Then). The L1 step bodies
    read `verdict` / `accepted`, never an exit code or stdout (those are L2 internals).
    The verdict is a `str` (the gate's own token), NOT a test-side enum — so the
    assertion compares the REAL observed token against the gate's PRODUCTION constant.
    """

    @property
    def verdict(self) -> str: ...

    @property
    def accepted(self) -> bool: ...


class GatewayDriver(Protocol):
    """The two-layer SEAM — the ProtocolDriver INTERFACE the L1 DSL depends on (DDD-3C).

    The L1 business-language steps depend ONLY on this interface, never on a concrete
    driver. A maintainer authors a feature-delta of a given slice-plan SHAPE, submits
    it to the gate, and observes the gate's verdict — all in business terms. Every
    implementation specific (how the feature-delta is built, how the gate is invoked,
    how the verdict is parsed) lives BELOW this seam, in the concrete driver. Swapping
    the concrete (the refactor-resilience scenario) leaves L1 untouched.
    """

    def author_feature_delta(self, tmp_path: Path, shape: SlicePlanShape) -> None: ...

    def submit_to_slice_plan_gate(self) -> None: ...

    def last_observation(self) -> GateVerdictObservation: ...


class SlicePlanGateDriver:
    """L2 concrete driver (adapter): drives the SHIPPED slice-plan gate subcutaneously.

    The per-language (Python) concrete behind `GatewayDriver`. It builds a hermetic
    feature-delta of the requested slice-plan SHAPE, runs the real
    `des validate-feature-delta --require-slice-plan --format=json` gate as a
    subprocess, and exposes the closed verdict + accept decision as a read-only
    observation. Multiple authored deltas (the reuse scenario) and a refactored
    invocation surface (the refactor-resilience scenario) are supported by re-driving
    through the SAME interface — the L1 steps never see the difference.

    Active-RED at HEAD: `_invoke_gate` is the single unimplemented seam. Every public
    method is wired; only the actual gate invocation raises (MISSING_FUNCTIONALITY).
    """

    def __init__(self) -> None:
        self._deltas: list[Path] = []
        self._observations: list[_Observation] = []
        self._refactored_surface: bool = False
        self._property_scenario: bool = False

    # -- L1 'Given' surface ---------------------------------------------------

    def note_property_scenario(self) -> None:
        """Mark the property scenario's precondition (a recognised shape exists).

        A marker only — the per-shape sweep over the closed `SlicePlanShape` Universe
        is driven by the property's Then steps. Kept on the driver (not a step-local
        flag) so the harness is the single SSOT for the scenario's state.
        """
        self._property_scenario = True

    def author_feature_delta(self, tmp_path: Path, shape: SlicePlanShape) -> None:
        """A maintainer authors a feature-delta of the given slice-plan shape.

        DELIVER A_GREEN authors the fixture body here (render a feature-delta whose
        Slice Plan section has the requested shape into a hermetic tmp_path) and
        appends its path. At HEAD nothing is built yet — but authoring is a pure
        arrangement, so it does not itself raise; the RED fires when the gate is
        driven (the right reason is MISSING_FUNCTIONALITY at the gate, not setup).
        """
        slot = len(self._deltas)
        delta_path = self._render_feature_delta(tmp_path, shape, slot)
        self._deltas.append(delta_path)

    def use_refactored_invocation_surface(self) -> None:
        """Re-point the driver at a refactored gate invocation surface (DDD-1C/10C).

        The refactor-resilience scenario: the gate's implementation is exercised
        through a different invocation surface (the same SUT, a refactored seam). This
        flips a driver-internal flag only — it is entirely BELOW the two-layer seam, so
        the L1 scenarios that assert the business outcome stay byte-identical.
        """
        self._refactored_surface = True

    # -- L1 'When' surface ----------------------------------------------------

    def submit_to_slice_plan_gate(self) -> None:
        """Submit every authored feature-delta to the gate, recording each verdict."""
        self._observations = [self._invoke_gate(delta) for delta in self._deltas]

    # -- L1 'Then' surface (read-only observation) ----------------------------

    def last_observation(self) -> _Observation:
        assert self._observations, "no feature-delta was submitted to the gate"
        return self._observations[-1]

    def all_observations(self) -> list[_Observation]:
        assert self._observations, "no feature-delta was submitted to the gate"
        return self._observations

    # -- L2 internals (the HOW; the only RED seam) ----------------------------

    def _render_feature_delta(
        self, tmp_path: Path, shape: SlicePlanShape, slot: int
    ) -> Path:
        """Render a feature-delta whose Slice Plan section has the requested shape.

        Each shape is rendered KNOWN-BY-CONSTRUCTION to drive the shipped gate to one
        verdict: WELL_FORMED -> the canonical `## Wave: DISCUSS / [REF] Slice Plan`
        heading + the fixed five-column header + a value-bearing row -> `accepted`;
        NO_PLAN -> a feature-delta carrying NO slice-plan section -> `missing-slice-plan`;
        MALFORMED -> the heading + a table whose header is not the fixed five columns ->
        `malformed-slice-plan`; INFRA_ONLY -> the heading + a five-column table whose
        EVERY data row is annotated `@infrastructure` -> `rejected-infra-only`. The
        returned path is a real hermetic file under tmp_path the subprocess gate reads.
        """
        tmp_path.mkdir(parents=True, exist_ok=True)
        delta_path = tmp_path / f"feature-delta-{slot}.md"
        delta_path.write_text(_FEATURE_DELTA_BODY[shape], encoding="utf-8")
        return delta_path

    def _invoke_gate(self, delta_path: Path) -> _Observation:
        """Drive the SHIPPED slice-plan gate subcutaneously and read its verdict.

        Active-RED: the gate invocation is the single unimplemented seam. DELIVER
        A_GREEN authors this to run `python -m des validate-feature-delta
        --require-slice-plan --format=json <delta_path>` (or the refactored surface
        when `self._refactored_surface`), parse the closed verdict token + exit code,
        and return a read-only `_Observation`. Today it raises cleanly so the right
        reason is MISSING_FUNCTIONALITY at the gate, never an ImportError.
        """
        argv = self._gate_argv(delta_path)
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
        )
        verdict = json.loads(completed.stdout)["verdict"]
        return _Observation(verdict=verdict, accepted=completed.returncode == 0)

    def _gate_argv(self, delta_path: Path) -> list[str]:
        """The shipped slice-plan gate invocation (the subcutaneous driving surface).

        The primary surface drives the gate through the `des` subcommand dispatcher
        (`python -m des validate-feature-delta ...`); the refactored surface (DDD-1C/10C)
        drives the SAME shipped gate code through the validator module's OWN entry point
        (`python -m des.cli.validate_feature_delta ...`), which takes no subcommand token.
        Both run THIS checkout's gate; they differ only in the invocation seam — the L1
        business outcome is identical, demonstrating refactor-resilience below the seam.
        """
        common = ["--require-slice-plan", "--format=json", str(delta_path)]
        if self._refactored_surface:
            return [sys.executable, "-m", "des.cli.validate_feature_delta", *common]
        return [sys.executable, "-m", "des", "validate-feature-delta", *common]


class _Observation:
    """A read-only observation of one gate run (implements GateVerdictObservation).

    A frozen view DELIVER's authored driver returns from `_invoke_gate`: the verdict
    TOKEN the gate spoke, PARSED from the real `--format=json` gate output (a raw
    `str`, the gate's own token — NOT a test-side enum), and whether the gate accepted
    (derived from the real exit code). Authored here as the L2 return shape so the L1
    'Then' steps have a stable read-only surface (verdict + accepted) independent of
    the gate's transport. Because the token is parsed from real output, DELIVER cannot
    satisfy the property by returning a test constant by lookup — it must run the gate.
    """

    def __init__(self, verdict: str, accepted: bool) -> None:
        self._verdict = verdict
        self._accepted = accepted

    @property
    def verdict(self) -> str:
        return self._verdict

    @property
    def accepted(self) -> bool:
        return self._accepted


#: The correctness oracle re-exported for the property step (DDD-5C): the PRODUCTION
#: verdict each constructed shape determines + the accept rule, both anchored to the
#: gate's published constants in `domain_types` (NOT a test-authored verdict string).
#: The property reads these as the expectation; the OBSERVATION is parsed from the
#: real gate — input built test-side, verdict observed from production: non-tautological.
EXPECTED_VERDICT: Mapping[SlicePlanShape, str] = PRODUCTION_VERDICT_FOR_SHAPE
expected_accept = shape_is_accepted


#: The canonical slice-plan section heading the shipped gate matches
#: (`_SLICE_PLAN_HEADING_RE`); a value-bearing row + the fixed five-column header.
_WELL_FORMED_DELTA = (
    "## Wave: DISCUSS / [REF] Slice Plan\n"
    "\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
    "| slice-01 | A maintainer authors a sustainable AT | pending | "
    "@walking-skeleton | keystone slice |\n"
)

#: NO slice-plan section at all -> the gate emits `missing-slice-plan`. A single
#: conforming non-slice-plan Wave heading keeps the heading-form check green so the
#: verdict is the absence of the plan, not a malformed heading.
_NO_PLAN_DELTA = (
    "## Wave: DISCUSS / [REF] Context\n"
    "\n"
    "This feature-delta carries no Slice Plan section.\n"
)

#: The canonical heading but a table header that is NOT the fixed five columns ->
#: the gate emits `malformed-slice-plan`.
_MALFORMED_DELTA = (
    "## Wave: DISCUSS / [REF] Slice Plan\n"
    "\n"
    "| Slice | Value | Status |\n"
    "|---|---|---|\n"
    "| slice-01 | wrong column shape | pending |\n"
)

#: The canonical heading + the fixed five columns, but EVERY data row is annotated
#: `@infrastructure` -> the MECC floor emits `rejected-infra-only`.
_INFRA_ONLY_DELTA = (
    "## Wave: DISCUSS / [REF] Slice Plan\n"
    "\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
    "| slice-01 | Deploy shared infra | shipped | @infrastructure | CI runner setup |\n"
    "| slice-02 | Configure pipeline | pending | @infrastructure | Pipeline wiring |\n"
)

#: The hermetic feature-delta body each constructed slice-plan SHAPE renders to. Each
#: body is KNOWN BY CONSTRUCTION to drive the shipped gate to the verdict
#: `PRODUCTION_VERDICT_FOR_SHAPE` names for that shape — the test builds the INPUT; the
#: gate's OBSERVED verdict is read from real output (non-tautological per the Sentinel
#: fix). The full `SlicePlanShape` Universe is keyed so the property sweep covers all.
_FEATURE_DELTA_BODY: Mapping[SlicePlanShape, str] = {
    SlicePlanShape.WELL_FORMED: _WELL_FORMED_DELTA,
    SlicePlanShape.NO_PLAN: _NO_PLAN_DELTA,
    SlicePlanShape.MALFORMED: _MALFORMED_DELTA,
    SlicePlanShape.INFRA_ONLY: _INFRA_ONLY_DELTA,
}
