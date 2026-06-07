"""Machine-verifiable gate for backup-retention-policy DoD #3.

Rule source: ``docs/feature/backup-retention-policy/discuss/scope.md``
Definition of Done items #2 and #3:

- DoD #2: ``scripts/install/enhanced_backup_system.py`` is deleted.
- DoD #3: no remaining imports or references to ``EnhancedBackupSystem``
  after deletion.

This test converts that DoD checklist item into a failing-then-passing
test (the converted-to-failing-test pattern). Today it is RED — the file
still exists and is referenced — so it is marked ``@pytest.mark.skip``
to avoid blocking unrelated test runs while DELIVER is in flight.

After backup-retention-policy DELIVER GREEN, the crafter MUST:
1. Delete ``scripts/install/enhanced_backup_system.py``.
2. Remove every remaining reference to the ``EnhancedBackupSystem``
   identifier in the tree.
3. Remove the ``@pytest.mark.skip`` decorator on the test below.

When all three conditions hold, the test goes GREEN and the DoD is
machine-enforced from that point forward.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCAN_ROOTS = ("scripts", "tests", "nwave_ai")
_FORBIDDEN_IDENTIFIER = "EnhancedBackupSystem"


def test_enhanced_backup_system_is_fully_removed():
    """Assert DoD #2 and DoD #3 from scope.md are satisfied.

    See module docstring for the rule source. Two assertions:
    1. The module ``scripts.install.enhanced_backup_system`` is unimportable
       (the file has been deleted from disk).
    2. No ``.py`` file under ``scripts/``, ``tests/``, or ``nwave_ai/``
       contains the identifier ``EnhancedBackupSystem`` (this test file
       itself is excluded from the scan because it must reference the
       identifier in this docstring and in the assertion message).
    """
    # DoD #2: module no longer importable.
    spec = importlib.util.find_spec("scripts.install.enhanced_backup_system")
    assert spec is None, (
        "scope.md DoD #2 violated: scripts/install/enhanced_backup_system.py "
        "still exists and is importable. DELIVER must delete this file."
    )

    # DoD #3: no remaining textual references to the identifier.
    self_path = Path(__file__).resolve()
    offenders: list[str] = []
    for root_name in _SCAN_ROOTS:
        root = _REPO_ROOT / root_name
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            if py_file.resolve() == self_path:
                continue
            try:
                text = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if _FORBIDDEN_IDENTIFIER in text:
                offenders.append(str(py_file.relative_to(_REPO_ROOT)))

    assert not offenders, (
        f"scope.md DoD #3 violated: {len(offenders)} file(s) still reference "
        f"{_FORBIDDEN_IDENTIFIER!r}: {offenders}"
    )
