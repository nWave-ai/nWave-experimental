#!/usr/bin/env python3
"""Pre-commit hook: run the `verify-wave-contract-coherence` gate on the migrated waves.

The gate (`des verify-wave-contract-coherence`, ADR-FLOW-006 D7, f-wave-contract-coherence
slice-02) verifies that a wave's command/skill prose carries valid `gates-ref` +
`outputs-ref` pointers, restates no bare catalog gate_id inline, and that the referenced
wave resolves in BOTH registry SSOTs. This hook is the FIRING SURFACE: it runs the shipped
gate over every wave whose contract has been migrated to the registry, so prose↔registry
drift is caught at commit time (the gate's reason for existing) rather than only on demand.

Git-free, stdlib + the shipped des gate only. Add a (wave, prose-locus) pair here as each
wave migrates to the registry; today DISCUSS is the worked example (both prose loci).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_REPO = Path(__file__).resolve().parents[2]
_WAVES_DIR = _REPO / "nWave" / "waves"

# (wave-id, prose-locus) pairs whose contract lives in the registry. Extend as waves migrate.
_MIGRATED: tuple[tuple[str, str], ...] = (
    ("discuss", "nWave/tasks/nw/discuss.md"),
    ("discuss", "nWave/skills/nw-discuss/SKILL.md"),
    ("distill", "nWave/tasks/nw/distill.md"),
    ("distill", "nWave/skills/nw-distill/SKILL.md"),
    ("deliver", "nWave/tasks/nw/deliver.md"),
    ("deliver", "nWave/skills/nw-deliver/SKILL.md"),
)


def main() -> int:
    # The spawned `-m des` child does NOT inherit the parent runtime's sys.path
    # (under pre-commit, sys.executable is the hook venv python without des on
    # its path -> ModuleNotFoundError: des). Prepend des's containing dir (src/)
    # to PYTHONPATH so the child resolves it -- same intent as
    # des.runtime.interpreter.des_subprocess_env(), inlined because this hook is
    # stdlib-only and cannot import des. Mirrors the core fix (commit 0854192ff).
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(_REPO / "src"), env.get("PYTHONPATH", "")) if p
    )

    failures: list[str] = []
    for wave, prose_rel in _MIGRATED:
        prose = _REPO / prose_rel
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "des",
                "verify-wave-contract-coherence",
                "--wave",
                wave,
                "--prose",
                str(prose),
                "--waves-dir",
                str(_WAVES_DIR),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            env=env,
        )
        if proc.returncode != 0:
            failures.append(
                f"  {wave} / {prose_rel}: {proc.stdout.strip()}{proc.stderr.strip()}"
            )

    if failures:
        print("verify-wave-contract-coherence: wave-contract drift detected:")
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
