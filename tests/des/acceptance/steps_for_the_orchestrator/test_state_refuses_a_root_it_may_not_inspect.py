"""`des state` on a repository root it may not inspect answers a closed block.

ADR-DES-003 §4 class C: the filesystem did not answer whether the root is a
repository top level, so the step cannot tell -- the disposition is
Indeterminate under the substrate's one `*Unavailable` name, and the terminal
is WHAT / WHY / HOW, never a PermissionError traceback.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    asked,
    base_repository,
    block,
    nexts,
)


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores mode bits, so a mode-000 root stays inspectable",
)
def test_state_on_a_mode_000_root_is_indeterminate_and_says_permission_denied(
    step, turns: Path, tmp_path: Path
):
    locked = base_repository(tmp_path / "locked").resolve()
    locked.chmod(0o000)
    try:
        code, stdout, stderr = step("state", "--repo-root", str(locked))
    finally:
        locked.chmod(0o755)

    assert "Traceback" not in stdout + stderr
    assert "PermissionError" not in stdout + stderr
    rows = block(stdout)
    assert rows.get("DELIVERY-OUTCOME") == "Indeterminate", stdout + stderr
    assert rows.get("WHAT") == "RepositoryRootUnavailable"
    why = rows.get("WHY", "")
    assert why.startswith(f"permission denied inspecting {locked}: "), why
    assert "cannot tell whether it is a repository top level" in why
    assert "Permission denied" in why
    how = rows.get("HOW", "")
    assert f"chmod u+rx {locked}" in how, how
    assert "des state" in how
    assert rows.get("TURNS-BOUGHT") == "0"
    assert nexts(stdout) == ["des state --repo-root <root> -- after the HOW above"]
    assert all("des po" not in n and "des oracle" not in n for n in nexts(stdout))
    assert code != 0
    assert asked(turns) == []
