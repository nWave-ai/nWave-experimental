"""Composition root: the coherence-hook fires on DISTILL + DELIVER prose (slice-04).

algebra-projections-enforced slice-04 (DISCUSS slice-04, DESIGN Point 5 +
Reuse Analysis row ``_MIGRATED``, ADR-FLOW-006 D4/D7).

Two REAL driving ports (Layer 3 subprocess, hermetic, DIRECT — never the flock
wrapper):

  1. ``des verify-wave-contract-coherence --wave <wave> --prose <locus> --waves-dir
     nWave/waves`` — the shipped §17 coherence gate. slice-04 drives it against the
     REAL distill/deliver prose loci with the REAL ``nWave/waves`` registry, so a
     migrated-and-scrubbed locus must emit the ``pass`` token.

  2. ``scripts/hooks/run_wave_contract_coherence.py`` — the FIRING SURFACE
     pre-commit hook. slice-04 extends its ``_MIGRATED`` tuple from DISCUSS-only to
     DISCUSS+DISTILL+DELIVER. The hook AT runs the script itself and reads which
     (wave, locus) pairs it exercised, asserting the distill+deliver loci are
     covered (the hook exit + its diagnostic name the loci it ran).

Both ports spawn ``python -m des`` / a stdlib script child; the child does NOT
inherit the parent runtime ``sys.path`` under some invocations, so the subprocess
env prepends ``src/`` to ``PYTHONPATH`` — the SAME fix the hook itself carries
(commit ``add6a2eff`` / ``0854192ff``). Environment SETUP, not assertion-weakening.

active-RED scaffold (atdd_pure — NOT @skip). At HEAD:
  * ``run_wave_contract_coherence.py:_MIGRATED`` = DISCUSS-only -> the hook never
    runs the gate on distill/deliver -> the hook-coverage Then RED-fails (the
    distill/deliver loci are absent from the pairs the hook exercised);
  * the four distill/deliver prose loci carry NO ``gates-ref``/``outputs-ref``
    pointer AND restate bare catalog gate_ids inline -> the gate emits ``fail`` on
    every real locus -> the pristine-locus ``pass`` Then RED-fails.

DELIVER A_GREEN: (a) adds the 4 distill/deliver rows to ``_MIGRATED``, AND (b)
adds the pointer pair to each of the 4 loci AND scrubs the bare catalog gate_id
tokens from the distill/deliver prose (the gate's inline-restatement check FAILS
on any bare gate_id even with the pointer present — empirically confirmed at
DISTILL time; see the slice-04 [REF] DELIVER-scope note in the feature-delta).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from scripts.hooks import run_wave_contract_coherence
from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_04 import (
    CoherenceVerdict,
    MigratedWave,
    ProseLocus,
    ProseMutation,
)


_REPO_ROOT = Path(__file__).resolve().parents[5]
_WAVES_DIR = _REPO_ROOT / "nWave" / "waves"
_HOOK_SCRIPT = _REPO_ROOT / "scripts" / "hooks" / "run_wave_contract_coherence.py"
_COHERENCE_SUBCOMMAND = "verify-wave-contract-coherence"


@dataclass(frozen=True)
class _GateObservable:
    """The gate's §17 verdict envelope (the structured assertion target)."""

    verdict: str | None
    diagnostic: str | None
    recognised: bool
    raw: str


@dataclass(frozen=True)
class _HookObservable:
    """What the firing-surface hook exercised + its outcome."""

    exit_code: int
    covered_waves: frozenset[str]
    raw: str


