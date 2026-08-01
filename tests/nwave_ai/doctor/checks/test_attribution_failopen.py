"""Regression: doctor + CLI status fail OPEN to inactive (step 01-06).

The enforcement gate (resolve_activation under the opt-in default) resolves a
missing/corrupt config to INACTIVE — fail-safe, don't act. The two diagnostic
helpers must AGREE with the gate: on a config-read exception they must report
INACTIVE, never "active". A diagnostic that is more optimistic than the gate
lies about the system's real behaviour.

This module forces a resolution exception (DESConfig construction raising) and
asserts BOTH diagnostics fail to inactive:
  - doctor report line  -> "this repo activation: inactive"
  - `attribution status` -> "Attribution is inactive for this repo."
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from nwave_ai.doctor.checks.attribution import AttributionCheck
from nwave_ai.doctor.context import DoctorContext

from nwave_ai import cli


if TYPE_CHECKING:
    from pathlib import Path


def _raise(*_args: object, **_kwargs: object) -> object:
    raise RuntimeError("forced config-read failure")


@pytest.fixture()
def context(tmp_path: Path) -> DoctorContext:
    return DoctorContext(home_dir=tmp_path, project_root=tmp_path)


# ---------------------------------------------------------------------------
# shared fixtures-as-preconditions for the P7 three-valued-verdict tests below
# ---------------------------------------------------------------------------

#: Matches AttributionCheck._HOOK_MARKER ("pre-commit-attribution") -- the
#: SAME substring register_attribution_hook() writes into settings.json's
#: hooks.PreToolUse[].hooks[].command (scripts/install/attribution_utils.py).
_HOOK_COMMAND = (
    "PYTHONPATH=$HOME/.claude/lib/python python3 -m "
    "des.adapters.drivers.hooks.claude_code_hook_adapter pre-commit-attribution"
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _declare_attribution_enabled(global_config_path: Path, *, enabled: bool) -> None:
    """Write ``~/.nwave/global-config.json`` -> ``attribution.enabled``."""
    _write_json(global_config_path, {"attribution": {"enabled": enabled}})


def _activate_repo(project_root: Path) -> None:
    """Write the per-project activation marker, enabled (ADR-AG-002)."""
    _write_json(
        project_root / ".nwave" / "local-config.json", {"enabled_for_repo": True}
    )


def _register_hook(settings_path: Path) -> None:
    """Write settings.json with the pre-commit-attribution hook present."""
    _write_json(
        settings_path,
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": _HOOK_COMMAND}],
                    }
                ]
            }
        },
    )


def _no_hook_registered(settings_path: Path) -> None:
    """Write settings.json with an empty PreToolUse list (hook absent)."""
    _write_json(settings_path, {"hooks": {"PreToolUse": []}})


def test_doctor_reports_inactive_when_activation_resolution_raises(
    context: DoctorContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor fails OPEN to inactive when the config read raises.

    A config-read failure must surface as 'inactive' — matching the gate's
    fail-to-inactive-under-opt-in semantics, never the more optimistic 'active'.
    """
    monkeypatch.setattr(
        "des.adapters.driven.config.des_config.DESConfig",
        _raise,
    )

    result = AttributionCheck().run(context)

    assert "this repo activation: inactive" in result.message
    assert "this repo activation: active" not in result.message


