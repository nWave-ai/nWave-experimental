"""The paired K4 runner exposes the product, never the operator's machine."""

from __future__ import annotations

import json

from scripts.analysis.k4 import preflight


def _value_after(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def test_delivery_runner_is_identical_fail_closed_and_subscription_safe():
    argv = preflight.delivery_argv("claude-sonnet-5")

    assert "--dangerously-skip-permissions" not in argv
    assert _value_after(argv, "--permission-mode") == "dontAsk"
    assert _value_after(argv, "--tools") == "default"
    assert _value_after(argv, "--setting-sources") == "user"
    assert "--strict-mcp-config" in argv
    assert json.loads(_value_after(argv, "--mcp-config")) == {"mcpServers": {}}

    settings = json.loads(_value_after(argv, "--settings"))
    assert settings["sandbox"] == {
        "allowUnsandboxedCommands": False,
        "enabled": True,
        "failIfUnavailable": True,
        "filesystem": {
            "allowRead": ["."],
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
    assert "Read(/.claude-k4/.credentials.json)" in settings["permissions"]["deny"]
    assert "Edit(/.claude-k4/**)" in settings["permissions"]["deny"]
    assert "Write(/.claude-k4/**)" in settings["permissions"]["deny"]
    assert "WebFetch" in settings["permissions"]["deny"]
    assert "WebSearch" in settings["permissions"]["deny"]


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
