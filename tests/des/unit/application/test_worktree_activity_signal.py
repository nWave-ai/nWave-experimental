"""Unit tests for `worktree_activity_signal` -- name normalization, declared-
ownership resolution, and HEAD/index activity age (lane/sentinel-tool).

`test_defect_3_*` is the third named defect: the scratchpad prototype's
declared-owner comparison prefixed the WRONG side (`"wt-" + "wt-charterarm"`
inside `.removeprefix`, matching nothing), so the axis silently reported
zero owners -- a fix that could not fire, inside the patch meant to end
exactly that class. The test proves a NAIVE re-implementation of that exact
bug fails on both directions this module must handle, then proves
`normalize_lane_name`/`resolve_declared_ownership` handle both correctly.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from des.application.worktree_activity_signal import (
    normalize_lane_name,
    qualified_name,
    read_activity_age_seconds,
    resolve_declared_ownership,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate


def _naive_buggy_match(wt_prefixed_row_name: str, declared: str) -> bool:
    """A faithful reconstruction of the prototype's actual bug: given a row
    name ALREADY reduced to its `wt-`-prefixed form (`path.name.replace(
    "nWave-dev-", "")`, e.g. `"wt-charterarm"`), the buggy comparator
    RE-PREFIXED it with `"wt-"` instead of stripping the prefix, producing
    `"wt-wt-charterarm"` -- which cannot equal any sane declared spelling.
    Kept here only to DEMONSTRATE the defect class the real fix below must
    not repeat."""
    return ("wt-" + wt_prefixed_row_name) == declared


@pytest.mark.parametrize("declared", ["charterarm", "wt-charterarm"])
def test_defect_3_naive_prefix_concatenation_fails_both_declared_spellings(
    declared: str,
) -> None:
    """Reproduces the exact failure shape: row name already `wt-`-prefixed
    (`"wt-charterarm"`), and the buggy comparator prefixes it AGAIN instead
    of stripping -- `"wt-wt-charterarm"` matches neither a bare nor a
    `wt-`-prefixed declared token, so the whole axis silently reports zero
    owners."""
    assert not _naive_buggy_match(
        wt_prefixed_row_name="wt-charterarm", declared=declared
    )


@pytest.mark.parametrize(
    "declared_token,worktree_basename",
    [
        pytest.param(
            "charterarm", "nWave-dev-wt-charterarm", id="bare_matches_full_prefixed"
        ),
        pytest.param("wt-charterarm", "charterarm", id="prefixed_matches_bare"),
        pytest.param("charterarm", "wt-charterarm", id="bare_matches_wt_prefixed"),
        pytest.param(
            "nWave-dev-wt-charterarm", "charterarm", id="full_prefixed_matches_bare"
        ),
        pytest.param("CHARTERARM", "wt-charterarm", id="case_insensitive"),
    ],
)
def test_defect_3_normalization_matches_wt_prefixed_and_bare_forms_both_ways(
    declared_token: str, worktree_basename: str
) -> None:
    assert normalize_lane_name(declared_token) == normalize_lane_name(worktree_basename)
    assert normalize_lane_name(declared_token) == "charterarm"


def test_declared_ownership_resolves_via_normalized_bare_name(tmp_path: Path) -> None:
    path = tmp_path / "Projects" / "nWave-dev-wt-charterarm"
    path.mkdir(parents=True)

    owned, how = resolve_declared_ownership(
        path=path, owned_tokens=frozenset({"wt-charterarm"}), marker_present=False
    )

    assert owned is True
    assert "charterarm" in how


def test_declared_ownership_resolves_via_qualified_name_for_a_collision(
    tmp_path: Path,
) -> None:
    """Two same-named worktrees under DIFFERENT parent directories --
    `~/Projects/nWave-dev-wt-sentinel` and `~/Projects/wt/sentinel-tool` --
    are the collision the prototype's bare-basename display could not
    distinguish. An `--owned "wt/sentinel-tool"` qualified token must match
    ONLY the intended one."""
    projects_wt = tmp_path / "Projects" / "wt" / "sentinel-tool"
    projects_wt.mkdir(parents=True)
    projects_bare = tmp_path / "Projects" / "nWave-dev-wt-sentinel"
    projects_bare.mkdir(parents=True)

    owned_intended, _ = resolve_declared_ownership(
        path=projects_wt,
        owned_tokens=frozenset({"wt/sentinel-tool"}),
        marker_present=False,
    )
    owned_other, _ = resolve_declared_ownership(
        path=projects_bare,
        owned_tokens=frozenset({"wt/sentinel-tool"}),
        marker_present=False,
    )

    assert owned_intended is True
    assert owned_other is False


def test_declared_ownership_absent_is_false_not_an_error(tmp_path: Path) -> None:
    path = tmp_path / "wt" / "unrelated-lane"
    path.mkdir(parents=True)

    owned, how = resolve_declared_ownership(
        path=path, owned_tokens=frozenset({"some-other-lane"}), marker_present=False
    )

    assert owned is False
    assert how == ""


def test_declared_ownership_marker_file_outranks_and_needs_no_owned_flag(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wt" / "marker-owned-lane"
    path.mkdir(parents=True)

    owned, how = resolve_declared_ownership(
        path=path, owned_tokens=frozenset(), marker_present=True
    )

    assert owned is True
    assert "marker" in how


def test_qualified_name_disambiguates_two_same_basename_parents(tmp_path: Path) -> None:
    a = tmp_path / "Projects" / "sentinel"
    b = tmp_path / "Projects" / "wt" / "sentinel"

    assert qualified_name(a) != qualified_name(b)
    assert qualified_name(a) == "Projects/sentinel"
    assert qualified_name(b) == "wt/sentinel"


def _write_gitdir(
    tmp_path: Path, *, head_age: float, index_age: float, now: float
) -> Path:
    worktree = tmp_path / "wt"
    gitdir = tmp_path / "gitdir-for-wt"
    gitdir.mkdir()
    (worktree).mkdir()
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    head = gitdir / "HEAD"
    index = gitdir / "index"
    head.write_text("ref: refs/heads/lane\n", encoding="utf-8")
    index.write_text("", encoding="utf-8")
    import os

    os.utime(head, (now - head_age, now - head_age))
    os.utime(index, (now - index_age, now - index_age))
    return worktree


def test_activity_age_is_decided_by_head_alone_index_is_excluded(
    tmp_path: Path,
) -> None:
    """Replaces `test_activity_age_is_the_younger_of_head_and_index`
    (D85-4, `docs/feature/fix-sentinel-activity-self-contamination/
    feature-delta.md`), which pinned the DEFECTIVE `min(HEAD, index)`
    contract this repair removes. `.git/index` is written by `git status
    --porcelain` -- which the Sentinel's own dirty-state axis runs on every
    sweep -- so a young `index` reading is evidence about the INSTRUMENT,
    never about the worktree. The repaired axis reads `HEAD` alone: a young
    `index` next to an old `HEAD` must NOT pull the reported age down."""
    now = time.time()
    worktree = _write_gitdir(tmp_path, head_age=300, index_age=10, now=now)

    age = read_activity_age_seconds(worktree, now=now)

    assert isinstance(age, int)
    assert 299 <= age <= 301, (
        f"expected ~300s (HEAD's own age), got {age}s -- the axis is still "
        "letting the younger `index` reading (10s) win"
    )


def test_activity_age_is_indeterminate_when_gitdir_is_absent(tmp_path: Path) -> None:
    worktree = tmp_path / "not-a-worktree"
    worktree.mkdir()

    age = read_activity_age_seconds(worktree)

    assert isinstance(age, Indeterminate)


def test_activity_age_resolves_a_linked_worktrees_gitdir_file(tmp_path: Path) -> None:
    """The common case this axis exists for: a LINKED worktree's `.git` is a
    FILE pointing at the real gitdir under the main checkout, not a
    directory of its own."""
    now = time.time()
    worktree = _write_gitdir(tmp_path, head_age=5, index_age=5, now=now)

    age = read_activity_age_seconds(worktree, now=now)

    assert isinstance(age, int)
    assert age <= 6