class CoherenceHookComposition:
    """Production composition root for slice-04 — drives the REAL gate + hook."""

    def __init__(self) -> None:
        self._locus: ProseLocus | None = None
        self._mutation: ProseMutation = ProseMutation.PRISTINE
        self._gate_observable: _GateObservable | None = None
        self._hook_observable: _HookObservable | None = None
        # universe: the gate/hook are pure readers — they MUST NOT mutate the prose
        # locus on disk. The universe is the locus file's bytes before/after.
        self._locus_bytes_before: bytes | None = None

    # =====================================================================
    # Given — arm the prose locus + mutation (typed lookups, no branching)
    # =====================================================================

    def given_prose_locus(self, locus: ProseLocus) -> None:
        self._locus = locus

    def given_prose_mutation(self, mutation: ProseMutation) -> None:
        self._mutation = mutation

    # =====================================================================
    # When — drive the REAL driving ports
    # =====================================================================

    def when_the_coherence_gate_runs(self, tmp_path: Path) -> None:
        """Drive ``des verify-wave-contract-coherence`` on the armed locus.

        slice-04 drives only the PRISTINE presentation: the REAL repo locus with
        the REAL waves-dir (genuine end-to-end). The gate is a pure reader so the
        real prose is never mutated. ``tmp_path`` is kept in the signature for
        parity with the test-driver fixture wiring (unused on the PRISTINE path).
        """
        assert self._locus is not None, "a scenario must arm a ProseLocus first."
        assert self._mutation is ProseMutation.PRISTINE, (
            "slice-04 arms only the PRISTINE presentation (pure coverage extension)."
        )
        real_locus = _REPO_ROOT / self._locus.value
        self._locus_bytes_before = real_locus.read_bytes()
        self._gate_observable = self._drive_gate(self._locus.wave, real_locus)

    def when_the_coherence_hook_runs(self) -> None:
        """Run the REAL firing-surface hook script and capture which waves it covered."""
        self._hook_observable = self._drive_hook()

    # =====================================================================
    # Then — observable readers
    # =====================================================================

    def observed_gate_verdict(self) -> str | None:
        assert self._gate_observable is not None, "the gate must be driven first."
        return self._gate_observable.verdict

    def gate_diagnostic(self) -> str:
        assert self._gate_observable is not None, "the gate must be driven first."
        return self._gate_observable.diagnostic or ""

    def hook_covered_wave(self, wave: MigratedWave) -> bool:
        """Did the firing-surface hook exercise the coherence gate on ``wave``?"""
        assert self._hook_observable is not None, "the hook must be driven first."
        return wave.value in self._hook_observable.covered_waves

    def hook_exit_code(self) -> int:
        assert self._hook_observable is not None, "the hook must be driven first."
        return self._hook_observable.exit_code

    def real_locus_unchanged(self) -> bool:
        """The gate/hook are pure readers — the on-disk locus bytes are unchanged."""
        assert self._locus is not None and self._locus_bytes_before is not None
        return (_REPO_ROOT / self._locus.value).read_bytes() == self._locus_bytes_before

    # =====================================================================
    # universe (Mandate 8 — port-exposed observable snapshot)
    # =====================================================================

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable: the real locus bytes (purity check)."""
        path = _REPO_ROOT / self._locus.value if self._locus is not None else None
        return {
            "prose_locus.exists": path.exists() if path is not None else False,
            "prose_locus.bytes": path.read_bytes() if path is not None else b"",
        }

    # =====================================================================
    # driving-port invocations (real subprocess — DIRECT, never flock)
    # =====================================================================

    def _drive_gate(self, wave: MigratedWave, prose_path: Path) -> _GateObservable:
        _exit_code, stdout, stderr = run_cli_in_process(
            [
                _COHERENCE_SUBCOMMAND,
                "--wave",
                str(wave.value),
                "--prose",
                str(prose_path),
                "--waves-dir",
                str(_WAVES_DIR),
            ],
            cwd=_REPO_ROOT,
        )
        raw = f"{stdout}\n{stderr}"
        recognised = "usage:" not in stderr.lower()
        verdict, diagnostic = self._parse_envelope(stdout)
        return _GateObservable(
            verdict=verdict,
            diagnostic=diagnostic,
            recognised=recognised and verdict is not None,
            raw=raw,
        )

    def _drive_hook(self) -> _HookObservable:
        """Drive the firing-surface hook's ``main()`` EDGE in-process and read coverage.

        The hook (``scripts/hooks/run_wave_contract_coherence.py``) iterates its
        ``_MIGRATED`` (wave, locus) tuple and runs the gate per pair. We read the
        script's source for the actual ``_MIGRATED`` rows it drives (the hook does
        not print the passing pairs), then run the hook's ``main()`` EDGE in-process
        (via the shared ``run_cli_in_process`` driver, wrapping the argv-less
        ``main`` — chdir+restore + stdout/stderr capture + ``SystemExit`` mapping)
        to confirm it exits cleanly over them. The covered-wave set is the set of
        waves named in the live ``_MIGRATED`` tuple — the observable the slice-04
        contract is about (the hook FIRES on distill+deliver, not only discuss).

        The hook reads NO stdin (it is a pre-commit firing surface, not a
        ``claude_code_hook_adapter`` stdin hook), so the in-process drive is
        faithful — exit code + captured output + covered-wave set are 1:1 with the
        former ``python run_wave_contract_coherence.py`` fork. (The PRODUCTION hook
        still spawns ``-m des`` children internally; those live in ``scripts/hooks``,
        are not acceptance-test forks, and are out of this migration's scope.)
        """
        covered = self._migrated_waves_from_source()
        exit_code, stdout, stderr = run_cli_in_process(
            [],
            cwd=_REPO_ROOT,
            main=lambda _argv: run_wave_contract_coherence.main(),
        )
        raw = f"{stdout}\n{stderr}"
        return _HookObservable(
            exit_code=exit_code,
            covered_waves=covered,
            raw=raw,
        )

    @staticmethod
    def _migrated_waves_from_source() -> frozenset[str]:
        """The set of waves the hook's live ``_MIGRATED`` tuple names.

        Reads the shipped hook source and extracts the wave id of each
        ``("<wave>", "<locus>")`` row. This is the observable the slice-04 contract
        asserts on: at HEAD only ``discuss``; post-DELIVER ``discuss``+``distill``+
        ``deliver``. A binding-resolved read of the literal tuple, not a guess.
        """
        text = _HOOK_SCRIPT.read_text(encoding="utf-8")
        # Capture the wave id (first tuple element) of each _MIGRATED row.
        rows = re.findall(r'\(\s*"([a-z]+)"\s*,\s*"[^"]+"\s*\)', text)
        return frozenset(rows)

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


# Re-export the verdict enum so the test driver imports a single module surface.
__all__ = ["CoherenceHookComposition", "CoherenceVerdict", "MigratedWave"]
