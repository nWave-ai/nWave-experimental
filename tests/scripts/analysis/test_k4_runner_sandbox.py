"""The paired K4 runner exposes the product, never the operator's machine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.k4 import preflight
from scripts.analysis.paired_campaign import ArmSpec


def _value_after(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def test_delivery_runner_is_identical_fail_closed_and_subscription_safe():
    argv = preflight.delivery_argv("claude-sonnet-5", "/probe/bin:/usr/bin")

    assert "--dangerously-skip-permissions" not in argv
    assert _value_after(argv, "--permission-mode") == "dontAsk"
    assert _value_after(argv, "--tools") == "default"
    assert _value_after(argv, "--setting-sources") == "user"
    assert "--strict-mcp-config" in argv
    assert json.loads(_value_after(argv, "--mcp-config")) == {"mcpServers": {}}

    settings = json.loads(_value_after(argv, "--settings"))
    assert settings["env"] == {"PATH": "/probe/bin:/usr/bin"}
    assert settings["sandbox"] == {
        "allowUnsandboxedCommands": False,
        "enabled": True,
        "failIfUnavailable": True,
        "filesystem": {
            "allowRead": ["."],
            "denyWrite": ["./.claude-k4"],
            "denyRead": [
                "~/",
                "/mnt/c/Users",
                "/root",
                "./.claude-k4/.credentials.json",
                "./.claude-k4/.claude.json",
            ],
        },
        "network": {"allowedDomains": ["localhost", "127.0.0.1", "[::1]"]},
    }
    assert settings["permissions"] == {
        "allow": ["Read", "Edit", "Write", "Bash", "Agent"],
        "deny": [
            "Read(/.claude-k4/.credentials.json)",
            "Read(/.claude-k4/.claude.json)",
            "Edit(./.claude-k4/**)",
            "Write(./.claude-k4/**)",
            "WebFetch",
            "WebSearch",
        ],
    }


def test_permission_canary_proves_effective_write_edit_and_config_denial(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    (workspace / ".claude-k4").mkdir(parents=True)

    class _Completed:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "is_error": False,
                "result": preflight._PERMISSION_CANARY_RESULT,
            }
        )

    def _successful_runner(argv, *, cwd: Path, env, timeout, **kwargs):
        assert cwd == workspace
        assert timeout == 180
        assert env["CLAUDE_CONFIG_DIR"] == str(workspace / ".claude-k4")
        assert any("Permission canary only" in token for token in argv)
        (workspace / "k4-permission-edit.txt").write_text("CANARY_AFTER\n")
        (workspace / "k4-permission-write.txt").write_text("CANARY_WRITE_OK\n")
        return _Completed()

    monkeypatch.setattr(preflight.subprocess, "run", _successful_runner)

    assert preflight.probe_delivery_permissions(workspace, "claude-sonnet-5") == []
    assert not (workspace / "k4-permission-edit.txt").exists()
    assert not (workspace / "k4-permission-write.txt").exists()
    assert not (workspace / ".claude-k4/k4-permission-denied.txt").exists()


def test_permission_canary_refuses_claim_without_observed_files(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    (workspace / ".claude-k4").mkdir(parents=True)

    class _ClaimOnly:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "is_error": False,
                "result": preflight._PERMISSION_CANARY_RESULT,
            }
        )

    monkeypatch.setattr(
        preflight.subprocess, "run", lambda *args, **kwargs: _ClaimOnly()
    )

    problems = preflight.probe_delivery_permissions(workspace, "claude-sonnet-5")

    assert "Edit did not mutate the in-workspace sentinel" in problems
    assert "Write did not create the in-workspace sentinel" in problems


def test_arm_environment_scrubs_provider_credentials_from_bash(monkeypatch):
    monkeypatch.setenv("PATH", "/sandbox-tools:/usr/bin:/bin")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/sandbox-tools/lib")

    environment = preflight._arm_env()

    assert environment["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] == "{workspace}"
    assert environment["LD_LIBRARY_PATH"] == (
        "{workspace}/.k4-sandbox-lib:/sandbox-tools/lib"
    )
    assert environment["PATH"].startswith(
        "{workspace}/k4-fixture-venv/bin:/sandbox-tools:"
    )


def test_delivery_settings_path_matches_arm_env_path_after_workspace_render(
    tmp_path, monkeypatch
):
    """The PATH Claude's startup preflight sees (the subprocess env) and the
    PATH its later socat bridge spawn sees (--settings env.PATH) must be the
    SAME bytes, or a bounded socat found by the preflight goes missing for
    the bridge spawn."""
    monkeypatch.setenv("PATH", "/sandbox-tools:/usr/bin:/bin")
    workspace = tmp_path / "workspace"
    arm_env = preflight._arm_env()
    arm = ArmSpec(
        "nwave",
        tuple(preflight.delivery_argv("claude-sonnet-5", arm_env["PATH"])),
        (),
        tuple(sorted(arm_env.items())),
    )
    rendered_argv = arm.rendered("deliver the task", workspace)
    rendered_env = arm.rendered_env(workspace)
    settings = json.loads(_value_after(rendered_argv, "--settings"))

    assert settings["env"]["PATH"] == rendered_env["PATH"]
    assert "{workspace}" not in settings["env"]["PATH"]


def _write_executable(path):
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)


def test_missing_socat_is_a_sandbox_prerequisite_gap(tmp_path, monkeypatch):
    """A host without socat must be caught before a campaign is built, not
    discovered mid-delivery when the fail-closed sandbox refuses network."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "claude")
    monkeypatch.setenv("PATH", str(bin_dir))

    missing = preflight.missing_sandbox_prerequisites()

    assert missing == ["socat"]


