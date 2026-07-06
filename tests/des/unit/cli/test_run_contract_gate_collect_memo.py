"""`_collect_scope` memoization (velocity-v2 <5min goal G-143).

Under ``NWAVE_COLLECT_MEMO`` the collect of the REAL (non-temp) repo is memoized so a
serial run collects the whole ~1677-test suite ONCE, not once-per-dir. Verified
DETERMINISTICALLY by counting `_collect_scope_uncached` calls -- the real collect is
stubbed, so these tests are fast and never spawn the ~22s worker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli import run_contract_gate


_NON_TMP_REPO = Path("/opt/nwave-real-repo")  # resolves outside tempdir; stubbed


@pytest.fixture(autouse=True)
def _clear_memo():
    run_contract_gate._COLLECT_MEMO.clear()
    yield
    run_contract_gate._COLLECT_MEMO.clear()


def _stub_uncached(monkeypatch):
    calls: list[tuple[Path, object]] = []
    sentinel = object()

    def fake(repo, paths=None):
        calls.append((repo, paths))
        return sentinel

    monkeypatch.setattr(run_contract_gate, "_collect_scope_uncached", fake)
    return calls, sentinel


def test_real_repo_collect_is_memoized(monkeypatch):
    """Non-temp repo + env set: the second collect HITS the memo (uncached called once)."""
    monkeypatch.setenv("NWAVE_COLLECT_MEMO", "1")
    calls, sentinel = _stub_uncached(monkeypatch)
    first = run_contract_gate._collect_scope(_NON_TMP_REPO)
    second = run_contract_gate._collect_scope(_NON_TMP_REPO)
    assert first is sentinel and second is sentinel
    assert len(calls) == 1  # collected ONCE; the second call hit the cache


def test_tmp_tree_is_never_memoized(monkeypatch, tmp_path):
    """Synthetic tmp trees (per-test, possibly mutated) are NEVER cached."""
    monkeypatch.setenv("NWAVE_COLLECT_MEMO", "1")
    calls, _ = _stub_uncached(monkeypatch)
    run_contract_gate._collect_scope(tmp_path)
    run_contract_gate._collect_scope(tmp_path)
    assert len(calls) == 2  # tmp tree: uncached called BOTH times


def test_no_memo_without_env(monkeypatch):
    """Production (no env var): exact pass-through, zero caching."""
    monkeypatch.delenv("NWAVE_COLLECT_MEMO", raising=False)
    calls, _ = _stub_uncached(monkeypatch)
    run_contract_gate._collect_scope(_NON_TMP_REPO)
    run_contract_gate._collect_scope(_NON_TMP_REPO)
    assert len(calls) == 2  # no env: no cache, uncached called BOTH times


def test_distinct_paths_get_distinct_cache_entries(monkeypatch):
    """The cache key includes the resolved repo path, so distinct repos never collide."""
    monkeypatch.setenv("NWAVE_COLLECT_MEMO", "1")
    calls, _ = _stub_uncached(monkeypatch)
    run_contract_gate._collect_scope(_NON_TMP_REPO)
    run_contract_gate._collect_scope(Path("/opt/other-real-repo"))
    assert len(calls) == 2  # two distinct repos: two collects
