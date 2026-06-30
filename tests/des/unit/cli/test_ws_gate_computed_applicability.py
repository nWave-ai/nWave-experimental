"""Regression: feature-end WS gate COMPUTES applicability from the declarative delta.

Sister-corroborated friction (nwave-sf, tsunami, 2026-06-23); RCA via /nw-bugfix
Phase-1 (nw-troubleshooter). A feature with NO `walking_skeleton_applicable` flag
AND an EMPTY `entry_points` list (no @walking-skeleton AT) must have its
applicability COMPUTED in `_feature_under_gate` from the git delta -- a non-installer
delta -> NOT_APPLICABLE (walking_skeleton_applicable=False, ships=False), NOT the
spurious build-failure FAIL it hit before (it fell through to _build_and_install on a
feature with no installable artifact).

INVARIANT PRESERVED (no false-DONE): a delta that ADDS an installable root ->
ships_installer_artifact=True -> the domain evaluate() FAILs (a no-AT installer
feature cannot dodge). git Indeterminate -> delta_indeterminate carried ->
INDETERMINATE (degrade-LOUD, AD-21). A feature WITH a @walking-skeleton AT
(non-empty entry_points) is UNCHANGED.
"""

from __future__ import annotations

from des.cli.walking_skeleton_gate import _feature_under_gate
from des.ports.driven_ports.feature_delta_port import (
    AddedPaths,
    FeatureDeltaPort,
    Indeterminate,
)


class _FakeDeltaPort(FeatureDeltaPort):
    """A fake delta port returning a pre-configured added-paths result."""

    def __init__(self, result: AddedPaths | Indeterminate) -> None:
        self._result = result

    def added_paths(self, repo, base_ref):
        return self._result


def _manifest(tmp_path, entry_points):
    return {"feature_root": str(tmp_path), "entry_points": entry_points}


def test_non_installer_no_at_computes_not_applicable(tmp_path):
    """No flag + empty entry_points + delta adds no installable -> NOT_APPLICABLE-bound VO."""
    fug = _feature_under_gate(
        _manifest(tmp_path, []),
        tmp_path,
        _FakeDeltaPort(AddedPaths(())),
        tmp_path,
        "master",
    )
    assert fug.walking_skeleton_applicable is False
    assert fug.ships_installer_artifact is False
    assert fug.delta_indeterminate is None


def test_delta_adds_installer_preserves_fail_invariant(tmp_path):
    """No flag + empty entry_points + delta ADDS an installable -> ships=True (domain FAILs)."""
    fug = _feature_under_gate(
        _manifest(tmp_path, []),
        tmp_path,
        _FakeDeltaPort(AddedPaths(("pkg/pyproject.toml",))),
        tmp_path,
        "master",
    )
    assert fug.walking_skeleton_applicable is False
    assert fug.ships_installer_artifact is True
    assert "pkg/pyproject.toml" in fug.added_installable_paths


def test_git_indeterminate_degrades_loud(tmp_path):
    """No flag + empty entry_points + git Indeterminate -> carried -> INDETERMINATE."""
    fug = _feature_under_gate(
        _manifest(tmp_path, []),
        tmp_path,
        _FakeDeltaPort(Indeterminate("git absent")),
        tmp_path,
        "master",
    )
    assert fug.delta_indeterminate == "git absent"


def test_at_present_path_unchanged(tmp_path):
    """A feature WITH a @walking-skeleton AT (non-empty entry_points) is UNCHANGED."""
    fug = _feature_under_gate(
        _manifest(tmp_path, ["mod/cli.py"]),
        tmp_path,
        _FakeDeltaPort(AddedPaths(())),
        tmp_path,
        "master",
    )
    assert fug.entry_points == ("mod/cli.py",)
    assert fug.walking_skeleton_applicable is None
