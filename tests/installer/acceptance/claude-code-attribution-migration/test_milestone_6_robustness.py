"""Binder — robustness / graceful degradation (Q5, malformed config)."""

from pytest_bdd import scenario


@scenario(
    "milestone-6-robustness.feature",
    "Claude Code not installed yet leaves the machine untouched",
)
def test_robustness_claude_absent():
    """Q5 (ADR-CA-007) — ~/.claude absent → install degrades gracefully;
    no machine change, no preference recorded, install still succeeds."""


@scenario(
    "milestone-6-robustness.feature",
    "A corrupt Claude configuration is not stomped on install",
)
def test_robustness_malformed_settings():
    """Robustness — malformed Claude config is not overwritten."""
