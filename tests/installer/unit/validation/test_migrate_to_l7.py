"""Unit tests for `scripts.migrate_to_l7` (DDD-3 implementation).

Covers the pure-function core (`compute_migration_plan`, `classify`,
`render_feature_delta`) and the thin IO shell (`migrate_feature`).
Strategy: pure-function tests for the planner; tmp_path real-IO for the
shell. No mocks.

Per DDD-3:
- Idempotent on re-run when the lean format marker is present
- Atomic write via tmp + os.replace
- Recovery cleans orphan .tmp files from prior crashed runs
- Heuristic classification table is deterministic
- Ambiguous content lands under `<!-- review-needed -->` marker
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from pathlib import Path

from scripts.migrate_to_l7 import (
    LEAN_FORMAT_MARKER,
    REVIEW_NEEDED_MARKER,
    classify,
    compute_migration_plan,
    main,
    migrate_feature,
    render_feature_delta,
)


# ---------------------------------------------------------------------------
# Pure-function: classify()
# ---------------------------------------------------------------------------


class TestClassify:
    """Heuristic classification table coverage (DDD-3 stable contract)."""

    @pytest.mark.parametrize(
        ("relative_path", "expected_wave", "expected_tier"),
        [
            ("discuss/user-stories.md", "DISCUSS", "REF"),
            ("discuss/elevator-pitch.md", "DISCUSS", "REF"),
            ("discuss/jtbd-analysis.md", "DISCUSS", "WHY"),
            ("discuss/persona.md", "DISCUSS", "WHY"),
            ("discuss/alternatives.md", "DISCUSS", "WHY"),
            ("design/adr-001-foo.md", "DESIGN", "REF"),
            ("design/architecture.md", "DESIGN", "REF"),
            ("distill/scenarios.feature", "DISTILL", "REF"),
            ("deliver/retro.md", "DELIVER", "WHY"),
            ("deliver/retrospective.md", "DELIVER", "WHY"),
        ],
    )
    def test_classifies_known_paths(
        self,
        relative_path: str,
        expected_wave: str,
        expected_tier: str,
    ) -> None:
        rule = classify(relative_path)
        assert rule is not None, f"Expected {relative_path!r} to match a heuristic rule"
        assert rule.wave == expected_wave
        assert rule.tier == expected_tier

    @pytest.mark.parametrize(
        "relative_path",
        [
            "discuss/freeform-notes.md",  # no rule
            "design/random-thoughts.md",  # no rule
            "discover/interview-001.md",  # SKIPPED_SUBDIRS
            "feature-delta.md",  # not under any subdir
            "wave-decisions.md",  # ambiguous (no subdir)
        ],
    )
    def test_returns_none_for_unmatched(self, relative_path: str) -> None:
        assert classify(relative_path) is None


# ---------------------------------------------------------------------------
# Pure-function: compute_migration_plan()
# ---------------------------------------------------------------------------


class TestComputeMigrationPlan:
    """Planner is deterministic + handles already-migrated short-circuit."""

    def test_empty_input_produces_empty_plan(self) -> None:
        plan = compute_migration_plan({})
        assert plan.sections == []
        assert plan.ambiguous == []
        assert plan.skipped == []
        assert plan.already_migrated is False

    def test_already_migrated_short_circuits(self) -> None:
        plan = compute_migration_plan(
            {"discuss/user-stories.md": "ignored content"},
            already_migrated=True,
        )
        assert plan.already_migrated is True
        assert plan.sections == []
        assert plan.ambiguous == []

    def test_classified_sections_ordered_by_wave(self) -> None:
        legacy = {
            "deliver/retro.md": "Retro body",
            "discuss/user-stories.md": "Stories body",
            "design/architecture.md": "Arch body",
        }
        plan = compute_migration_plan(legacy)
        # Canonical order: DISCUSS -> DESIGN -> DELIVER
        actual_waves = [s.wave for s in plan.sections]
        assert actual_waves == ["DISCUSS", "DESIGN", "DELIVER"]

    def test_ambiguous_paths_collected_separately(self) -> None:
        legacy = {
            "discuss/user-stories.md": "Stories body",
            "discuss/random-stuff.md": "Free-form notes",
            "design/notes.md": "More notes",
        }
        plan = compute_migration_plan(legacy)
        assert "discuss/random-stuff.md" in plan.ambiguous
        assert "design/notes.md" in plan.ambiguous
        assert len(plan.sections) == 1
        assert plan.sections[0].section_name == "User stories"

    def test_skipped_subdir_listed_separately(self) -> None:
        legacy = {
            "discover/interview-001.md": "verbatim transcript",
            "discuss/user-stories.md": "Stories body",
        }
        plan = compute_migration_plan(legacy)
        assert "discover/interview-001.md" in plan.skipped
        assert len(plan.sections) == 1


# ---------------------------------------------------------------------------
# Pure-function: render_feature_delta()
# ---------------------------------------------------------------------------


class TestRenderFeatureDelta:
    """Renderer emits the lean marker, schema-typed headings, and markers."""

    def test_first_line_is_lean_marker(self) -> None:
        plan = compute_migration_plan({"discuss/user-stories.md": "Stories"})
        rendered = render_feature_delta(plan, "feat-x")
        assert rendered.splitlines()[0] == LEAN_FORMAT_MARKER

    def test_each_section_has_schema_typed_heading(self) -> None:
        plan = compute_migration_plan(
            {
                "discuss/user-stories.md": "Stories",
                "design/architecture.md": "Arch",
            }
        )
        rendered = render_feature_delta(plan, "feat-x")
        assert "## Wave: DISCUSS / [REF] User stories" in rendered
        assert "## Wave: DESIGN / [REF] Architecture" in rendered

    def test_review_needed_marker_present_when_ambiguous(self) -> None:
        plan = compute_migration_plan({"discuss/random-stuff.md": "free-form"})
        rendered = render_feature_delta(plan, "feat-x")
        assert REVIEW_NEEDED_MARKER in rendered
        assert "## Wave: DISCUSS / [WHY] Migration residue" in rendered


# ---------------------------------------------------------------------------
# IO shell: migrate_feature() against tmp_path
# ---------------------------------------------------------------------------


class TestMigrateFeatureRealIO:
    """Real filesystem under tmp_path. No mocks."""

    def _seed_legacy_feature(self, root: Path, feature_id: str) -> Path:
        """Create a minimal legacy feature directory under ``root``."""
        feature_dir = root / "docs" / "feature" / feature_id
        (feature_dir / "discuss").mkdir(parents=True)
        (feature_dir / "design").mkdir(parents=True)
        (feature_dir / "discuss" / "user-stories.md").write_text(
            "# User Stories\n\nUS-1 story body.\n", encoding="utf-8"
        )
        (feature_dir / "design" / "architecture.md").write_text(
            "# Architecture\n\nHexagonal monolith.\n", encoding="utf-8"
        )
        return feature_dir

    def test_first_run_migrates_and_writes_lean_marker(self, tmp_path: Path) -> None:
        feature_dir = self._seed_legacy_feature(tmp_path, "feat-alpha")
        rc = migrate_feature(feature_dir)
        assert rc == 0
        target = feature_dir / "feature-delta.md"
        assert target.is_file()
        first_line = target.read_text(encoding="utf-8").splitlines()[0]
        assert first_line == LEAN_FORMAT_MARKER

    def test_idempotent_when_lean_marker_present(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        feature_dir = self._seed_legacy_feature(tmp_path, "feat-beta")
        # First run produces the lean marker.
        migrate_feature(feature_dir)
        target = feature_dir / "feature-delta.md"
        before = target.read_bytes()

        # Second run must NOT modify the target.
        capsys.readouterr()  # drain any prior output
        rc = migrate_feature(feature_dir)
        assert rc == 0
        captured = capsys.readouterr()
        assert "already migrated: feat-beta" in captured.out
        after = target.read_bytes()
        assert before == after, "Idempotent run rewrote feature-delta.md"

    def test_atomic_write_no_orphan_tmp_remains(self, tmp_path: Path) -> None:
        feature_dir = self._seed_legacy_feature(tmp_path, "feat-gamma")
        migrate_feature(feature_dir)
        tmp_path_file = feature_dir / "feature-delta.md.tmp"
        assert not tmp_path_file.exists(), (
            "Atomic write left an orphan .tmp file behind"
        )

    def test_recovers_from_orphan_tmp_left_by_prior_crash(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Simulate a crashed prior run: stale .tmp present, no target."""
        feature_dir = self._seed_legacy_feature(tmp_path, "feat-delta")
        target = feature_dir / "feature-delta.md"
        orphan = feature_dir / "feature-delta.md.tmp"
        orphan.write_text("partial-write garbage", encoding="utf-8")

        capsys.readouterr()
        rc = migrate_feature(feature_dir)
        captured = capsys.readouterr()

        assert rc == 0
        assert not orphan.exists(), "Orphan .tmp should have been removed"
        assert target.is_file()
        assert "cleaned up orphan .tmp" in captured.out

    def test_ambiguous_content_creates_review_marker_in_output(
        self, tmp_path: Path
    ) -> None:
        feature_dir = tmp_path / "docs" / "feature" / "feat-residue"
        (feature_dir / "discuss").mkdir(parents=True)
        # File whose stem matches no rule -> ambiguous
        (feature_dir / "discuss" / "random-stuff.md").write_text(
            "free-form notes", encoding="utf-8"
        )
        rc = migrate_feature(feature_dir)
        assert rc == 0
        target = feature_dir / "feature-delta.md"
        body = target.read_text(encoding="utf-8")
        assert REVIEW_NEEDED_MARKER in body
        assert "discuss/random-stuff.md" in body

    def test_returns_nonzero_on_missing_directory(self, tmp_path: Path) -> None:
        rc = migrate_feature(tmp_path / "does" / "not" / "exist")
        assert rc != 0


# ---------------------------------------------------------------------------
# CLI shell: main() against tmp_path
# ---------------------------------------------------------------------------


class TestCLIMain:
    """Argparse smoke + multi-feature dispatch."""

    def test_main_migrates_supplied_feature_dir(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "docs" / "feature" / "feat-cli"
        (feature_dir / "discuss").mkdir(parents=True)
        (feature_dir / "discuss" / "user-stories.md").write_text(
            "Stories", encoding="utf-8"
        )
        rc = main([str(feature_dir)])
        assert rc == 0
        assert (feature_dir / "feature-delta.md").is_file()
