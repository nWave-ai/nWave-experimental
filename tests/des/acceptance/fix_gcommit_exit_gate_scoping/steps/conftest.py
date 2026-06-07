"""Pytest config for fix-gcommit-exit-gate-scoping acceptance tests.

slice-01 is the ENTERING slice (atdd_pure per-slice JIT, ADR-028 D2 /
`feedback_atdd_pure_distill_per_slice_jit_canonical_2026_05_30`). Its ATs are
authored as genuine UNMARKED RED -- the production fix (committed-tree digest +
git-absent LOUD-INDETERMINATE refusal) does not exist yet, so DELIVER's
A_GREEN_ATS turns them green. They are NOT xfail-marked: the dispatch requires
RED-for-right-reason to be observable directly.

These ATs spawn a real `pytest --collect-only` worker subprocess (via the
`des run-contract-gate` CLI) and a real `git` subprocess against a tmp_path
repo. They are layer-3 real-IO acceptance tests.
"""

from __future__ import annotations
