"""Active K4 environment and installed-launcher safety properties."""

from __future__ import annotations

import shutil
import sys

from scripts.analysis.k4 import preflight
from scripts.analysis.paired_campaign import ArmSpec


def test_arm_environment_scrubs_provider_credentials_from_bash(monkeypatch):
    monkeypatch.setenv("PATH", "/sandbox-tools:/usr/bin:/bin")
    environment = preflight._arm_env()
    assert environment["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] == "{workspace}"
    assert environment["PATH"].startswith("{workspace}/.claude-k4/bin:")


def test_control_uses_the_same_isolated_profile_as_its_arm(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/sandbox-tools:/usr/bin:/bin")
    workspace = tmp_path / "workspace"
    arm_env = preflight._arm_env()
    arm = ArmSpec(
        "control",
        tuple(preflight.delivery_argv("claude-opus-5")),
        (),
        tuple(sorted(arm_env.items())),
    )
    assert "--settings" not in arm.rendered(workspace)
    assert arm.rendered_env(workspace)["CLAUDE_CONFIG_DIR"] == str(
        workspace / ".claude-k4"
    )


def test_missing_socat_is_a_fail_closed_prerequisite(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    assert preflight.missing_sandbox_prerequisites() == ["socat"]


def test_arm_env_path_resolves_the_installed_des_shim(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    bin_dir = workspace / ".claude-k4" / "bin"
    bin_dir.mkdir(parents=True)
    des = bin_dir / "des"
    des.write_text(f"#!{sys.executable}\nprint('des')\n")
    des.chmod(0o755)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    rendered = preflight._arm_env()["PATH"].replace("{workspace}", str(workspace))
    assert shutil.which("des", path=rendered) == str(des)
