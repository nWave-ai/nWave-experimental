"""Composition root for f-wave-contract-coherence slice-02 (coherence-check gate).

DRIVING SURFACE (Mandate-13 driving-port-only -- ONE real surface, no
direct-domain testing):

  * Layer 3 subprocess -- the REAL ``des verify-wave-contract-coherence``
    subcommand invoked through the shipped ``des`` dispatcher
    (``python -m des <sub>``, the kebab CLI seam preferred for CLI behaviours,
    Mandate-13). The gate reads two real on-disk artifacts -- the wave PROSE
    (markdown) and the wave-contract REGISTRY (``nWave/waves/<wave>.yaml``) --
    and emits a §17 ``GateVerdict`` token on JSON-stdout (ADR-FLOW-006 D7; the
    five existing verdicts, no sixth, ADR-GV-001 / D9). The observable is that
    verdict token. Mandate-14 @real-io: real OS subprocess + real filesystem
    reads -- the AT would fail if the dispatcher or the registry file were absent.

No production module is imported-and-called at the step boundary for its business
logic -- the gate is reached ONLY as the real ``des`` subprocess. The fixture
authoring below sets up PRECONDITIONS (the prose + registry INPUT files), never the
expected OUTPUT verdict (Critical Rule 7 -- no fixture theater; the verdict is the
SUT's own emission, not a value the test fabricated).

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the DESIGN driving-surface (brief §2
"coherence-check gate" + §5) declares the load-bearing net-new seam:

  the ``des verify-wave-contract-coherence`` subcommand -- a new ``src/des/cli``
  module + its ``_REGISTRY`` row in ``src/des/cli/__main__.py`` + its
  ``nWave/gates/_catalog.yaml`` mirror (brief §2, the only NEW executable). Each
  slice-02 AT NAMES that subcommand seam, drives it through the REAL dispatcher
  (the shipped entry point), and asserts an observable effect (the emitted verdict
  token) -- never a name/protocol match, an actual subprocess invocation.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the
``verify-wave-contract-coherence`` subcommand does NOT exist -- the dispatcher
rejects it (``invalid choice`` usage error) and emits no verdict token. So every
Then fires a semantic ``AssertionError`` naming the missing gate subcommand /
absent verdict, never a collection / import / setup error. GREEN once DELIVER ships
``src/des/cli/verify_wave_contract_coherence.py`` + its registry row + catalog
mirror, emitting the five-verdict GateVerdict per the §5 check table.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .domain_types import CoherenceVerdict


# tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/<this file>
#   parents[6] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

# The operator-visible coherence-check subcommand (the DESIGN-declared net-new
# seam, brief §2). Driven as the REAL `des <sub>` kebab dispatch.
_GATE_SUBCOMMAND = "verify-wave-contract-coherence"

# The wave the worked-example prose points at -- DISCUSS, the slice-01 registry.
_DISCUSS_WAVE = "discuss"

# A bare catalog gate_id from the DISCUSS gate stack (nWave/waves/discuss.yaml /
# nWave/gates/_catalog.yaml). Restating THIS token inline in wave prose is the
# duplication drift surface AT-4 exercises -- the lexical scan (TextSearch floor)
# detects it. NOT a fabricated value: it is a real gate_id shipped in the catalog
# and the DISCUSS gate_stack today.
_CATALOG_GATE_ID = "validate-feature-delta"


@dataclass(frozen=True)
class _GateInvocation:
    """The observable boundary DTO of one coherence-check subprocess run.

    ``verdict``    -- the §17 GateVerdict token parsed from JSON-stdout, or None
                      when the gate emitted no parseable verdict (the RED at HEAD:
                      the subcommand does not exist, so nothing is emitted).
    ``stdout`` / ``stderr`` / ``exit_code`` -- raw observables for diagnostics.
    """

    verdict: str | None
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class CoherenceCheckComposition:
    """Drives the DISCUSS wave through the REAL coherence-check gate subprocess.

    Builds real on-disk fixture inputs (wave prose + registry) under a per-scenario
    tmp dir, invokes the real ``des verify-wave-contract-coherence`` subprocess over
    them, and exposes the emitted verdict token for the Then assertions.
    """

    tmp_path: Path
    _registry_dir: Path | None = field(default=None)
    _prose_path: Path | None = field(default=None)
    _registry_readable: bool = field(default=True)
    _invocation: _GateInvocation | None = field(default=None)

    # ---- given: registry preconditions --------------------------------------

    def given_registry_entry_for_discuss_with_both_ssots(self) -> None:
        """Stage a real DISCUSS registry file carrying BOTH SSOTs (gate_stack +
        output_contract) under a tmp waves dir.

        Copies the SHIPPED ``nWave/waves/discuss.yaml`` (slice-01, both SSOTs) into a
        tmp ``waves/`` dir -- the real registry shape the gate parses, not a hand-rolled
        stub. This is a PRECONDITION (a valid registry exists), never the expected
        output.
        """
        self._registry_dir = self.tmp_path / "waves"
        self._registry_dir.mkdir(parents=True, exist_ok=True)
        shipped = REPO_ROOT / "nWave" / "waves" / f"{_DISCUSS_WAVE}.yaml"
        (self._registry_dir / f"{_DISCUSS_WAVE}.yaml").write_text(
            shipped.read_text(encoding="utf-8"), encoding="utf-8"
        )

    def given_registry_is_unreadable(self) -> None:
        """Point the gate at an ABSENT registry dir -- the unreadable case (AT-6).

        A tmp waves dir with NO ``discuss.yaml`` inside: the gate must read the
        registry to resolve the pointer, cannot, and degrades LOUD to INDETERMINATE
        (Invariant 2) -- never a silent green.
        """
        self._registry_dir = self.tmp_path / "empty-waves"
        self._registry_dir.mkdir(parents=True, exist_ok=True)
        self._registry_readable = False

    # ---- given: prose preconditions -----------------------------------------

    def given_prose_restates_a_catalog_gate_id_inline(self) -> None:
        """Stage wave prose that restates a bare catalog gate_id inline (AT-4).

        The prose carries valid pointers BUT also enumerates a real catalog gate_id
        from the DISCUSS gate stack -- the duplication drift surface. The lexical scan
        (TextSearch floor) must detect the bare token and FAIL.
        """
        self._prose_path = self.tmp_path / f"{_DISCUSS_WAVE}.md"
        self._prose_path.write_text(
            "# DISCUSS wave\n\n"
            f"<!-- gates-ref: {_DISCUSS_WAVE} -->\n"
            f"<!-- outputs-ref: {_DISCUSS_WAVE} -->\n\n"
            "DISCUSS produces a slice plan the architect consumes.\n\n"
            "The gate-out stack runs "
            f"`{_CATALOG_GATE_ID}` then `verify-discuss-review`.\n",
            encoding="utf-8",
        )

    def given_prose_with_valid_pointers_zero_restatement(self) -> None:
        """Stage wave prose with valid pointers and ZERO inline restatement (AT-5/6).

        Carries both gates-ref + outputs-ref markers, NARRATES intent only (allowed),
        and enumerates NO gate_id and NO [REF]-section list -- the cured prose shape.
        """
        self._prose_path = self.tmp_path / f"{_DISCUSS_WAVE}.md"
        self._prose_path.write_text(
            "# DISCUSS wave\n\n"
            f"<!-- gates-ref: {_DISCUSS_WAVE} -->\n"
            f"<!-- outputs-ref: {_DISCUSS_WAVE} -->\n\n"
            "DISCUSS produces a slice plan the architect consumes. The gate stack "
            "and the output contract live in the registry the pointers name -- this "
            "prose narrates intent and restates neither.\n",
            encoding="utf-8",
        )

    # ---- when: drive the REAL gate subprocess -------------------------------

    def when_maintainer_runs_coherence_check(self) -> None:
        """Invoke the REAL ``des verify-wave-contract-coherence`` subprocess.

        Drives the shipped ``des`` dispatcher (``python -m des <sub>``) over the staged
        prose + registry, capturing stdout/stderr/exit. At HEAD the subcommand does
        not exist -> the dispatcher emits an ``invalid choice`` usage error and NO
        verdict token -> ``verdict`` is None (the RED).
        """
        assert self._prose_path is not None, (
            "wave prose must be staged (Given) before running the gate (When)"
        )
        assert self._registry_dir is not None, (
            "a registry dir must be staged (Given) before running the gate (When)"
        )
        argv = [
            sys.executable,
            "-m",
            "des",
            _GATE_SUBCOMMAND,
            "--wave",
            _DISCUSS_WAVE,
            "--prose",
            str(self._prose_path),
            "--waves-dir",
            str(self._registry_dir),
        ]
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        self._invocation = _GateInvocation(
            verdict=_parse_verdict(completed.stdout),
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )

    # ---- then: the emitted verdict token ------------------------------------

    def then_gate_emits_verdict(self, expected: CoherenceVerdict) -> None:
        """The gate emitted the expected §17 verdict token on JSON-stdout.

        Seam-named oracle (Mandate-15): the observable is the verdict the REAL
        ``des verify-wave-contract-coherence`` subprocess emits. RED at HEAD: the
        subcommand does not exist, so the dispatcher emits no verdict -> ``verdict``
        is None -> semantic AssertionError naming the missing gate subcommand.
        """
        inv = self._require_invocation()
        assert inv.verdict is not None, (
            "the `des verify-wave-contract-coherence` subcommand must emit a §17 "
            "GateVerdict token on JSON-stdout (ADR-FLOW-006 D7, the coherence-check "
            "gate) -- it emitted none. The subcommand does not exist yet: DELIVER "
            "slice-02 must ship src/des/cli/verify_wave_contract_coherence.py + its "
            f"_REGISTRY row + _catalog.yaml mirror. {self._observed()}"
        )
        assert inv.verdict == expected.value, (
            f"the coherence-check gate must emit the {expected.value!r} verdict for "
            f"this case; it emitted {inv.verdict!r}. {self._observed()}"
        )

    def then_failure_diagnostic_names_inline_restatement(self) -> None:
        """The FAIL diagnostic names the inline restatement the gate found (AT-4).

        Beyond the verdict, the gate must surface WHAT it found (the bare gate_id) so
        the maintainer can fix it -- the diagnostic carries the offending token. RED
        at HEAD: no verdict, no diagnostic -> semantic AssertionError.
        """
        inv = self._require_invocation()
        diagnostic = _parse_diagnostic(inv.stdout)
        assert diagnostic is not None and _CATALOG_GATE_ID in diagnostic, (
            "the FAIL diagnostic must name the inline restatement the gate found "
            f"(the bare catalog gate_id {_CATALOG_GATE_ID!r}) so the maintainer can "
            f"strip it; got diagnostic={diagnostic!r}. {self._observed()}"
        )

    def then_indeterminate_diagnostic_names_unreadable_registry(self) -> None:
        """The INDETERMINATE diagnostic names the unreadable registry (AT-6).

        Degrade-LOUD (Invariant 2): the refusal-to-decide must be VISIBLE -- the
        diagnostic states the registry could not be read for the referenced wave. RED
        at HEAD: no verdict, no diagnostic -> semantic AssertionError.
        """
        inv = self._require_invocation()
        diagnostic = _parse_diagnostic(inv.stdout)
        assert diagnostic is not None and _DISCUSS_WAVE in diagnostic, (
            "the INDETERMINATE diagnostic must name the unreadable registry for the "
            f"referenced wave ({_DISCUSS_WAVE!r}) -- a LOUD refusal-to-decide, never "
            f"a silent green; got diagnostic={diagnostic!r}. {self._observed()}"
        )

    # ---- helpers ------------------------------------------------------------

    def _require_invocation(self) -> _GateInvocation:
        assert self._invocation is not None, (
            "the coherence-check gate must run (When) before asserting (Then)"
        )
        return self._invocation

    def _observed(self) -> str:
        inv = self._invocation
        exit_code = inv.exit_code if inv else None
        stdout = repr(inv.stdout) if inv else None
        stderr = repr(inv.stderr) if inv else None
        return (
            f"gate_subcommand={_GATE_SUBCOMMAND!r}; "
            f"prose={self._prose_path}; registry_dir={self._registry_dir}; "
            f"registry_readable={self._registry_readable}; "
            f"exit_code={exit_code}; stdout={stdout}; stderr={stderr}"
        )


def _parse_verdict(stdout: str) -> str | None:
    """Parse the ``verdict`` token from the gate's JSON-stdout line.

    The shipped gate-CLI convention (e.g. ``des gate-g``) prints one JSON line
    ``{"verdict": <token>, "diagnostic": <str>}``. Tolerate extra non-JSON lines
    (the dev-checkout freshness banner). Return None when no JSON line carries a
    verdict -- the RED at HEAD (the subcommand emits no such line).
    """
    payload = _last_json_object(stdout)
    if payload is None:
        return None
    verdict = payload.get("verdict")
    return verdict if isinstance(verdict, str) else None


def _parse_diagnostic(stdout: str) -> str | None:
    """Parse the ``diagnostic`` string from the gate's JSON-stdout line."""
    payload = _last_json_object(stdout)
    if payload is None:
        return None
    diagnostic = payload.get("diagnostic")
    return diagnostic if isinstance(diagnostic, str) else None


def _last_json_object(stdout: str) -> dict[str, object] | None:
    """Return the last line of stdout that parses as a JSON object, else None."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
