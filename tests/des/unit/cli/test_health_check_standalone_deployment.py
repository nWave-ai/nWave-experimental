"""P1 regression: health_check CLI exits 0 with PYTHONPATH=des-only environment.

Root cause: RC-A (P0-A) chain — health_check imports claude_code_hook_adapter
which imports session_start_handler which imports substrate_probe which had
top-level nwave_ai imports. Fix: substrate_probe lazy-imports nwave_ai inside
run_probe() with try/except ImportError.

This test exercises the full import chain at subprocess level, simulating
a minimal healthy DES deployment without nwave_ai on the path.

Test Budget: 1 behavior x 2 = 2 max. Using 1 test.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_health_check_exits_zero_with_des_only_pythonpath(tmp_path: Path) -> None:
    """health_check must exit 0 when PYTHONPATH contains only the DES lib.

    Stages a minimal healthy environment in tmp_path so that checks
    1 (version), 3 (templates), 6 (agents), 7 (skills) have enough
    structure to pass — or gracefully degrade. The critical assertion
    is exit code 0, proving that the import chain does not break when
    nwave_ai is absent.

    Environment is curated: only PATH and PYTHONPATH are set.
    HOME is pointed at tmp_path so health_check uses the staged dirs.
    """
    # Stage minimal healthy structure under tmp_path as the fake HOME
    claude_dir = tmp_path / ".claude"
    (claude_dir / "agents" / "nw").mkdir(parents=True)
    (claude_dir / "skills" / "nw-canary").mkdir(parents=True)
    (claude_dir / "templates").mkdir(parents=True)
    (claude_dir / "templates" / "step-tdd-cycle-schema.json").write_text("{}")
    (claude_dir / "VERSION").write_text("2.99.0-test")
    # logs dir — health_check creates it if absent, so no need to pre-create
    logs_dir = tmp_path / ".nwave" / "logs"
    logs_dir.mkdir(parents=True)

    # PYTHONPATH: point at src/ so that 'des' package is importable.
    # Use the repo's src/ directory — same layout that DES hooks consume.
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    des_lib = repo_root / "src"
    assert (des_lib / "des").is_dir(), f"DES package not found at {des_lib / 'des'}"

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        "PYTHONPATH": str(des_lib),
        # Silence logging noise
        "NW_LOG": "false",
        # Bypass the freshness gate: this test stages a synthetic DES tree under
        # tmp_path that intentionally lacks the install manifest the gate expects.
        # `skip` is the audit-bearing dev-tree contract per fix-des-self-hosted-
        # gate-sync design §6 — propagated to the curated subprocess env because
        # `env={...}` discards the parent's NWAVE_FRESHNESS.
        "NWAVE_FRESHNESS": "skip",
    }

    result = subprocess.run(
        [sys.executable, "-m", "des.cli.health_check"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"health_check exited {result.returncode} with des-only PYTHONPATH.\n"
        f"stdout:\n{result.stdout[-500:]}\n"
        f"stderr:\n{result.stderr[-500:]}\n"
        "This indicates substrate_probe (or another DES module) has a top-level\n"
        "nwave_ai import that breaks standalone deployment."
    )
