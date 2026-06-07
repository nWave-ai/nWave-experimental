"""Unit tests for `scripts/validation/validate_feature_layout.py` (R2).

Per Recommendation 2 (lean-wave doc audit, 2026-04-28). The validator
enforces ONE narrative file (`feature-delta.md`) per feature, allows
machine companions (`.json`/`.yaml`/`.yml`/`.feature`), allows specific
subdirectories (`steps/`, `slices/`, `spike/`, `bugfix/`), and rejects
loose markdown — especially under legacy wave-grouping subdirs.

Lean test budget: behavior-first. One test per non-overlapping behavior.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Module-under-test loader — keeps tests independent of repo `sys.path`.
# ---------------------------------------------------------------------------


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    target = repo_root / "scripts" / "validation" / "validate_feature_layout.py"
    spec = importlib.util.spec_from_file_location("validate_feature_layout", target)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vfl():
    return _load_module()


# ---------------------------------------------------------------------------
# Pure-core tests
# ---------------------------------------------------------------------------


def test_lean_layout_passes(vfl) -> None:
    """A feature with only `feature-delta.md` + machine artifacts passes."""
    feature_paths = [
        (
            "lean-feature",
            [
                "feature-delta.md",
                "environments.yaml",
                "roadmap.json",
            ],
        )
    ]
    result = vfl.validate_feature_layout(feature_paths)
    assert result.is_valid is True
    assert result.offenders == []
    assert result.feature_count == 1


def test_legacy_wave_subdirs_flagged_with_canonical_alternative(vfl) -> None:
    """Loose `.md` under legacy wave dirs flags with merge-into-delta hint."""
    feature_paths = [
        (
            "legacy-feature",
            [
                "feature-delta.md",
                "discuss/user-stories.md",
                "design/architecture-design.md",
                "deliver/retrospective.md",
            ],
        )
    ]
    result = vfl.validate_feature_layout(feature_paths)
    assert result.is_valid is False
    assert len(result.offenders) == 3
    waves_flagged = {o.path.split("/")[1] for o in result.offenders}
    assert waves_flagged == {"discuss", "design", "deliver"}
    # Each offender's canonical alternative names the corresponding wave.
    discuss_off = next(o for o in result.offenders if "discuss" in o.path)
    assert "## Wave: DISCUSS" in discuss_off.canonical_alternative


def test_loose_top_level_markdown_flagged(vfl) -> None:
    """A loose `.md` at feature root other than feature-delta.md is rejected."""
    feature_paths = [
        ("loose-md", ["feature-delta.md", "wave-decisions.md", "outcome-kpis.md"])
    ]
    result = vfl.validate_feature_layout(feature_paths)
    assert result.is_valid is False
    paths_flagged = {o.path for o in result.offenders}
    assert "loose-md/wave-decisions.md" in paths_flagged
    assert "loose-md/outcome-kpis.md" in paths_flagged
    # The narrative file itself must NOT be flagged.
    assert "loose-md/feature-delta.md" not in paths_flagged


def test_allowed_subdirs_pass_through(vfl) -> None:
    """Files under steps/, slices/, spike/, bugfix/ are exempt."""
    feature_paths = [
        (
            "exempt-subdirs",
            [
                "feature-delta.md",
                "steps/conftest.py",
                "steps/install_steps.py",
                "slices/slice-01-foo.md",
                "spike/findings.md",
                "bugfix/rca.md",
            ],
        )
    ]
    result = vfl.validate_feature_layout(feature_paths)
    assert result.is_valid is True
    assert result.offenders == []


def test_machine_artifacts_at_any_depth_allowed(vfl) -> None:
    """`.feature`, `.yaml`, `.yml`, `.json` files pass at any depth."""
    feature_paths = [
        (
            "machine-only",
            [
                "feature-delta.md",
                "tests/acceptance/walking-skeleton.feature",
                "kpi-overrides.yaml",
                "deliver/roadmap.json",
            ],
        )
    ]
    result = vfl.validate_feature_layout(feature_paths)
    # The `deliver/roadmap.json` is allowed because `.json` is a machine
    # artifact even under a legacy wave dir name.
    assert result.is_valid is True


# ---------------------------------------------------------------------------
# CLI shell tests
# ---------------------------------------------------------------------------


def test_main_exits_zero_on_clean_tree(vfl, tmp_path: Path) -> None:
    """End-to-end: a tmp tree with one lean feature returns exit code 0."""
    root = tmp_path / "feature"
    feat = root / "alpha"
    feat.mkdir(parents=True)
    (feat / "feature-delta.md").write_text("# alpha\n", encoding="utf-8")
    (feat / "environments.yaml").write_text(
        "target_environments: []\n", encoding="utf-8"
    )
    rc = vfl.main([str(root)])
    assert rc == 0


def test_main_exits_one_on_offenders(vfl, tmp_path: Path) -> None:
    """End-to-end: a tmp tree with legacy outputs returns exit code 1."""
    root = tmp_path / "feature"
    feat = root / "beta"
    (feat / "discuss").mkdir(parents=True)
    (feat / "feature-delta.md").write_text("# beta\n", encoding="utf-8")
    (feat / "discuss" / "user-stories.md").write_text("legacy\n", encoding="utf-8")
    rc = vfl.main([str(root)])
    assert rc == 1


def test_main_usage_error_returns_two(vfl) -> None:
    """Wrong argument count returns exit code 2."""
    rc = vfl.main([])
    assert rc == 2


def test_soft_flag_returns_zero_despite_offenders(vfl, tmp_path: Path) -> None:
    """`--soft` mode exits 0 even when offenders are found.

    Used during the pre-commit rollout window so existing legacy features
    do not block local commits. Strict mode (no `--soft`) is the long-term
    contract.
    """
    root = tmp_path / "feature"
    feat = root / "gamma"
    (feat / "discuss").mkdir(parents=True)
    (feat / "feature-delta.md").write_text("# gamma\n", encoding="utf-8")
    (feat / "discuss" / "user-stories.md").write_text("legacy\n", encoding="utf-8")
    rc = vfl.main(["--soft", str(root)])
    assert rc == 0
