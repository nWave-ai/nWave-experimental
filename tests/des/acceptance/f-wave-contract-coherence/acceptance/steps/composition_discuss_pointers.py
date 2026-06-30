"""Composition root for f-wave-contract-coherence slice-03 (DISCUSS prose pointers).

DRIVING SURFACE (Mandate-13 driving-port-only -- ONE real surface, no
direct-domain testing):

  * Layer 3 subprocess -- the REAL ``des verify-wave-contract-coherence``
    subcommand (slice-02, the shipped gate) invoked through the shipped ``des``
    dispatcher (``python -m des <sub>``). The gate is the seam slice-03 drives;
    slice-03 ADDS no executable -- it re-points the DISCUSS prose so the slice-02
    gate, run over the SHIPPED prose + SHIPPED registry, returns PASS.

slice-03 differs from slice-02 in ONE load-bearing way: slice-02 staged
hand-rolled prose in a tmp dir (the gate's unit behaviour); slice-03 drives the
gate over the **REAL shipped DISCUSS prose** (``nWave/tasks/nw/discuss.md`` +
``nWave/skills/nw-discuss/SKILL.md``) and the **REAL shipped registry**
(``nWave/waves``). The observable is the verdict the gate emits about the prose
that actually ships -- so a GREEN here proves the cure landed on the files the
maintainer edits, not on a fixture (Critical Rule 7: no fixture theater -- the
prose is the real shipped artifact, the verdict is the gate's own emission).

The structural Then (``then_prose_carries_both_pointers`` /
``then_prose_restates_nothing_inline``) re-uses the SAME git-free check primitives
the slice-02 gate is built from (the ``gates-ref`` / ``outputs-ref`` markers + the
catalog ``gate_id`` lexical scan): it does not re-implement them -- it imports the
shipped gate's own ``_GATES_REF`` / ``_OUTPUTS_REF`` / ``_catalog_gate_ids`` /
``_inline_restatement`` so the AT asserts exactly what the gate enforces (no
test-private duplicate of the rule).

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): slice-03 introduces NO net-new
load-bearing seam -- it RE-POINTS the DISCUSS prose at the slice-02 gate's already
load-bearing seam (the ``des verify-wave-contract-coherence`` subcommand). Each
slice-03 AT NAMES that subcommand seam, drives it through the REAL dispatcher over
the REAL shipped prose, and asserts an observable effect (the emitted verdict /
the pointer + no-restatement facts the gate keys on).

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the shipped DISCUSS prose
carries NO ``gates-ref``/``outputs-ref`` pointer and STILL restates the bare
catalog gate_id ``validate-feature-delta`` inline. So the gate returns FAIL (not
PASS) and the structural facts are false -> every Then fires a semantic
``AssertionError`` naming the missing pointer / surviving restatement, never a
collection / import / setup error. GREEN once DELIVER adds the two pointer markers
and STRIPS the inline gate-id / [REF]-section restatement from both prose loci.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

# Import the SHIPPED gate's own check primitives so the structural AT asserts
# exactly what the gate enforces -- the rule has ONE definition (the gate), the AT
# does not keep a private copy of it (Mandate-12 SSOT).
from des.cli.verify_wave_contract_coherence import (
    _GATES_REF,
    _OUTPUTS_REF,
    _catalog_gate_ids,
    _inline_restatement,
)


if TYPE_CHECKING:
    from .domain_types import CoherenceVerdict, DiscussProseLocus


# tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/<this file>
#   parents[6] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

# The operator-visible coherence-check subcommand (the slice-02 shipped gate, the
# DESIGN-declared seam). Driven as the REAL `des <sub>` kebab dispatch.
_GATE_SUBCOMMAND = "verify-wave-contract-coherence"

# The wave whose shipped prose slice-03 re-points -- DISCUSS, the slice-01 registry.
_DISCUSS_WAVE = "discuss"

# The shipped wave-contract registry dir (slice-01 -- the REAL nWave/waves, not a
# tmp fixture): the gate resolves the DISCUSS pointer against this.
_SHIPPED_WAVES_DIR = REPO_ROOT / "nWave" / "waves"


@dataclass(frozen=True)
class _GateInvocation:
    """The observable boundary DTO of one coherence-check subprocess run."""

    verdict: str | None
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class DiscussPointersComposition:
    """Drives the REAL coherence-check gate over the SHIPPED DISCUSS prose.

    Resolves the shipped prose locus (command or skill) under check, invokes the
    real ``des verify-wave-contract-coherence`` subprocess over it + the shipped
    ``nWave/waves`` registry, and exposes both the emitted verdict (AT-8) and the
    shipped prose text for the structural pointer/restatement facts (AT-7).
    """

    _locus: DiscussProseLocus | None = field(default=None)
    _prose_path: Path | None = field(default=None)
    _invocation: _GateInvocation | None = field(default=None)

    # ---- given: the shipped prose locus under check -------------------------

    def given_shipped_discuss_prose(self, locus: DiscussProseLocus) -> None:
        """Bind the REAL shipped DISCUSS prose locus (command or skill) under check.

        Resolves to the actual on-disk file the maintainer edits and the coherence
        gate scans -- ``nWave/tasks/nw/discuss.md`` or
        ``nWave/skills/nw-discuss/SKILL.md`` (brief §4 + §6 name BOTH loci as the
        cure targets). PRECONDITION only -- the file is the real shipped artifact,
        not staged output.
        """
        prose_path = REPO_ROOT / locus.value
        assert prose_path.is_file(), (
            f"the shipped DISCUSS prose locus {locus.value!r} must exist on disk "
            f"(it is the real artifact the cure re-points); resolved to {prose_path}"
        )
        self._locus = locus
        self._prose_path = prose_path

    # ---- when: drive the REAL gate subprocess over the shipped prose --------

    def when_maintainer_runs_coherence_check_over_discuss(self) -> None:
        """Invoke the REAL ``des verify-wave-contract-coherence`` over the shipped
        DISCUSS prose + the shipped ``nWave/waves`` registry."""
        prose_path = self._require_prose_path()
        argv = [
            sys.executable,
            "-m",
            "des",
            _GATE_SUBCOMMAND,
            "--wave",
            _DISCUSS_WAVE,
            "--prose",
            str(prose_path),
            "--waves-dir",
            str(_SHIPPED_WAVES_DIR),
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

    # ---- then: the structural pointer/restatement facts (AT-7) -------------

    def then_prose_carries_both_pointers(self) -> None:
        """The shipped DISCUSS prose carries BOTH a gates-ref and an outputs-ref
        pointer naming the DISCUSS wave (the cure's ADD half).

        Asserted with the SHIPPED gate's own marker regexes -- the AT checks exactly
        what the gate keys on. RED at HEAD: the shipped prose carries neither marker
        -> semantic AssertionError naming the missing pointer.
        """
        prose_text = self._read_prose()
        gates_ref = _GATES_REF.search(prose_text)
        outputs_ref = _OUTPUTS_REF.search(prose_text)
        assert gates_ref is not None and gates_ref.group(1) == _DISCUSS_WAVE, (
            f"the shipped DISCUSS prose {self._locus_label()} must carry a valid "
            f"`<!-- gates-ref: {_DISCUSS_WAVE} -->` pointer (the prose must POINT at "
            f"the registry, not restate the gate stack inline); none found. DELIVER "
            f"slice-03 must add the pointer to both DISCUSS prose loci."
        )
        assert outputs_ref is not None and outputs_ref.group(1) == _DISCUSS_WAVE, (
            f"the shipped DISCUSS prose {self._locus_label()} must carry a valid "
            f"`<!-- outputs-ref: {_DISCUSS_WAVE} -->` pointer (the prose must POINT "
            f"at the registry, not restate the output contract inline); none found."
        )

    def then_prose_restates_nothing_inline(self) -> None:
        """The shipped DISCUSS prose restates NO bare catalog gate_id inline (the
        cure's REMOVE half).

        Re-uses the SHIPPED gate's ``_inline_restatement`` over the shipped prose +
        the real catalog gate_id set -- the AT asserts the exact lexical rule the
        gate enforces, not a test-private re-derivation. RED at HEAD: the prose
        still restates ``validate-feature-delta`` (x1 in discuss.md, x4 in the
        skill) -> the scan returns that token -> semantic AssertionError naming the
        surviving restatement.
        """
        prose_text = self._read_prose()
        restated = _inline_restatement(prose_text, _catalog_gate_ids())
        assert restated is None, (
            f"the shipped DISCUSS prose {self._locus_label()} still restates the bare "
            f"catalog gate_id {restated!r} inline (the duplication drift surface "
            f"cure-I strips); DELIVER slice-03 must remove the inline gate-id / "
            f"[REF]-section enumeration and let the pointers carry it."
        )

    # ---- then: the gate verdict over the shipped prose (AT-8) ---------------

    def then_gate_emits_verdict(self, expected: CoherenceVerdict) -> None:
        """The REAL gate emitted the expected §17 verdict over the shipped prose.

        Seam-named oracle (Mandate-15): the observable is the verdict the slice-02
        gate emits about the SHIPPED DISCUSS prose + SHIPPED registry. RED at HEAD:
        the uncured prose has no pointer + restates a gate_id -> the gate emits FAIL,
        not the expected PASS -> semantic AssertionError.
        """
        inv = self._require_invocation()
        assert inv.verdict is not None, (
            "the `des verify-wave-contract-coherence` gate must emit a §17 GateVerdict "
            "token on JSON-stdout over the shipped DISCUSS prose; it emitted none. "
            f"{self._observed()}"
        )
        assert inv.verdict == expected.value, (
            f"the coherence-check gate must emit {expected.value!r} for the cured "
            f"shipped DISCUSS prose {self._locus_label()}; it emitted {inv.verdict!r}. "
            f"At HEAD the prose is uncured (no pointers, gate_id restated inline) so "
            f"the gate FAILs -- DELIVER slice-03 adds the pointers + strips the "
            f"restatement. {self._observed()}"
        )

    # ---- helpers ------------------------------------------------------------

    def _read_prose(self) -> str:
        return self._require_prose_path().read_text(encoding="utf-8")

    def _require_prose_path(self) -> Path:
        assert self._prose_path is not None, (
            "the shipped DISCUSS prose locus must be bound (Given) before the gate "
            "runs / facts are asserted"
        )
        return self._prose_path

    def _require_invocation(self) -> _GateInvocation:
        assert self._invocation is not None, (
            "the coherence-check gate must run (When) before asserting the verdict "
            "(Then)"
        )
        return self._invocation

    def _locus_label(self) -> str:
        return self._locus.value if self._locus is not None else "<unbound>"

    def _observed(self) -> str:
        inv = self._invocation
        exit_code = inv.exit_code if inv else None
        stdout = repr(inv.stdout) if inv else None
        stderr = repr(inv.stderr) if inv else None
        return (
            f"gate_subcommand={_GATE_SUBCOMMAND!r}; prose={self._prose_path}; "
            f"waves_dir={_SHIPPED_WAVES_DIR}; exit_code={exit_code}; "
            f"stdout={stdout}; stderr={stderr}"
        )


def _parse_verdict(stdout: str) -> str | None:
    """Parse the ``verdict`` token from the gate's JSON-stdout line (tolerating the
    dev-checkout freshness banner line)."""
    payload = _last_json_object(stdout)
    if payload is None:
        return None
    verdict = payload.get("verdict")
    return verdict if isinstance(verdict, str) else None


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
