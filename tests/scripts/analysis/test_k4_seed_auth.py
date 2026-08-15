"""The K4 login seed carries one account and one isolated trust decision."""

from __future__ import annotations

import json
import stat

from scripts.analysis.k4 import preflight, seed_auth


def test_seed_carries_only_subscription_identity_and_exact_campaign_trust(tmp_path):
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
    assert stat.S_IMODE((target / ".credentials.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((target / ".claude.json").stat().st_mode) == 0o600
    assert preflight.seed_step(source)[-2:] == ["--trust-project", "."]
