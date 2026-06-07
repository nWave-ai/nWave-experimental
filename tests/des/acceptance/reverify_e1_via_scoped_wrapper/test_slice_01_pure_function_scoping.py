"""slice-01 AT-(a): the SSOT pure-function correctly feature-scopes E1.

Layer 2 (in-process, real temp-git filesystem, pure-function SUT). Per
Mandate 9 the input mode is PBT full -- ``missing_at_files(feature_id=...)``
takes a small int parameter (n_features sharing @slice-NN), and the
universal invariant the wrapper depends on is:

  forall n in [1..N], forall primary_id, forall slice_id:
    missing_at_files(repo_with_n_features, commit, slice_id, feature_id=primary)
    == []
    AND
    no .feature file from feature[k] for k != 0 appears in any
    intermediate output of feature_files_for_slice(repo, slice_id, primary)

i.e. the feature-scoped call returns ONLY the primary's slice files; a
collider's identically-tagged file is NEVER walked into the verdict.

Pinned example (Mandate 9, Pillar 1 readability): the n=2 case is the
minimal cross-feature-collision -- the row R4 the existing reverify ATs
miss; the n=1 case is the regression-guard equivalent of row R3.

RED scaffold: ``des.application.slice_at_completeness.missing_at_files``
raises AssertionError -- Hypothesis surfaces it on the first example,
shrinks to n_features=1, fails for the right reason. DELIVER's A_GREEN_ATS
relocates the genuine logic + the property goes green.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from des.application.slice_at_completeness import missing_at_files


pytestmark = pytest.mark.acceptance


_FEATURE_ID_PRIMARY = "fix-reverify-e1-via-scoped-wrapper"
_FEATURE_ID_COLLIDER_PREFIX = "fix-other-feature-sharing-slice-01"
_SLICE_ID = "slice-01"

_TEMP_PYTEST_INI = "[pytest]\nmarkers =\n    acceptance: Acceptance tests\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


def _feature_body(feature_id: str, slice_id: str = _SLICE_ID) -> str:
    return (
        f"@feature-{feature_id} @{slice_id}\n"
        f"Feature: {feature_id} -- {slice_id}\n\n"
        "  Scenario: ships its AT\n"
        "    Given a committed slice\n"
        "    When the gate runs\n"
        "    Then the slice is certified green\n"
    )


def _build_repo_with_n_features(repo: Path, n_features: int) -> str:
    """Seed ``repo`` with ``n_features`` features sharing @slice-01; return commit SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "pytest.ini").write_text(_TEMP_PYTEST_INI)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: base")

    # Seed primary + (n-1) colliders.
    feature_ids = [_FEATURE_ID_PRIMARY] + [
        f"{_FEATURE_ID_COLLIDER_PREFIX}-{i}" for i in range(1, n_features)
    ]
    for fid in feature_ids:
        rel = Path(f"tests/{fid}/acceptance/{_SLICE_ID}.feature")
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_feature_body(fid))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"feat: {_SLICE_ID}\n\nSlice-Id: {_SLICE_ID}\n")
    return _git(repo, "rev-parse", "HEAD").strip()


@given(n_features=st.integers(min_value=1, max_value=5))
@example(n_features=1)  # R3: single-feature, feature-scoped.
@example(n_features=2)  # R4: minimal cross-feature-collision -- THE MISSED ROW.
@example(n_features=5)
@settings(max_examples=20, deadline=None)
def test_feature_scoped_missing_at_files_returns_empty_for_primary(
    tmp_path_factory, n_features: int
) -> None:
    """For any n >= 1, scoping to the primary feature returns no missing files.

    Universal invariant: ``missing_at_files(..., feature_id=primary)`` walks
    ONLY the primary's @feature-{id}-tagged .feature; a collider's identically-
    @slice-NN-tagged file MUST NOT enter the verdict. A non-empty return for
    n >= 2 is the W5 defect -- this property catches re-instantiation.
    """
    repo = tmp_path_factory.mktemp("repo")
    commit = _build_repo_with_n_features(repo, n_features)
    missing = missing_at_files(repo, commit, _SLICE_ID, feature_id=_FEATURE_ID_PRIMARY)
    assert missing == [], (
        f"feature-scoped E1 leaked collider files into verdict for n={n_features}: "
        f"{missing!r}"
    )
