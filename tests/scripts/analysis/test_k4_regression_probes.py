"""Each probe must REJECT the broken configuration that made it necessary.

Three corrections were measured on 2026-09-13/14, each of which had made every
campaign this project ever bought unable to exercise the method. Only the first
had a probe. These checks hold the other two, and each one reconstructs the
exact broken state rather than a plausible-looking stand-in:

- the launcher as a SYMLINK to somewhere outside the workspace, which a plain
  harness probe resolves happily and a delivery cannot see at all;
- the allowlist with localhost alone, which returns 403 to every nested turn.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_K4 = Path(__file__).resolve().parents[3] / "scripts" / "analysis" / "k4"
sys.path.insert(0, str(_K4))

import preflight
import seed_auth
import subject as k4_subject


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / ".claude-k4" / "bin").mkdir(parents=True)
    return tmp_path


def _settings(workspace: Path, domains: list[str]) -> None:
    (workspace / ".claude-k4" / "settings.json").write_text(
        json.dumps({"sandbox": {"network": {"allowedDomains": domains}}}),
        encoding="utf-8",
    )


def _filesystem_settings(workspace: Path, filesystem: dict[str, list[str]]) -> None:
    config_dir = workspace / ".claude-k4"
    config_dir.mkdir(parents=True, exist_ok=True)
    for name in (".credentials.json", ".claude.json"):
        (config_dir / name).write_text("{}\n", encoding="utf-8")
    (config_dir / "settings.json").write_text(
        json.dumps({"sandbox": {"filesystem": filesystem}}), encoding="utf-8"
    )


def test_a_symlinked_launcher_is_rejected(tmp_path) -> None:
    """The broken shape: resolvable by the harness, invisible to the delivery."""
    workspace = _workspace(tmp_path)
    outside = tmp_path / "elsewhere" / "claude"
    outside.parent.mkdir(parents=True)
    outside.write_text("#!/bin/sh\nexit 0\n")
    outside.chmod(0o755)
    (workspace / ".claude-k4" / "bin" / "claude").symlink_to(outside)

    problems = preflight.probe_launcher_is_inside_the_workspace(workspace)
    assert problems
    assert "SYMLINK" in problems[0]


def test_an_absent_launcher_is_rejected(tmp_path) -> None:
    problems = preflight.probe_launcher_is_inside_the_workspace(_workspace(tmp_path))
    assert problems and "no launcher" in problems[0]


def test_a_copied_executable_launcher_is_accepted(tmp_path) -> None:
    workspace = _workspace(tmp_path)
    launcher = workspace / ".claude-k4" / "bin" / "claude"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)

    assert preflight.probe_launcher_is_inside_the_workspace(workspace) == []


def test_a_copied_but_unexecutable_launcher_is_rejected(tmp_path) -> None:
    workspace = _workspace(tmp_path)
    launcher = workspace / ".claude-k4" / "bin" / "claude"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o644)

    problems = preflight.probe_launcher_is_inside_the_workspace(workspace)
    assert problems and "not executable" in problems[0]


def test_a_localhost_only_allowlist_is_rejected(tmp_path) -> None:
    """The broken shape: every nested role turn returns 403."""
    workspace = _workspace(tmp_path)
    _settings(workspace, ["localhost", "127.0.0.1", "[::1]"])

    problems = preflight.probe_sandbox_allows_the_model_api(workspace)
    assert problems
    assert "403" in problems[0]


def test_the_declared_allowlist_is_accepted(tmp_path) -> None:
    workspace = _workspace(tmp_path)
    _settings(workspace, list(k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS))

    assert preflight.probe_sandbox_allows_the_model_api(workspace) == []


def test_an_allowlist_reaching_a_package_index_is_rejected(tmp_path) -> None:
    """The subject's hermetic property is what the task states; hold it."""
    workspace = _workspace(tmp_path)
    _settings(
        workspace,
        [*k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS, "pypi.org"],
    )

    problems = preflight.probe_sandbox_allows_the_model_api(workspace)
    assert problems and "package index" in problems[0]


def test_absent_settings_are_rejected_not_assumed_sound(tmp_path) -> None:
    problems = preflight.probe_sandbox_allows_the_model_api(_workspace(tmp_path))
    assert problems and "no rendered settings" in problems[0]


def test_the_old_workspace_relative_filesystem_policy_is_rejected(tmp_path) -> None:
    """2.1.271 resolves these relative entries from CLAUDE_CONFIG_DIR."""
    workspace = _workspace(tmp_path)
    _filesystem_settings(
        workspace,
        {
            "denyRead": [
                "~/",
                "/mnt/c/Users",
                "/root",
                "./.claude-k4/.credentials.json",
                "./.claude-k4/.claude.json",
            ],
            "allowRead": ["."],
            "denyWrite": ["./.claude-k4"],
        },
    )

    problems = preflight.probe_sandbox_filesystem_policy(workspace)

    assert problems
    assert any("nested .claude-k4/.claude-k4" in problem for problem in problems)
    assert any("denyWrite does not resolve exactly" in problem for problem in problems)


def test_the_workspace_readable_config_relative_filesystem_policy_is_accepted(
    tmp_path,
) -> None:
    workspace = _workspace(tmp_path)
    filesystem = seed_auth._sandbox_settings(workspace / ".claude-k4")["sandbox"][
        "filesystem"
    ]
    assert isinstance(filesystem, dict)
    _filesystem_settings(workspace, filesystem)

    assert preflight.probe_sandbox_filesystem_policy(workspace) == []


@pytest.mark.parametrize("removed", ["~/", "/mnt/c/Users", "/root"])
def test_removing_an_external_filesystem_deny_is_rejected(tmp_path, removed) -> None:
    workspace = _workspace(tmp_path)
    filesystem = seed_auth._sandbox_settings(workspace / ".claude-k4")["sandbox"][
        "filesystem"
    ]
    assert isinstance(filesystem, dict)
    deny_read = [entry for entry in filesystem["denyRead"] if entry != removed]
    _filesystem_settings(workspace, {**filesystem, "denyRead": deny_read})

    problems = preflight.probe_sandbox_filesystem_policy(workspace)

    assert any(f"required external deny {removed!r}" in problem for problem in problems)