def test_bounded_path_provided_socat_satisfies_the_gate(tmp_path, monkeypatch):
    """The fix is PATH, never a global install: a bounded, non-global `socat`
    staged into a directory that is prepended to PATH must be sufficient."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "claude")
    _write_executable(bin_dir / "socat")
    monkeypatch.setenv("PATH", str(bin_dir))

    assert preflight.missing_sandbox_prerequisites() == []


def test_preflight_main_refuses_before_writing_arms_json_when_socat_is_absent(
    tmp_path, monkeypatch
):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "claude")
    monkeypatch.setenv("PATH", str(bin_dir))

    def _refuse_any_setup(*_args, **_kwargs):
        raise AssertionError(
            "no packaging/probe step should run when a sandbox prerequisite is missing"
        )

    monkeypatch.setattr(preflight, "build_arm_runtime", _refuse_any_setup)
    monkeypatch.setattr(preflight, "build_arm_runtime_from_wheel", _refuse_any_setup)
    monkeypatch.setattr(preflight, "probe_engagement", _refuse_any_setup)

    root = tmp_path / "root"
    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")

    code = preflight.main(["--root", str(root), "--task-file", str(task_file)])

    assert code == 78
    assert not (root / "arms.json").exists()


def _arrange_engaged_nwave(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "nwave_setup_steps", lambda *_args: [["setup"]])

    def setup_succeeds(_step, *, cwd: Path, **_kwargs):
        (cwd / "CLAUDE.md").write_text(preflight._SECTION_MARKER)
        for name in ("agents", "skills"):
            directory = cwd / ".claude-k4" / name
            directory.mkdir(parents=True)
            (directory / "installed").write_text("present\n")
        return 0, ""

    monkeypatch.setattr(preflight, "_run", setup_succeeds)


def test_broken_installed_dispatch_refuses_before_permission_probe(
    tmp_path, monkeypatch
):
    """probe_installed_dispatch_help catches dispatch entry point failures
    BEFORE probe_delivery_permissions runs, avoiding wasted model calls."""
    dispatch_problems = [
        "`des dispatch --help` exited 1 under the arm PATH: ModuleNotFoundError"
    ]

    def _broken_dispatch(workspace: Path, venv: Path) -> list[str]:
        return dispatch_problems

    def _permission_probe_should_not_run(*_args, **_kwargs):
        raise AssertionError("permission probe must not run when dispatch is broken")

    _arrange_engaged_nwave(monkeypatch)
    monkeypatch.setattr(preflight, "probe_installed_dispatch_help", _broken_dispatch)
    monkeypatch.setattr(
        preflight, "probe_delivery_permissions", _permission_probe_should_not_run
    )

    root = tmp_path / "root"
    root.mkdir(parents=True)
    venv = root / "nwave-venv"
    venv.mkdir()

    verdict, detail = preflight.probe_engagement(
        root, venv, Path.home() / ".claude-alt3", "claude-sonnet-5"
    )

    assert verdict == "broken-dispatch"
    assert detail == dispatch_problems


@pytest.mark.parametrize(
    ("permission_problems", "expected_verdict"),
    [
        pytest.param([], "present", id="ready"),
        pytest.param(["Write escaped into .claude-k4"], "unsafe", id="unsafe"),
    ],
)
def test_healthy_dispatch_proceeds_to_permission_probe(
    tmp_path, monkeypatch, permission_problems, expected_verdict
):
    """When dispatch --help succeeds, probe_engagement proceeds to the
    permission probe without stopping at the broken-dispatch verdict."""

    def _healthy_dispatch(workspace: Path, venv: Path) -> list[str]:
        return []

    def _permission_probe_runs(workspace: Path, model: str) -> list[str]:
        return permission_problems

    _arrange_engaged_nwave(monkeypatch)
    monkeypatch.setattr(preflight, "probe_installed_dispatch_help", _healthy_dispatch)
    monkeypatch.setattr(preflight, "probe_delivery_permissions", _permission_probe_runs)

    root = tmp_path / "root"
    root.mkdir(parents=True)
    venv = root / "nwave-venv"
    venv.mkdir()

    verdict, detail = preflight.probe_engagement(
        root, venv, Path.home() / ".claude-alt3", "claude-sonnet-5"
    )

    assert verdict == expected_verdict
    assert detail == permission_problems