def test_cli_status_reports_inactive_when_activation_resolution_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`attribution status` (preference on) fails OPEN to inactive on a read error.

    With the preference ON, a config-read failure must print 'inactive for this
    repo', agreeing with the gate — never 'active'.
    """
    monkeypatch.setattr(cli, "read_attribution_preference", lambda _config_dir: True)
    monkeypatch.setattr(
        "des.adapters.driven.config.des_config.DESConfig",
        _raise,
    )

    exit_code = cli._handle_attribution(["status"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Attribution is inactive for this repo." in out
    assert "Attribution is active for this repo." not in out


# ---------------------------------------------------------------------------
# P7 -- AttributionCheck.run() must be a THREE-VALUED verdict (AGREED /
# DISAGREED / COULD_NOT_VERIFY), never the unconditional passed=True the
# check's own docstring currently admits to ("It is a diagnostic, not a
# gate: it always reports passed=True").
#
# Two axes are observed (GDP-8 witness corollary -- the Bash-hook axis alone
# is what went stale):
#   (a) is the pre-commit-attribution PreToolUse hook registered in
#       settings.json -- AttributionCheck._hook_registered.
#   (b) does the producing-tool resolver now attribute for this repo -- the
#       SAME resolution `attribute_commit_message` performs (activation AND
#       attribution.enabled), landed by slice-01.
#
# Verdict = compare the two axes: agree (both live, or both dark) -> AGREED
# (passed=True); disagree -> DISAGREED (passed=False, error_code, WHAT/WHY/HOW
# remediation naming `nwave-ai attribution on`, the real producing-tool
# command for the preference, GDP-4); resolution itself fails -> COULD_NOT_VERIFY
# (passed=False, reaching the aggregate per the GDP-8 arity corollary --
# never silently absorbed back into AGREED).
# ---------------------------------------------------------------------------


class TestAttributionCheckThreeValuedVerdict:
    def test_attribution_check_reports_disagreed_when_enabled_but_hook_not_registered(
        self, context: DoctorContext
    ) -> None:
        """The exact live defect demonstrated in the dispatch: declared
        enabled + repo ACTIVE (both promise attribution), but the hook axis
        is dark. `run()` must surface passed=False -- not the unconditional
        True it returns today.
        """
        _declare_attribution_enabled(context.global_config_path, enabled=True)
        _activate_repo(context.project_root)
        _no_hook_registered(context.settings_path)

        result = AttributionCheck().run(context)

        assert result.passed is False
        assert result.error_code == "ATTRIBUTION_DISAGREEMENT"
        assert result.remediation is not None
        assert "nwave-ai attribution on" in result.remediation

    def test_attribution_check_agrees_when_declared_enabled_and_both_axes_live(
        self, context: DoctorContext
    ) -> None:
        """AGREED (i): declared enabled + repo ACTIVE + hook registered --
        both axes live, nothing promised is missing.
        """
        _declare_attribution_enabled(context.global_config_path, enabled=True)
        _activate_repo(context.project_root)
        _register_hook(context.settings_path)

        result = AttributionCheck().run(context)

        assert result.passed is True
        assert result.error_code is None
        assert result.remediation is None

    def test_attribution_check_agrees_when_declared_disabled_and_neither_axis_live(
        self, context: DoctorContext
    ) -> None:
        """AGREED (ii): declared NOT enabled + repo inactive (no marker,
        default opt-in mode) + hook not registered -- nothing promised,
        nothing missing, not a disagreement.
        """
        _declare_attribution_enabled(context.global_config_path, enabled=False)
        # no activation marker written -> inactive under the default opt-in mode
        _no_hook_registered(context.settings_path)

        result = AttributionCheck().run(context)

        assert result.passed is True
        assert result.error_code is None
        assert result.remediation is None

    def test_attribution_check_reports_could_not_verify_when_resolution_raises(
        self, context: DoctorContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COULD_NOT_VERIFY: a genuine config-read failure that prevents
        observing axis (b) must reach the aggregate as ITS OWN third state --
        `passed=False`, never silently folded into the AGREED passed=True
        default (GDP-8 arity corollary). Distinct `error_code` from
        DISAGREED so a caller can tell "known gap" apart from "could not
        look".
        """
        _register_hook(context.settings_path)  # axis (a) is irrelevant here
        monkeypatch.setattr(
            "des.adapters.driven.config.des_config.DESConfig",
            _raise,
        )

        result = AttributionCheck().run(context)

        assert result.passed is False
        assert result.error_code == "ATTRIBUTION_UNVERIFIABLE"
        assert result.error_code != "ATTRIBUTION_DISAGREEMENT"

    def test_attribution_check_never_writes_settings_or_global_config(
        self, context: DoctorContext
    ) -> None:
        """Read-only invariant (ADR-CA-007 / the check's own docstring: "It
        never mutates settings.json"): the three-valued verdict must not
        tempt an implementation into auto-fixing the disagreement it
        reports. Exercised on the exact DISAGREED-triggering precondition,
        where a well-intentioned auto-remediation would be most tempting.
        """
        _declare_attribution_enabled(context.global_config_path, enabled=True)
        _activate_repo(context.project_root)
        _no_hook_registered(context.settings_path)

        settings_before = context.settings_path.read_text(encoding="utf-8")
        settings_mtime_before = context.settings_path.stat().st_mtime_ns
        global_config_before = context.global_config_path.read_text(encoding="utf-8")
        global_config_mtime_before = context.global_config_path.stat().st_mtime_ns

        AttributionCheck().run(context)

        assert context.settings_path.read_text(encoding="utf-8") == settings_before
        assert context.settings_path.stat().st_mtime_ns == settings_mtime_before
        assert (
            context.global_config_path.read_text(encoding="utf-8")
            == global_config_before
        )
        assert (
            context.global_config_path.stat().st_mtime_ns == global_config_mtime_before
        )
