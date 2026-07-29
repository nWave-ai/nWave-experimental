"""Fixtures + parser converters for the attribution-activation-coupling suite.

The single ``composition`` fixture builds the production composition root over a
``tmp_path`` project + sandbox HOME. HOME is redirected so the real
``AttributionPlugin``, the real ``attribution on|off|status`` CLI, the real
``AttributionCheck`` doctor check, and the reused ``DESConfig`` all resolve the
sandbox ``~/.claude`` + ``~/.nwave`` — NEVER the operator's real home.

Parser converters coerce Gherkin literals into the typed ``domain_types`` enums
so step bodies stay logic-free (Mandate-12 criterion 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .composition import AttributionCouplingComposition


def pytest_bdd_apply_tag(tag: str, function):
    """Own only ``@skip``; defer every other tag to the root terminal handler.

    ``@skip`` marks a scenario pending (one-at-a-time unskip in DELIVER) and the
    root hook cannot do this (``skip`` is a builtin, not a registered ini
    marker), so this track owns it. Every other tag (`@ab-N`, `@driving_port`,
    `@error`, `@real-io`, `@contract-shape:*`, `@walking_skeleton`,
    feature-level descriptors) is returned as ``None`` so the chain falls
    through to the root ``tests/conftest.py`` (``pytest_bdd_apply_tag`` is
    ``firstresult``; per-dir conftests fire first via LIFO). The root applies
    registered markers and absorbs descriptive gherkin metadata under
    ``--strict-markers``. Blanket-absorbing foreign tags here (returning
    ``True`` for everything — the WTBD-165 defect) swallowed the bugs-track
    ``@failing`` tag before root could route it to xfail.
    """
    if tag == "skip":
        marker = pytest.mark.skip(reason="DISTILL scaffold — unskip in DELIVER")
        marker(function)
        return True
    return None


@pytest.fixture
def composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AttributionCouplingComposition:
    """Production composition root over an isolated project + sandbox HOME."""
    project_root = tmp_path / "project"
    home_dir = tmp_path / "home"
    project_root.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    # nwave_ai.cli._handle_attribution resolves claude_dir via
    # PathUtils.get_claude_config_dir(), which honors CLAUDE_CONFIG_DIR. On a
    # multi-profile dev machine that env var overrides the HOME/Path.home
    # sandboxing above unless scrubbed here too (same isolation as
    # tests/installer/unit/cli/test_target_flag.py::_scrub_env).
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return AttributionCouplingComposition(home_dir=home_dir, project_root=project_root)
