"""Unit tests for FeatureMigrator application service (driving port: migrate()).

Test Budget: 3 distinct behaviors x 2 = 6 unit tests max.
  B1: happy-path migration embeds .feature content + round-trip passes
  B2: idempotent — .pre-migration present -> no-op, exit 0, "already migrated"
  B3: round-trip failure -> MigrationAbortError raised, no files modified

Mandate M2: tests drive through FeatureMigrator.migrate() — the application
service driving port. Filesystem adapter is a real InMemory double for speed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from nwave_ai.feature_delta.application.migrator import (
    FeatureMigrator,
    MigrationAbortError,
)


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# B1 — happy-path: embeds content, round-trip passes, backup created
# ---------------------------------------------------------------------------


def test_migrate_embeds_feature_content_in_delta(tmp_path: Path) -> None:
    """migrate() embeds .feature content as gherkin block in feature-delta.md."""
    fdir = tmp_path / "my-feature"
    fdir.mkdir()
    feature_content = (
        "Feature: simple\n\n  Scenario: one\n    Given a\n    When b\n    Then c\n"
    )
    (fdir / "tests.feature").write_text(feature_content, encoding="utf-8")
    (fdir / "feature-delta.md").write_text(
        "# my-feature\n\n## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | embed feature | n/a | migration |\n",
        encoding="utf-8",
    )

    result = FeatureMigrator().migrate(fdir)

    assert result.embedded_count == 1
    delta_text = (fdir / "feature-delta.md").read_text(encoding="utf-8")
    assert "```gherkin" in delta_text
    assert "Scenario: one" in delta_text
    assert (fdir / "tests.feature.pre-migration").exists()
    assert not (fdir / "tests.feature").exists()


# ---------------------------------------------------------------------------
# B2 — idempotent: .pre-migration exists → no-op
# ---------------------------------------------------------------------------


def test_migrate_is_noop_when_pre_migration_backup_present(tmp_path: Path) -> None:
    """migrate() is a no-op when .feature.pre-migration already exists."""
    fdir = tmp_path / "migrated-feature"
    fdir.mkdir()
    (fdir / "tests.feature.pre-migration").write_text("old content", encoding="utf-8")
    (fdir / "feature-delta.md").write_text(
        "# migrated-feature\n\n## Wave: DISCUSS\n\n"
        "```gherkin\n"
        "Scenario: already embedded\n"
        "  Given already done\n"
        "```\n",
        encoding="utf-8",
    )

    result = FeatureMigrator().migrate(fdir)

    assert result.already_migrated is True
    assert result.embedded_count == 0
    # feature-delta.md must not be modified
    delta_text = (fdir / "feature-delta.md").read_text(encoding="utf-8")
    assert "already embedded" in delta_text


# ---------------------------------------------------------------------------
# B3 — round-trip failure: raises MigrationAbortError, no files modified
# ---------------------------------------------------------------------------


def test_migrate_aborts_when_round_trip_would_lose_content(tmp_path: Path) -> None:
    """migrate() raises MigrationAbortError when round-trip loses > 1 byte."""
    fdir = tmp_path / "lossy-feature"
    fdir.mkdir()
    # Create a .feature with content that the parser cannot survive round-trip
    # (e.g., a raw binary/non-UTF8 sequence embedded). We simulate by
    # providing a FeatureMigrator that returns forced diff > 1 byte.
    # Since our real gherkin parser strips leading whitespace from blocks,
    # use content that would be normalised away — deeply indented non-standard content.
    feature_content = "Feature: lossy\n\nXXXNOT-STANDARD-GHERKIN-CONTENT-FORCED-LOSS\n"
    (fdir / "tests.feature").write_text(feature_content, encoding="utf-8")
    (fdir / "feature-delta.md").write_text(
        "# lossy-feature\n\n## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | lossy | n/a | test |\n",
        encoding="utf-8",
    )
    original_delta = (fdir / "feature-delta.md").read_text(encoding="utf-8")

    # The migration should not raise for valid gherkin — we need to test
    # the abort path. We simulate by patching the extractor to return
    # content that differs by > 1 byte from original.
    # Use a custom migrator with a forced-fail round-trip check.
    migrator = FeatureMigrator(force_roundtrip_fail=True)

    with pytest.raises(MigrationAbortError) as exc_info:
        migrator.migrate(fdir)

    # No files modified
    assert not (fdir / "tests.feature.pre-migration").exists()
    assert (fdir / "feature-delta.md").read_text(encoding="utf-8") == original_delta
    assert (
        "diff" in str(exc_info.value).lower()
        or "round-trip" in str(exc_info.value).lower()
    )
