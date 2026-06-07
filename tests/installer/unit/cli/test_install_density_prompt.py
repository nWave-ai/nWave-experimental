"""Unit tests for install-time density prompt (D6 + AC-3.a..e).

Driving port: nwave_ai.cli.handle_install_density_prompt(...) — the pure
function the install subcommand calls. Driven port: ~/.nwave/global-config.json
on disk (real filesystem, tmp_path).

Test budget: 5 distinct behaviors x 2 = 10 max. Using 5 tests.

Per Decision 4 (2026-04-28), the default `expansion_prompt` is now
`ask-intelligent` (scoped trigger-based menu) rather than the broader
`ask`. The wave skill prose owns trigger detection.

Behaviors covered:
1. Fresh install + interactive  -> prompt fires, choice persisted
2. Fresh install + non-interactive (--yes) -> default "lean" written, no prompt
3. Existing config WITHOUT documentation key -> silent default lean (AC-3.e)
4. Existing config WITH documentation.density -> idempotent no-op (AC-3.c)
5. Persisted shape: {"documentation": {"density": ..., "expansion_prompt":"ask-intelligent"}}
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from nwave_ai.cli import handle_install_density_prompt


if TYPE_CHECKING:
    from pathlib import Path


def _read(config_path: Path) -> dict[str, Any]:
    return json.loads(config_path.read_text(encoding="utf-8"))


class TestInstallDensityPrompt:
    """Tests for handle_install_density_prompt — install-time D6 logic."""

    def test_fresh_install_interactive_prompts_and_persists_lean(
        self, tmp_path: Path
    ) -> None:
        """Behavior 1: no config + interactive -> prompt fires, lean persisted."""
        config_dir = tmp_path / ".nwave"

        with patch(
            "nwave_ai.cli._prompt_density_choice", return_value="lean"
        ) as prompt_mock:
            outcome = handle_install_density_prompt(
                config_dir=config_dir, non_interactive=False
            )

        prompt_mock.assert_called_once()
        assert outcome == "prompted"
        config = _read(config_dir / "global-config.json")
        assert config["documentation"]["density"] == "lean"
        # Per Decision 4 (2026-04-28), default expansion_prompt is now
        # "ask-intelligent" (scoped trigger-based menu).
        assert config["documentation"]["expansion_prompt"] == "ask-intelligent"

    def test_fresh_install_non_interactive_defaults_to_lean_without_prompt(
        self, tmp_path: Path
    ) -> None:
        """Behavior 2: no config + --yes -> silent lean default (AC-3.d)."""
        config_dir = tmp_path / ".nwave"

        with patch("nwave_ai.cli._prompt_density_choice") as prompt_mock:
            outcome = handle_install_density_prompt(
                config_dir=config_dir, non_interactive=True
            )

        prompt_mock.assert_not_called()
        assert outcome == "default_silent"
        config = _read(config_dir / "global-config.json")
        assert config["documentation"]["density"] == "lean"
        # Per Decision 4: silent default uses ask-intelligent.
        assert config["documentation"]["expansion_prompt"] == "ask-intelligent"

    def test_upgrade_path_silent_default_when_documentation_key_absent(
        self, tmp_path: Path
    ) -> None:
        """Behavior 3: existing config without documentation -> silent lean (AC-3.e)."""
        config_dir = tmp_path / ".nwave"
        config_dir.mkdir()
        config_path = config_dir / "global-config.json"
        config_path.write_text(
            json.dumps({"attribution": {"enabled": False}}), encoding="utf-8"
        )

        with patch("nwave_ai.cli._prompt_density_choice") as prompt_mock:
            outcome = handle_install_density_prompt(
                config_dir=config_dir, non_interactive=False
            )

        prompt_mock.assert_not_called()
        assert outcome == "upgrade_silent"
        config = _read(config_path)
        # Original key preserved.
        assert config["attribution"] == {"enabled": False}
        # Density block written. Per Decision 4: ask-intelligent default.
        assert config["documentation"]["density"] == "lean"
        assert config["documentation"]["expansion_prompt"] == "ask-intelligent"

    def test_idempotent_no_op_when_density_already_set(self, tmp_path: Path) -> None:
        """Behavior 4: existing density -> no prompt, no write (AC-3.c)."""
        config_dir = tmp_path / ".nwave"
        config_dir.mkdir()
        config_path = config_dir / "global-config.json"
        original_payload = {
            "documentation": {"density": "full", "expansion_prompt": "always-expand"}
        }
        config_path.write_text(json.dumps(original_payload), encoding="utf-8")
        before_text = config_path.read_text(encoding="utf-8")

        with patch("nwave_ai.cli._prompt_density_choice") as prompt_mock:
            outcome = handle_install_density_prompt(
                config_dir=config_dir, non_interactive=False
            )

        prompt_mock.assert_not_called()
        assert outcome == "noop_already_configured"
        # Bit-identical: no rewrite.
        assert config_path.read_text(encoding="utf-8") == before_text

    def test_persisted_shape_when_user_picks_full(self, tmp_path: Path) -> None:
        """Behavior 5: full choice persists with expansion_prompt='ask-intelligent'."""
        config_dir = tmp_path / ".nwave"

        with patch("nwave_ai.cli._prompt_density_choice", return_value="full"):
            handle_install_density_prompt(config_dir=config_dir, non_interactive=False)

        config = _read(config_dir / "global-config.json")
        # Per Decision 4 (2026-04-28), the fresh-install default
        # expansion_prompt is "ask-intelligent" (scoped trigger-based menu).
        assert config["documentation"] == {
            "density": "full",
            "expansion_prompt": "ask-intelligent",
        }
