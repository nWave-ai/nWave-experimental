"""Composition root: the `_inline_restatement` clause scopes to enumeration (slice-04).

algebra-projections-enforced slice-04 — ADR-003 (REROUTE_DESIGN #2, DD-A6).

ONE REAL driving port (Layer 3 subprocess, hermetic, DIRECT — never the flock
wrapper): ``des verify-wave-contract-coherence --wave discuss --prose <locus>
--waves-dir <dir>`` — the shipped §17 coherence gate. The narrowing witnesses drive
it over:

  * a SYNTHETIC prose body (written to ``tmp_path``) + a SYNTHETIC minimal-but-valid
    ``discuss.yaml`` registry (carrying BOTH SSOTs so the gate REACHES the
    inline-restatement clause under test) — for the enumeration/invocation
    discriminators (W1, W2); and
  * the REAL ``nWave/skills/nw-discuss/SKILL.md`` locus + the REAL ``nWave/waves``
    registry — for the byte-stable DISCUSS preservation guard (W3).

The synthetic registry is named ``discuss.yaml`` and the gate is driven with
``--wave discuss`` so the pointer markers (``gates-ref: discuss``) resolve and the
pointer-presence check PASSes; the gate then reaches ``_inline_restatement`` — the
exact clause ADR-003 narrows. Using a synthetic registry keeps W1/W2 hermetic and
independent of the live ``discuss.yaml`` contents (only the clause's
enumeration-vs-mention behaviour is under test, not the real discuss prose).

The spawned ``python -m des`` child does not inherit the parent runtime ``sys.path``
under some invocations, so the subprocess env prepends ``src/`` to ``PYTHONPATH``
(the same fix the firing-surface hook carries; commits ``add6a2eff`` / ``0854192ff``).
Environment SETUP, not assertion-weakening.

active-RED / preservation classification (atdd_pure — NOT @skip), per the HEAD probe
(red-classification slice-04 narrowing table):
  * W1 (enumeration FAILs) — PRESERVATION-GUARD: at HEAD the lexical scan flags the
    first bare catalog gate_id (``carpaccio-slice-gate``), so the enumeration already
    FAILs; the narrowing must KEEP it failing. GREEN at HEAD and post-narrowing.
  * W2 (invocation + roadmap.json PASS) — ACTIVE-RED MISSING_FUNCTIONALITY: at HEAD
    the scan flags ``verify-integrity`` / ``init-log`` / ``roadmap`` as bare tokens,
    so the gate emits ``fail`` — the false positive. The narrowing (A_GREEN) makes it
    ``pass``.
  * W3 (DISCUSS byte-stable) — PRESERVATION-GUARD: the real discuss prose carries no
    gate-stack enumeration today, so it PASSes at HEAD; the narrowing must not change
    that (ADR-003 D2 byte-stable).

Step bodies delegate here; no inline business logic (Mandate-12 criterion 3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_04_narrowing import (
    SYNTHETIC_BODY_BY_SHAPE,
    CoherenceVerdict,
    InlineProseShape,
)


_REPO_ROOT = Path(__file__).resolve().parents[5]
_REAL_WAVES_DIR = _REPO_ROOT / "nWave" / "waves"
_REAL_DISCUSS_LOCUS = _REPO_ROOT / "nWave" / "skills" / "nw-discuss" / "SKILL.md"
_COHERENCE_SUBCOMMAND = "verify-wave-contract-coherence"

# A minimal-but-valid `discuss.yaml` carrying BOTH SSOTs (gate_stack +
# output_contract) so the gate's pointer + both-SSOT checks PASS and execution
# REACHES `_inline_restatement` (the clause under test). `validate-feature-delta`
# is a real catalog gate_id, so the gate_stack entry is not an orphan.
_SYNTHETIC_REGISTRY = (
    "gate_stack:\n"
    "  gate_in:\n"
    "    - gate_id: validate-feature-delta\n"
    "output_contract:\n"
    "  ref_sections:\n"
    "    - id: Persona\n"
)


@dataclass(frozen=True)
class _GateObservable:
    """The gate's §17 verdict envelope (the structured assertion target)."""

    verdict: str | None
    diagnostic: str | None
    raw: str


