"""Unit tests for the scaffold command (US-01).

Test budget: 4 behaviors x 2 = 8 max unit tests.
Behaviors:
  B1 — scaffold creates 3 wave sections (DISCUSS, DESIGN, DISTILL)
  B2 — scaffold output passes E1+E2 validator (exits 0)
  B3 — missing future-wave sections don't fail (incremental authoring)
  B4 — --feature <name> creates file at correct path

Driving port: init_scaffold_command(feature_name, output_dir) -> int
Port-to-port: enters through CLI command, asserts via return code + filesystem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from nwave_ai.feature_delta.cli import init_scaffold_command


if TYPE_CHECKING:
    from pathlib import Path


class TestScaffoldCreatesWaveSections:
    """B1 — scaffold creates 3 wave sections: DISCUSS, DESIGN, DISTILL."""

    def test_scaffold_creates_discuss_design_distill_sections(
        self, tmp_path: Path
    ) -> None:
        exit_code = init_scaffold_command("my-feature", output_dir=tmp_path)
        assert exit_code == 0
        content = (
            tmp_path / "docs" / "feature" / "my-feature" / "feature-delta.md"
        ).read_text()
        assert "## Wave: DISCUSS" in content
        assert "## Wave: DESIGN" in content
        assert "## Wave: DISTILL" in content

    def test_scaffold_includes_inherited_commitments_tables(
        self, tmp_path: Path
    ) -> None:
        init_scaffold_command("another-feature", output_dir=tmp_path)
        content = (
            tmp_path / "docs" / "feature" / "another-feature" / "feature-delta.md"
        ).read_text()
        # Each wave section must have a [REF] Inherited commitments table.
        assert content.count("### [REF] Inherited commitments") == 3


class TestScaffoldPassesValidator:
    """B2 — scaffold output passes E1+E2 validator (exits 0 on warn-only)."""

    def test_scaffold_passes_e1_rule(self, tmp_path: Path) -> None:
        from nwave_ai.feature_delta.domain.rules import e1_section_present

        init_scaffold_command("e1-feature", output_dir=tmp_path)
        path = tmp_path / "docs" / "feature" / "e1-feature" / "feature-delta.md"
        content = path.read_text()
        violations = e1_section_present.check(content, str(path))
        assert violations == ()

    def test_scaffold_passes_e2_rule(self, tmp_path: Path) -> None:
        from nwave_ai.feature_delta.domain.rules import e2_columns_present

        init_scaffold_command("e2-feature", output_dir=tmp_path)
        path = tmp_path / "docs" / "feature" / "e2-feature" / "feature-delta.md"
        content = path.read_text()
        violations = e2_columns_present.check(content, str(path))
        assert violations == ()


class TestScaffoldIncrementalAuthoring:
    """B3 — missing future-wave sections don't fail (incremental authoring OK)."""

    def test_scaffold_with_only_discuss_section_passes_e1(self, tmp_path: Path) -> None:
        """A file with just one wave section should still pass E1."""
        from nwave_ai.feature_delta.domain.rules import e1_section_present

        partial = tmp_path / "partial-feature-delta.md"
        partial.write_text(
            "# partial\n\n"
            "## Wave: DISCUSS\n\n"
            "### [REF] Inherited commitments\n\n"
            "| Origin | Commitment | DDD | Impact |\n"
            "|--------|------------|-----|--------|\n"
            "| n/a | initial commitment | n/a | establishes surface |\n",
            encoding="utf-8",
        )
        violations = e1_section_present.check(partial.read_text(), str(partial))
        assert violations == ()


class TestScaffoldOutputPath:
    """B4 — --feature <name> creates file at correct path."""

    def test_scaffold_creates_file_at_expected_path(self, tmp_path: Path) -> None:
        exit_code = init_scaffold_command("my-epic-feature", output_dir=tmp_path)
        assert exit_code == 0
        expected = (
            tmp_path / "docs" / "feature" / "my-epic-feature" / "feature-delta.md"
        )
        assert expected.exists()

    @pytest.mark.parametrize(
        "feature_name",
        ["simple", "hyphen-name", "feature-with-numbers-123"],
    )
    def test_scaffold_handles_various_feature_names(
        self, feature_name: str, tmp_path: Path
    ) -> None:
        exit_code = init_scaffold_command(feature_name, output_dir=tmp_path)
        assert exit_code == 0
        assert (
            tmp_path / "docs" / "feature" / feature_name / "feature-delta.md"
        ).exists()
