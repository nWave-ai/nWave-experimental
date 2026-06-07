"""slice-02 arch-test: reverify imports the wrapper or the SSOT (DDD-9).

Closes the residuality risk noted in
``docs/feature/fix-reverify-e1-via-scoped-wrapper/feature-delta.md`` sec.
"Residuality pass" entry "arch-test slice-02": a future contributor reverting
``_compose_gates`` to the global-scope CLI would silently re-instantiate the
W5 cross-feature-collision defect. This arch-test fails closed when the
production reverify CLI imports NEITHER the new wrapper (``check_slice_at_completeness``)
NOR the SSOT module (``slice_at_completeness``) -- the only two paths
guaranteed to be feature-scoped.

Also fails closed on path drift: if the source file cannot be read, the
arch-test errors rather than silently passing on an empty grep (residuality
risk catalogued under "arch-test self-coverage").
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.acceptance


_REVERIFY_SOURCE = (
    Path(__file__).resolve().parents[4]
    / "src"
    / "des"
    / "cli"
    / "reverify_slice_commit.py"
)

# The two import strings that guarantee feature-scoped E1 invocation. Either
# the wrapper CLI module name (current shape, post slice-02) or the SSOT
# module (a hypothetical future in-process refactor) suffice.
_FEATURE_SCOPED_E1_MARKERS = (
    "des.cli.check_slice_at_completeness",
    "des.application.slice_at_completeness",
)


def test_reverify_e1_invocation_is_feature_scoped() -> None:
    """The production reverify CLI must reach feature-scoped E1.

    Fails closed on (a) path drift (source not found) and (b) future revert
    to the global-scope ``verify_slice_commit_completeness`` invocation.
    """
    assert _REVERIFY_SOURCE.is_file(), (
        f"arch-test path drift: cannot find {_REVERIFY_SOURCE!s}; the "
        f"arch-test silently passing on an empty source would mask the "
        f"W5 cross-feature-collision regression vector."
    )
    source = _REVERIFY_SOURCE.read_text(encoding="utf-8")
    found = [marker for marker in _FEATURE_SCOPED_E1_MARKERS if marker in source]
    assert found, (
        f"reverify_slice_commit.py mentions NONE of "
        f"{_FEATURE_SCOPED_E1_MARKERS!r}; E1 has likely been reverted to the "
        f"global-scope verify_slice_commit_completeness path, re-instantiating "
        f"F-REVERIFY-E1-GLOBAL-SCOPE-COLLISION (W5)."
    )
