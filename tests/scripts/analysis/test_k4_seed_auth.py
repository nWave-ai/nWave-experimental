"""The K4 login seed carries one account and one isolated trust decision."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

from scripts.analysis.k4 import preflight, seed_auth
from scripts.analysis.k4 import subject as k4_subject


def test_seed_carries_identity_trust_and_shared_sandbox_settings(tmp_path, monkeypatch):
    source = tmp_path / "source"
    checkout = tmp_path / "pair" / "nwave"
    target = checkout / ".claude-k4"
    source.mkdir()
    checkout.mkdir(parents=True)
    (source / ".credentials.json").write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": "subscription-token",
                    "subscriptionType": "max",
                },
                "mcpOauth": {"unrelated": "must-not-copy"},
            }
        ),
        encoding="utf-8",
    )
    (source / ".claude.json").write_text(
        json.dumps(
            {
                "oauthAccount": {"email": "owner@example.test"},
                "userID": "owner-id",
                "hasCompletedOnboarding": True,
                "projects": {"/real/project": {"hasTrustDialogAccepted": True}},
                "mcpServers": {"unrelated": {}},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("PATH", "/sandbox/bin:/usr/bin")
    assert seed_auth.seed(source, target, trust_project=checkout) == 0

    credentials = json.loads((target / ".credentials.json").read_text())
    config = json.loads((target / ".claude.json").read_text())
    assert credentials == {
        "claudeAiOauth": {
            "accessToken": "subscription-token",
            "subscriptionType": "max",
        }
    }
    assert config == {
        "oauthAccount": {"email": "owner@example.test"},
        "userID": "owner-id",
        "hasCompletedOnboarding": True,
        "projects": {str(checkout.resolve()): {"hasTrustDialogAccepted": True}},
    }
    settings = json.loads((target / "settings.json").read_text())
    assert settings["env"]["PATH"] == "/sandbox/bin:/usr/bin"
    assert settings["sandbox"]["failIfUnavailable"] is True
    assert settings["sandbox"]["enabled"] is True
    assert settings["sandbox"]["allowUnsandboxedCommands"] is False
    assert settings["sandbox"]["filesystem"] == {
        "denyRead": [
            "~/",
            "/mnt/c/Users",
            "/root",
            "./.credentials.json",
            "./.claude.json",
        ],
        "allowRead": [str(checkout.resolve())],
        "denyWrite": ["."],
    }
    assert settings["permissions"]["allow"] == [
        "Read",
        "Edit",
        "Write",
        "Bash",
        "Agent",
    ]
    assert settings["permissions"]["deny"] == [
        "Read(/.claude-k4/.credentials.json)",
        "Read(/.claude-k4/.claude.json)",
        "Edit(./.claude-k4/**)",
        "Write(./.claude-k4/**)",
        "WebFetch",
        "WebSearch",
    ]
    assert stat.S_IMODE((target / ".credentials.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((target / ".claude.json").stat().st_mode) == 0o600
    assert preflight.seed_step(source)[-2:] == ["--trust-project", "."]


def test_seed_script_runs_by_path_from_an_external_working_directory(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".credentials.json").write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token"}}), encoding="utf-8"
    )
    (source / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"email": "owner@example.test"}}),
        encoding="utf-8",
    )
    external = tmp_path / "Healthchecks"
    external.mkdir()
    target = external / ".claude-k4"
    script = Path(seed_auth.__file__).resolve()

    done = subprocess.run(
        [
            sys.executable,
            str(script),
            "--from",
            str(source),
            "--into",
            str(target),
            "--trust-project",
            ".",
        ],
        cwd=external,
        text=True,
        capture_output=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    settings = json.loads((target / "settings.json").read_text())
    assert settings["sandbox"]["filesystem"]["allowRead"] == [str(external.resolve())]
    assert settings["sandbox"]["network"]["allowedDomains"] == list(
        k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS
    )
    # The hermetic property the task states is what this guards, not the list's
    # length: an arm that could fetch packages would not be the subject.
    assert not [
        domain
        for domain in settings["sandbox"]["network"]["allowedDomains"]
        if "pypi" in domain or "npm" in domain
    ]
