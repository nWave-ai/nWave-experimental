"""The K4 login seed carries one account and one isolated trust decision."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

from scripts.analysis.k4 import preflight, seed_auth


def test_seed_carries_identity_trust_and_shared_sandbox_settings(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    checkout = tmp_path / "pair" / "nwave"
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
    assert settings["permissions"]["allow"] == [
        "Read",
        "Edit",
        "Write",
        "Bash",
        "Agent",
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
    assert settings["sandbox"]["network"]["allowedDomains"] == [
        "localhost",
        "127.0.0.1",
        "[::1]",
    ]
