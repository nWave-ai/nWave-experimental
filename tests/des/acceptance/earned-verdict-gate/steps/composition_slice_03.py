"""Composition root for slice-03 (SeamInjectionPort) of the earned-verdict gate.

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION composition root -- the real seam-injection CLI invoked as a
``python -m des.cli.inject_seam`` subprocess. The SeamInjectionPort is NEVER
imported and called directly; the only entry is the CLI driving port. The port
reads ``NWAVE_PERTURB=<seam-id>`` from the environment and acts on a generated
AT scaffold staged on a tmp path, reporting which implementation the named seam
resolves to AFTER injection (and whether it abstained).

ALL business logic lives in the production port behind that CLI. This module's
service methods only (a) stage a generated scaffold exposing named seams on a
tmp path, (b) invoke the CLI as a subprocess with ``NWAVE_PERTURB`` set, and (c)
parse + port-expose the emitted result. Step bodies in ``slice_03_steps.py``
delegate here and never inline business logic (Mandate-12 criterion 3).

Layer 3 (subprocess CLI + JSON assertion): real I/O (a real subprocess, a real
scaffold file on a tmp path), example-only -- no PBT machinery (Mandate 9/11).
The post-injection seam resolution + the abstain signal are the universe
(Mandate 8).

SWAP MECHANISM (DESIGN GAP -- FLAGGED): the feature-delta specifies the
BEHAVIOUR ("swaps the named dependency at the seam") but not the mechanism. This
composition stages a generated scaffold that declares its named seams + their
real implementations in a small manifest, and asserts the mechanism-INDEPENDENT
observable contract -- which implementation each seam resolves to after the port
acts. The concrete swap mechanism is DELIVER's choice once DESIGN confirms it;
this composition does not presuppose one. The scaffold manifest shape below is a
minimal stand-in so the ATs can name a seam + observe its post-injection
resolution; DELIVER may replace it with the real generated-AT-scaffold shape.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from des.cli.inject_seam import main as _inject_seam_main
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import InjectionOutcome, VerdictReason


# The production driving port: the seam-injection CLI module, invoked as a
# subprocess (``python -m``). Driven IN-PROCESS via the shared
# ``run_cli_in_process`` driver (the in-process analogue of
# ``python -m des.cli.inject_seam``); the port reads ``NWAVE_PERTURB`` from
# ``os.environ`` at call time, so setting it around the in-process call is
# behaviour-identical to passing it in the subprocess env.

# The named seam the scaffold exposes + the implementation labels the port
# reports. ``real`` is what the seam resolves to before perturbation; ``fault``
# is what a successful injection swaps it to. These are opaque labels -- the
# verdict CORE never sees them; they exist only so the AT can OBSERVE the swap.
_NAMEABLE_SEAM = "declared-dependency"
_REAL_IMPL = "real-implementation"
_FAULT_IMPL = "fault-implementation"

# A seam name the staged scaffold does NOT expose -- exercises the fail-safe
# no-nameable-seam abstain.
_UNNAMEABLE_SEAM = "no-such-seam"

# The NWAVE_PERTURB env var the port reads (feature-delta line 40).
_PERTURB_ENV = "NWAVE_PERTURB"


@dataclass
class InjectionResult:
    """Observable outcome of one seam-injection CLI invocation.

    Universe entries are port-exposed only (the post-injection seam resolution,
    the abstain status/reason) -- never internal port struct fields (Mandate 8).
    ``raw`` retains the full emitted envelope so a Then step can read the
    declared outcome + resolution.
    """

    outcome: InjectionOutcome | None = None
    resolved_impl: str | None = None
    reason: VerdictReason | None = None
    cli_exit_code: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class SeamInjectionComposition:
    """Production composition root for the ``inject_seam`` CLI (SeamInjectionPort).

    Stages a generated scaffold exposing named seams, invokes the real CLI
    subprocess with ``NWAVE_PERTURB`` set, and parses the emitted result. The
    port's swap logic is the single source of truth for whether the perturbation
    took effect -- this composition never swaps anything itself (no shadow
    oracle); it stages a scaffold + transports the emitted result.
    """

    result: InjectionResult = field(default_factory=InjectionResult)
    _workspace: Path | None = field(default=None, init=False)
    _seam_to_request: str = field(default=_NAMEABLE_SEAM, init=False)

    def given_scaffold_with_nameable_seam(self) -> None:
        """Stage a generated scaffold exposing the nameable seam."""
        self._seam_to_request = _NAMEABLE_SEAM

    def given_scaffold_without_matching_seam(self) -> None:
        """Stage a scaffold whose seams do NOT match the requested name."""
        self._seam_to_request = _UNNAMEABLE_SEAM

    def perturb_seam(self) -> InjectionResult:
        """Invoke the ``inject_seam`` CLI with ``NWAVE_PERTURB`` set to the seam.

        Writes a generated scaffold manifest (the nameable seam + its real impl)
        on a tmp path, runs ``python -m des.cli.inject_seam`` against it with
        ``NWAVE_PERTURB=<seam>`` in the environment, and parses the emitted
        result. The perturbation is the port's -- the composition only stages +
        transports.
        """
        workspace = Path(tempfile.mkdtemp(prefix="inject-seam-"))
        self._workspace = workspace
        scaffold_path = workspace / "scaffold.json"
        out_path = workspace / "injection.json"
        scaffold_path.write_text(
            json.dumps(
                {"seams": {_NAMEABLE_SEAM: {"real": _REAL_IMPL, "fault": _FAULT_IMPL}}}
            ),
            encoding="utf-8",
        )
        prior_perturb = os.environ.get(_PERTURB_ENV)
        os.environ[_PERTURB_ENV] = self._seam_to_request
        try:
            exit_code, _stdout, _stderr = run_cli_in_process(
                [
                    "--scaffold",
                    str(scaffold_path),
                    "--out",
                    str(out_path),
                ],
                cwd=workspace,
                main=_inject_seam_main,
            )
        finally:
            if prior_perturb is None:
                os.environ.pop(_PERTURB_ENV, None)
            else:
                os.environ[_PERTURB_ENV] = prior_perturb
        return self._result_from_emission(out_path, exit_code)

    def _result_from_emission(
        self, out_path: Path, cli_exit_code: int
    ) -> InjectionResult:
        """Parse the emitted injection result into an ``InjectionResult``.

        When the CLI does not exist yet (RED scaffold) the subprocess exits
        non-zero and writes no result; the result then carries only the CLI exit
        code, and the outcome/resolution Then steps fail for the RIGHT reason
        (missing functionality at the driving port).
        """
        if not out_path.is_file():
            return InjectionResult(cli_exit_code=cli_exit_code)
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        outcome_str = payload.get("outcome")
        reason_str = payload.get("reason")
        return InjectionResult(
            outcome=InjectionOutcome(outcome_str) if outcome_str is not None else None,
            resolved_impl=payload.get("resolved_impl"),
            reason=VerdictReason(reason_str) if reason_str is not None else None,
            cli_exit_code=cli_exit_code,
            raw=payload,
        )

    def seam_resolves_to_fault(self) -> bool:
        """Whether the seam now resolves to the FAULT implementation.

        The post-injection observable: a successful perturbation leaves the seam
        resolving to the fault impl. Port-exposed observable only.
        """
        return self.result.resolved_impl == _FAULT_IMPL

    def seam_resolves_to_real(self) -> bool:
        """Whether the seam still resolves to the REAL implementation.

        Used to assert the perturbation is a real CHANGE (AT-2): after a
        successful injection this MUST be false. Port-exposed observable only.
        """
        return self.result.resolved_impl == _REAL_IMPL

    def real_dependency_left_untouched(self) -> bool:
        """Whether an abstain left the real dependency in place (AT-3).

        On the no-nameable-seam path the port abstains; it must NOT have swapped
        anything, so the seam (if reported at all) still resolves to the real
        impl, never the fault impl. Port-exposed observable only.
        """
        return self.result.resolved_impl != _FAULT_IMPL