class InlineRestatementNarrowingComposition:
    """Production composition root for the slice-04 narrowing witnesses.

    Drives the REAL ``des verify-wave-contract-coherence`` gate over a prose shape and
    captures the §17 verdict envelope. The shape decides synthetic-vs-real prose and
    synthetic-vs-real registry — a typed lookup, no branching logic in the step body.
    """

    def __init__(self) -> None:
        self._shape: InlineProseShape | None = None
        self._gate_observable: _GateObservable | None = None
        self._real_locus_bytes_before: bytes | None = None

    # =====================================================================
    # Given — arm the prose shape (typed lookup, no branching)
    # =====================================================================

    def given_prose_shape(self, shape: InlineProseShape) -> None:
        self._shape = shape

    # =====================================================================
    # When — drive the REAL coherence gate over the armed shape
    # =====================================================================

    def when_the_coherence_gate_runs(self, tmp_path: Path) -> None:
        assert self._shape is not None, "a scenario must arm an InlineProseShape first."
        if self._shape is InlineProseShape.PRISTINE_DISCUSS:
            prose_path = _REAL_DISCUSS_LOCUS
            waves_dir = _REAL_WAVES_DIR
            self._real_locus_bytes_before = prose_path.read_bytes()
        else:
            prose_path = tmp_path / "prose.md"
            prose_path.write_text(
                SYNTHETIC_BODY_BY_SHAPE[self._shape], encoding="utf-8"
            )
            waves_dir = tmp_path / "waves"
            waves_dir.mkdir(exist_ok=True)
            (waves_dir / "discuss.yaml").write_text(
                _SYNTHETIC_REGISTRY, encoding="utf-8"
            )
        self._gate_observable = self._drive_gate(prose_path, waves_dir)

    # =====================================================================
    # Then — observable readers
    # =====================================================================

    def observed_gate_verdict(self) -> str | None:
        assert self._gate_observable is not None, "the gate must be driven first."
        return self._gate_observable.verdict

    def gate_diagnostic(self) -> str:
        assert self._gate_observable is not None, "the gate must be driven first."
        return self._gate_observable.diagnostic or ""

    def real_discuss_locus_unchanged(self) -> bool:
        """The gate is a pure reader — the real discuss locus bytes are unchanged."""
        assert self._real_locus_bytes_before is not None, (
            "real_discuss_locus_unchanged is only meaningful for the PRISTINE_DISCUSS "
            "shape (which reads the real locus)."
        )
        return _REAL_DISCUSS_LOCUS.read_bytes() == self._real_locus_bytes_before

    # =====================================================================
    # universe (Mandate 8 — port-exposed observable snapshot, real-locus purity)
    # =====================================================================

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable for the byte-stable guard: the real locus bytes."""
        return {
            "discuss_locus.exists": _REAL_DISCUSS_LOCUS.exists(),
            "discuss_locus.bytes": _REAL_DISCUSS_LOCUS.read_bytes(),
        }

    # =====================================================================
    # driving-port invocation (real subprocess — DIRECT, never flock)
    # =====================================================================

    def _drive_gate(self, prose_path: Path, waves_dir: Path) -> _GateObservable:
        _exit_code, stdout, stderr = run_cli_in_process(
            [
                _COHERENCE_SUBCOMMAND,
                "--wave",
                "discuss",
                "--prose",
                str(prose_path),
                "--waves-dir",
                str(waves_dir),
            ],
            cwd=_REPO_ROOT,
        )
        raw = f"{stdout}\n{stderr}"
        verdict, diagnostic = self._parse_envelope(stdout)
        return _GateObservable(verdict=verdict, diagnostic=diagnostic, raw=raw)

    @staticmethod
    def _parse_envelope(stdout: str) -> tuple[str | None, str | None]:
        """Pull the ``verdict`` + ``diagnostic`` fields out of the JSON envelope."""
        for line in reversed(stdout.splitlines()):
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "verdict" in payload:
                verdict = payload.get("verdict")
                diagnostic = payload.get("diagnostic")
                return (
                    str(verdict) if verdict is not None else None,
                    str(diagnostic) if diagnostic is not None else None,
                )
        return None, None


__all__ = ["CoherenceVerdict", "InlineRestatementNarrowingComposition"]
