"""The mirror must refresh a stale cache, not strand the next run on it.

The stranding case is the one this file exists for: a persistent cache plus a
moved pin is the state a reviewer found before it could be built, and it would
have put a human back in the loop with a manual delete -- the exact step the
mirror removes.
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import pytest


_K4 = Path(__file__).resolve().parents[3] / "scripts" / "analysis" / "k4"
sys.path.insert(0, str(_K4))

import sut_mirror


def _repo(path: Path, *, commits: int = 1) -> str:
    """A tiny real repository, returning the revision of its last commit."""
    path.mkdir(parents=True, exist_ok=True)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t.invalid",
        "PATH": "/usr/bin:/bin",
        "HOME": str(path.parent),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    subprocess.run(
        ["git", "init", "-q", "-b", "main", "."], cwd=path, check=True, env=env
    )
    head = ""
    for index in range(commits):
        (path / "f.txt").write_text(f"{index}-{uuid.uuid4()}")
        subprocess.run(["git", "add", "-A"], cwd=path, check=True, env=env)
        subprocess.run(
            ["git", "commit", "-qm", f"c{index}"], cwd=path, check=True, env=env
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    return head


def test_a_declined_mirror_is_a_stated_choice(monkeypatch) -> None:
    outcome = sut_mirror.resolve_subject_source(None)
    assert not outcome.is_mirror
    assert "declined" in outcome.detail
    assert outcome.source == sut_mirror.k4_subject.SUT_URL


def test_an_absent_cache_is_cloned(tmp_path, monkeypatch) -> None:
    origin = tmp_path / "origin"
    pin = _repo(origin)
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_URL", str(origin))
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_PINNED_REV", pin)

    outcome = sut_mirror.resolve_subject_source(tmp_path / "mirror.git")
    assert outcome.is_mirror
    assert "cloned" in outcome.detail


def test_a_cache_carrying_the_pin_is_reused_without_fetching(
    tmp_path, monkeypatch
) -> None:
    origin = tmp_path / "origin"
    pin = _repo(origin)
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_URL", str(origin))
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_PINNED_REV", pin)
    cache = tmp_path / "mirror.git"
    sut_mirror.ensure_mirror(cache)

    outcome = sut_mirror.ensure_mirror(cache)
    assert "reused" in outcome.detail


def test_a_moved_pin_refreshes_the_cache_instead_of_stranding_it(
    tmp_path, monkeypatch
) -> None:
    """The review finding: a bumped pin must not require a manual delete."""
    origin = tmp_path / "origin"
    first = _repo(origin)
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_URL", str(origin))
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_PINNED_REV", first)
    cache = tmp_path / "mirror.git"
    sut_mirror.ensure_mirror(cache)

    # The subject moves on, and the pin is bumped to the new revision -- the
    # documented, deliberate case. The cache is now behind.
    moved = _repo(origin, commits=2)
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_PINNED_REV", moved)

    outcome = sut_mirror.ensure_mirror(cache)
    assert outcome.is_mirror
    assert "fetched" in outcome.detail


def test_a_pin_no_fetch_can_reach_refuses_loudly(tmp_path, monkeypatch) -> None:
    origin = tmp_path / "origin"
    _repo(origin)
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_URL", str(origin))
    monkeypatch.setattr(sut_mirror.k4_subject, "SUT_PINNED_REV", "0" * 40)
    cache = tmp_path / "mirror.git"

    with pytest.raises(sut_mirror.MirrorUnavailable) as refused:
        sut_mirror.ensure_mirror(cache)
    message = str(refused.value)
    assert "WHAT:" in message and "WHY:" in message and "HOW:" in message
