"""Regression: NWAVE_COLLECT_MEMO must be active for the WHOLE suite, not just
``tests/des/acceptance/``.

``run_contract_gate._collect_scope`` (src/des/cli/run_contract_gate.py) memoizes the
real repo's whole-tree pytest collection across a session under ``NWAVE_COLLECT_MEMO``
-- but today only ``tests/des/acceptance/conftest.py`` sets that env var
(``os.environ.setdefault("NWAVE_COLLECT_MEMO", "1")``). The root ``tests/conftest.py``
does not, so any test session that does not include ``tests/des/acceptance/`` -- e.g.
``tests/des/cli/`` or ``tests/des/integration/`` run alone -- never activates the
cache and re-pays the ~20s+ real-repo collection on every call.

This file lives OUTSIDE ``tests/des/acceptance/`` (a representative sample of the
uncovered directories, per the charter's own repro instructions), so running it in
isolation (``pytest tests/bugs/des/test_collect_memo_active_outside_acceptance_dir.py``)
reproduces the defect directly: no ancestor conftest of this file sets
``NWAVE_COLLECT_MEMO``.

Charter: docs/product/expectations/fix-collect-memo-root-conftest/
         whole-suite-shares-one-real-repo-collection.md

Negative-safety companion (charter oracle 3, "cache never latches onto a synthetic
tree"): already covered by the dedicated regression test
``tests/des/unit/cli/test_run_contract_gate_collect_memo.py::test_tmp_tree_is_never_memoized``
-- relied upon here rather than duplicated (DRY/reuse-first).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from des.cli import run_contract_gate


# Resolves outside tempfile.gettempdir() -- a stand-in for "this repo's real,
# immutable tree" (mirrors the dedicated unit test's own stub repo path).
_NON_TMP_REPO = Path("/opt/nwave-real-repo-outside-acceptance")


@pytest.fixture(autouse=True)
def _clear_memo():
    run_contract_gate._COLLECT_MEMO.clear()
    yield
    run_contract_gate._COLLECT_MEMO.clear()


def test_nwave_collect_memo_env_active_outside_acceptance_dir():
    """NWAVE_COLLECT_MEMO must be set for a test running outside tests/des/acceptance/.

    This test module's own ancestor conftest chain is tests/bugs/des/ ->
    tests/bugs/ -> tests/conftest.py (root) -- tests/des/acceptance/conftest.py is
    NOT an ancestor and is never imported for this file. Today only that acceptance
    conftest sets NWAVE_COLLECT_MEMO, so it is absent here -- RED for the right
    reason (the env var the caching mechanism keys on is simply unset).
    """
    assert os.environ.get("NWAVE_COLLECT_MEMO"), (
        "NWAVE_COLLECT_MEMO is not set outside tests/des/acceptance/ -- the "
        "whole-suite collection memo (run_contract_gate._collect_scope) is "
        "inactive for this directory, so the real repo's ~20s+ collection is "
        "re-paid on every call instead of once per session"
    )


def test_real_repo_collect_scope_is_memoized_from_non_acceptance_context(monkeypatch):
    """Calling _collect_scope twice for the real repo, from a non-acceptance test,
    must hit the cache the second time -- exercising the ACTUAL production seam
    (_COLLECT_MEMO / _collect_scope), not just the env var's presence.

    Deliberately does NOT monkeypatch NWAVE_COLLECT_MEMO itself: the point is to
    observe whether the AMBIENT environment (as set up by conftest chain) already
    activates the memo here. Today it does not (see the sibling test above), so
    _collect_scope's env check is false on both calls and the uncached collector
    runs twice -- RED via a real assertion (len(calls) == 1) failing with 2.
    """
    calls: list[tuple[Path, object]] = []
    sentinel = object()

    def fake_uncached(repo, paths=None):
        calls.append((repo, paths))
        return sentinel

    monkeypatch.setattr(run_contract_gate, "_collect_scope_uncached", fake_uncached)

    first = run_contract_gate._collect_scope(_NON_TMP_REPO)
    second = run_contract_gate._collect_scope(_NON_TMP_REPO)

    assert first is sentinel and second is sentinel
    assert len(calls) == 1, (
        f"expected the real repo's collect to be memoized (1 uncached call), got "
        f"{len(calls)} -- NWAVE_COLLECT_MEMO is not active outside "
        "tests/des/acceptance/, so no caching occurred"
    )


def test_tmp_repo_scope_is_never_memoized_from_non_acceptance_context(
    monkeypatch, tmp_path
):
    """Negative safety companion (charter oracle, negative bullet 3): even once
    the memo is active, a synthetic/temporary tree must NEVER be served from the
    cache -- it must be re-collected on every call, unlike the real repo above.

    Forces NWAVE_COLLECT_MEMO on (unlike the sibling tests above) to exercise the
    widened-cache's safety boundary in THIS file's own context, distinct from --
    not a substitute for -- the dedicated cache-mechanism regression test
    ``tests/des/unit/cli/test_run_contract_gate_collect_memo.py::test_tmp_tree_is_never_memoized``,
    which already pins this property directly against ``_collect_scope`` and is
    relied upon rather than re-derived here.
    """
    monkeypatch.setenv("NWAVE_COLLECT_MEMO", "1")
    calls: list[tuple[Path, object]] = []

    def fake_uncached(repo, paths=None):
        calls.append((repo, paths))
        return object()

    monkeypatch.setattr(run_contract_gate, "_collect_scope_uncached", fake_uncached)

    run_contract_gate._collect_scope(tmp_path)
    run_contract_gate._collect_scope(tmp_path)

    assert len(calls) == 2, (
        f"a synthetic tmp tree must NEVER be memoized, got {len(calls)} uncached "
        "call(s) -- the cache must not latch onto a per-test fixture tree"
    )
