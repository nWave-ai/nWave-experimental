"""pytest-bdd configuration for the fix-crafter-stash-structural-mitigation AT set.

Slice-01 (git-stash guard) scope: isolate the `NWAVE_GIT_STASH_ALLOW` env var
state per test so AT-2 (kill-switch set) does not leak the bypass into AT-1
(block path) or AT-3 (passthrough), where the ABSENCE of the env var is part
of the precondition.

The conftest is placed at the feature root (sibling of the .feature file)
rather than under steps to avoid a pytest plugin-name collision with sibling
features that also carry a steps/conftest.py.

RED-for-the-right-reason: the production driving port for slice-01 is the
script `scripts/hooks/git_stash_guard.py`. That script does NOT EXIST YET
(the crafter lands it in DELIVER). The composition fixture invokes the target
module as a real subprocess (Layer 3) via `python -m scripts.hooks.git_stash_guard`;
when the module is absent, the interpreter returns a non-zero exit with a
"No module named scripts.hooks.git_stash_guard" stderr and the fixture
surfaces this as AssertionError on the FIRST `Then` step. That is the correct
RED: the assertion fires because the implementation is missing, not because of
an import error or fixture setup bug.
"""

from __future__ import annotations

import os

import pytest


_ALLOW_ENV = "NWAVE_GIT_STASH_ALLOW"


@pytest.fixture(autouse=True)
def _isolate_allow_env() -> object:
    """Restore NWAVE_GIT_STASH_ALLOW around every test in this suite.

    AT-2 sets the env var; without restoration it leaks into AT-1 and AT-3
    where the absence of the env var is part of the precondition.
    """
    sentinel = object()
    saved = os.environ.get(_ALLOW_ENV, sentinel)
    try:
        yield
    finally:
        if saved is sentinel:
            os.environ.pop(_ALLOW_ENV, None)
        else:
            os.environ[_ALLOW_ENV] = saved  # type: ignore[arg-type]
