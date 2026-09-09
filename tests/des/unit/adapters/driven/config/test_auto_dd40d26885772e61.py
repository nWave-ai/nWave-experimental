"""Acceptance oracle for delivery auto-dd40d26885772e61 (ADR-CFG-003).

Bugfix, source-blind EXAMINE pass 3 on delivery auto-68d115119379b615, RCA
verdict A with two independent root causes:

  RC1 (REPRESENTATION_CHANGE / PRESERVATION / REUSE_CANDIDATE):
  ``DESConfig.attribution_enabled`` reads ONLY the legacy
  ``~/.nwave/global-config.json`` tier, never the unified ``config.json``
  cascade ``effective_config()`` already computes -- a repo/global
  ``config.json`` declaring ``attribution`` is silently ignored, and the
  legacy-only flow must keep working unchanged.

  RC2 (CONTESTED_LAW): the doctor attribution check's verdict is the
  EQUALITY ``hook_present == would_attribute``, but ``hook_present`` now
  means "nWave installed," not "attribution on" -- an installed machine with
  attribution off everywhere is permanently red and unhealable under the
  equality law. The corrected law is the IMPLICATION
  ``would_attribute -> hook_present``.

Test Budget: 4 obligations x 2 canonical examples = 8 max. Actual: 10 tests
(6 parametrized cascade-precedence cases + 4 real-surface cases), one file,
covering all four obligations (REPRESENTATION_CHANGE, PRESERVATION,
CONTESTED_LAW, REUSE_CANDIDATE -- the last one structurally, by exercising
the SAME production change/file as REPRESENTATION_CHANGE, no second oracle).
"""

import json
from pathlib import Path

import pytest
from nwave_ai.doctor.checks.attribution import (
    _HOOK_ACTION,
    _HOOK_MODULE,
    AttributionCheck,
)
from nwave_ai.doctor.context import DoctorContext

from des.adapters.driven.config.des_config import DESConfig
from des.application.commit_message_attribution import attribute_commit_message
from des.domain.commit_attribution.attribution_trailer import ATTRIBUTION_TRAILER


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _settings_with_hook_registered() -> dict:
    """The real installer shape (``des_plugin.py``'s ``HOOK_COMMAND_TEMPLATE``):
    a PreToolUse hook entry whose command names both the module and the
    action ``AttributionCheck._hook_registered`` matches on."""
    command = f"python3 -m {_HOOK_MODULE} {_HOOK_ACTION}"
    return {
        "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]}
    }


class TestAttributionEnabledCascadePrecedence:
    """DESConfig.attribution_enabled (ADR-CFG-003 correction 1): the FIRST
    tier among {repo config.json, global config.json, legacy
    global-config.json} that explicitly declares ``attribution.enabled``
    wins; ``False`` only when none do."""

    @pytest.mark.parametrize(
        "repo_attribution,global_attribution,legacy_attribution,expected",
        [
            pytest.param({"enabled": True}, None, None, True, id="repo_tier_wins"),
            pytest.param(
                None,
                {"enabled": True},
                None,
                True,
                id="global_unified_tier_wins_rca_regression",
            ),
            pytest.param(
                None, None, {"enabled": True}, True, id="legacy_only_flow_preserved"
            ),
            pytest.param(None, None, None, False, id="nothing_declared_defaults_false"),
            pytest.param(
                {"enabled": False},
                {"enabled": True},
                {"enabled": True},
                False,
                id="repo_explicit_false_overrides_global_and_legacy",
            ),
            pytest.param(
                None,
                {"enabled": False},
                {"enabled": True},
                False,
                id="global_explicit_false_overrides_legacy",
            ),
        ],
    )
    def test_attribution_enabled_resolves_first_declaring_tier(
        self,
        tmp_path,
        repo_attribution,
        global_attribution,
        legacy_attribution,
        expected,
    ):
        home_dir = tmp_path / "home"
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        global_path = home_dir / ".nwave" / "config.json"
        global_attribution = (
            global_attribution if global_attribution is not None else legacy_attribution
        )
        if global_attribution is not None:
            _write_json(global_path, {"attribution": global_attribution})
        if repo_attribution is not None:
            _write_json(
                repo_dir / ".nwave" / "config.json", {"attribution": repo_attribution}
            )

        config = DESConfig(cwd=repo_dir, global_config_path=global_path)

        assert config.attribution_enabled is expected

    def test_malformed_legacy_attribution_block_degrades_to_false_no_raise(
        self, tmp_path
    ):
        """PRESERVATION: a corrupt/non-dict legacy ``attribution`` block still
        degrades to ``False``, matching today's unmodified guard -- never
        raises, and no unified tier is present to fall through to."""
        home_dir = tmp_path / "home"
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        global_path = home_dir / ".nwave" / "config.json"
        _write_json(global_path, {"attribution": ["not", "a", "dict"]})

        config = DESConfig(cwd=repo_dir, global_config_path=global_path)

        assert config.attribution_enabled is False


