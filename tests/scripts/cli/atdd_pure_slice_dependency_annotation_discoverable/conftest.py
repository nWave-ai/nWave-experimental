"""pytest-bdd configuration for the slice-02 acceptance set.

ATDD-pure per-slice JIT: every scenario runs (no `@xfail`/`@skip`); the RED
ones fail with a real `AssertionError` naming the missing documentation,
never a collection/import error.
"""

from __future__ import annotations
