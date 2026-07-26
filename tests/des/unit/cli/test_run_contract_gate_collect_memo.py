"""`_collect_scope` memoization (velocity-v2 <5min goal G-143).

Under ``NWAVE_COLLECT_MEMO`` the collect of the REAL (non-temp) repo is memoized so a
serial run collects the whole ~1677-test suite ONCE, not once-per-dir. Verified
DETERMINISTICALLY by counting `_collect_scope_uncached` calls -- the real collect is
stubbed, so these tests are fast and never spawn the ~22s worker.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.cli import run_contract_gate


_NON_TMP_REPO = Path("/opt/nwave-real-repo")  # resolves outside tempdir; stubbed

_PARENT_HEAD = "1111111111111111111111111111111111111111"
_CHILD_HEAD = "2222222222222222222222222222222222222222"


def _stub_head(monkeypatch, sha=_PARENT_HEAD):
    """Give the (fictional) repo a resolvable committed HEAD -- the memo's key axis.

    Required by every test that expects a memo HIT: the memo keys on a HEAD sha and
    BYPASSES itself when `rev-parse HEAD` cannot produce one, so a repo left without
    a stubbed HEAD is simply never cached.
    """
    monkeypatch.setattr(run_contract_gate, "_git", lambda repo, *args: f"{sha}\n")


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
    _stub_head(monkeypatch)
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
    _stub_head(monkeypatch)  # both repos on ONE head: only the path can tell them apart
    calls, _ = _stub_uncached(monkeypatch)
    run_contract_gate._collect_scope(_NON_TMP_REPO)
    run_contract_gate._collect_scope(Path("/opt/other-real-repo"))
    assert len(calls) == 2  # two distinct repos: two collects


def _stub_head_and_tree(monkeypatch, state: dict[str, object]):
    """Bind BOTH the memo's HEAD axis and the collect answer to one `state` dict.

    `state["head"]` is what `git rev-parse HEAD` reports; `state["node_ids"]` is
    what a fresh collect of that committed scope yields. Moving HEAD moves both
    together -- exactly as a real commit does. A `state["head"]` of ``None`` models
    a tree with NO resolvable HEAD: `rev-parse` fails, exactly as it does on an
    unborn branch.
    """

    def _rev_parse(repo, *args):
        if state["head"] is None:
            raise subprocess.CalledProcessError(128, ("git", *args))
        return f"{state['head']}\n"

    monkeypatch.setattr(run_contract_gate, "_git", _rev_parse)
    monkeypatch.setattr(
        run_contract_gate,
        "_collect_scope_uncached",
        lambda repo, paths=None: run_contract_gate._CollectedScope(
            node_ids=list(state["node_ids"]),
            collected_count=len(state["node_ids"]),
        ),
    )


def test_two_heads_same_paths_do_not_share_a_collect_digest(monkeypatch):
    """Two committed scopes differing ONLY in HEAD get TWO digests, not one.

    The terminating run and the G_COMMIT exit gate ask about DIFFERENT HEADs on
    purpose (`commit_slice` module docstring): at terminating-run time HEAD is
    still the slice's PARENT, after the commit HEAD includes the new files. The
    repo, the requested paths and the markers are identical across that pair --
    so a memo key that omits HEAD makes the second question silently reuse the
    FIRST question's answer, certifying the parent tree as if it were the child.
    """
    monkeypatch.setenv("NWAVE_COLLECT_MEMO", "1")
    state: dict[str, object] = {
        "head": _PARENT_HEAD,
        "node_ids": ["tests/t.py::test_already_there"],
    }
    _stub_head_and_tree(monkeypatch, state)

    parent_scope = run_contract_gate._collect_scope(_NON_TMP_REPO)

    # The slice commits: HEAD advances and its committed scope gains a test.
    state["head"] = _CHILD_HEAD
    state["node_ids"] = ["tests/t.py::test_already_there", "tests/t.py::test_new"]

    child_scope = run_contract_gate._collect_scope(_NON_TMP_REPO)

    parent_digest = run_contract_gate.compute_gate_scope_digest(parent_scope.node_ids)
    child_digest = run_contract_gate.compute_gate_scope_digest(child_scope.node_ids)
    assert parent_digest != child_digest, (
        "two committed scopes differing only in HEAD collapsed to ONE digest -- "
        "the memo key omits HEAD, so the exit gate re-used the terminating run's "
        f"answer for the parent tree (both {parent_digest})"
    )


def test_same_head_repeat_still_hits_the_memo(monkeypatch):
    """The key NARROWS, never loosens: a genuine repeat on ONE head still HITS.

    67% of a session's collects are same-HEAD repeats (24 calls -> 8 keys on
    `test_deliver_finalize_unmissable.py`); a HEAD-inclusive key must still
    collapse those, or the fix would trade correctness for the whole memo.
    """
    monkeypatch.setenv("NWAVE_COLLECT_MEMO", "1")
    _stub_head(monkeypatch)
    calls, _ = _stub_uncached(monkeypatch)
    run_contract_gate._collect_scope(_NON_TMP_REPO)
    run_contract_gate._collect_scope(_NON_TMP_REPO)
    assert len(calls) == 1  # same head, same paths, same markers: ONE collect


def test_memo_is_not_consulted_when_head_is_unresolvable(monkeypatch):
    """No HEAD, no cache: an unresolvable HEAD BYPASSES the memo entirely.

    A HEAD sha is what the key uses to name a tree's committed state. When
    `rev-parse HEAD` fails there is no such name -- and a missing name is not a
    name every HEAD-less tree may share: two unborn repos can agree on repo,
    paths and markers and still hold different bytes, and ONE unborn repo mutated
    mid-session is two different trees under one key. So the memo is not
    consulted at all rather than consulted with a placeholder axis.

    Costs nothing: a tree with no committed state has next to nothing to gain
    from a cache of its committed scope.
    """
    monkeypatch.setenv("NWAVE_COLLECT_MEMO", "1")
    state: dict[str, object] = {
        "head": None,  # `rev-parse HEAD` fails -- unborn branch, no git, no work-tree
        "node_ids": ["tests/t.py::test_before"],
    }
    _stub_head_and_tree(monkeypatch, state)

    before = run_contract_gate._collect_scope(_NON_TMP_REPO)

    # The HEAD-less tree is mutated mid-session: still no HEAD to tell the two apart.
    state["node_ids"] = ["tests/t.py::test_before", "tests/t.py::test_after"]

    after = run_contract_gate._collect_scope(_NON_TMP_REPO)

    assert run_contract_gate._COLLECT_MEMO == {}, (
        "a HEAD-less tree was cached -- the memo keyed it on the absent HEAD, so "
        "every HEAD-less tree (and every mid-session mutation of one) shares that "
        f"entry: {run_contract_gate._COLLECT_MEMO!r}"
    )
    before_digest = run_contract_gate.compute_gate_scope_digest(before.node_ids)
    after_digest = run_contract_gate.compute_gate_scope_digest(after.node_ids)
    assert before_digest != after_digest, (
        "two different states of ONE HEAD-less tree collapsed to a single digest -- "
        f"the second collect re-used the first's cached answer (both {before_digest})"
    )