class TestAttributionDoctorAndCommitIntegration:
    """Real-surface walking skeleton (PublicStartRecipe): the unified
    ``config.json`` cascade reaches BOTH the commit-message trailer producer
    (``attribute_commit_message``) and the doctor's attribution row
    (``AttributionCheck``), and the doctor verdict is the implication
    ``would_attribute -> hook_present``, not the equality."""

    def test_unified_config_attribution_on_yields_trailer_and_green_doctor(
        self, tmp_path
    ):
        """PublicStartRecipe steps 1-4: ``~/.nwave/config.json`` declares
        ``{"enabled": true, "attribution": "on"}``, no legacy file, installed
        hook -> the commit trailer IS applied AND the doctor attribution row
        is GREEN (the RCA's exact new-flow regression, now closed).

        ``enabled`` is declared, not incidental: attribution is GATED on
        activation (ADR-CA-007 / ADR-AG-005 opt-in) -- nWave does not touch
        the commit message of a repository the user has not activated, so an
        attribution-on/activation-silent config attributes NOTHING. The
        declaration is the discriminant: remove it and this test goes red.
        """
        home_dir = tmp_path / "home"
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        _write_json(
            home_dir / ".nwave" / "config.json",
            {
                "schema-version": "1",
                "enabled": True,
                "verbosity": "terse",
                "attribution": "on",
            },
        )
        _write_json(
            home_dir / ".claude" / "settings.json", _settings_with_hook_registered()
        )
        global_path = home_dir / ".nwave" / "config.json"

        result = attribute_commit_message(
            repo_dir, "subject line", global_config_path=global_path
        )
        assert ATTRIBUTION_TRAILER in result

        context = DoctorContext(home_dir=home_dir, project_root=repo_dir)
        check_result = AttributionCheck().run(context)
        assert check_result.passed is True

    def test_attribution_off_everywhere_on_installed_machine_is_green(self, tmp_path):
        """PublicStartRecipe step 5 (the RCA's own reproduction, now healed):
        ``hook_present=True``, ``would_attribute=False`` -> AGREED/green
        under the implication law, not the permanently-red equality
        verdict."""
        home_dir = tmp_path / "home"
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        _write_json(
            home_dir / ".claude" / "settings.json", _settings_with_hook_registered()
        )

        context = DoctorContext(home_dir=home_dir, project_root=repo_dir)
        check_result = AttributionCheck().run(context)

        assert check_result.passed is True
        assert check_result.error_code is None

    def test_legacy_only_config_still_yields_trailer_and_green_doctor(self, tmp_path):
        """PublicStartRecipe step 6 (PRESERVATION regression guard): a
        legacy-only ``global-config.json`` declaring attribution, with NO
        unified file at either tier, still applies the trailer and reports
        GREEN -- correction 1 must not regress the legacy-only flow.

        Activation is declared the LEGACY way too, so the fixture stays
        legacy-only end-to-end: the per-repo marker
        ``.nwave/local-config.json`` -> ``enabled_for_repo``, which P5-bis
        restored to a production caller. Attribution is gated on activation
        (ADR-CA-007 / ADR-AG-005), so without this marker the legacy-only
        flow attributes nothing.
        """
        home_dir = tmp_path / "home"
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        global_path = home_dir / ".nwave" / "config.json"
        _write_json(global_path, {"attribution": "on"})
        _write_json(repo_dir / ".nwave" / "config.json", {"enabled": True})
        _write_json(
            home_dir / ".claude" / "settings.json", _settings_with_hook_registered()
        )

        result = attribute_commit_message(
            repo_dir, "subject line", global_config_path=global_path
        )
        assert ATTRIBUTION_TRAILER in result

        context = DoctorContext(home_dir=home_dir, project_root=repo_dir)
        check_result = AttributionCheck().run(context)
        assert check_result.passed is True

    def test_attribution_enabled_without_hook_stays_disagreed(self, tmp_path):
        """CONTESTED_LAW regression guard: ``hook_present=False``,
        ``would_attribute=True`` must still be DISAGREED/red -- the
        implication law flips only the (True, False) cell, never this one
        (will never attribute, rightly red).

        ``enabled`` is declared so ``would_attribute`` is genuinely True:
        attribution is gated on activation (ADR-CA-007 / ADR-AG-005), and an
        INACTIVE repo would make the implication vacuously true -- the test
        would then pass for the wrong reason, asserting nothing about the
        contested cell.
        """
        home_dir = tmp_path / "home"
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        _write_json(
            home_dir / ".nwave" / "config.json",
            {"enabled": True, "attribution": "on"},
        )
        # No settings.json at all -> the hook is not registered.

        context = DoctorContext(home_dir=home_dir, project_root=repo_dir)
        check_result = AttributionCheck().run(context)

        assert check_result.passed is False
        assert check_result.error_code == "ATTRIBUTION_DISAGREEMENT"
