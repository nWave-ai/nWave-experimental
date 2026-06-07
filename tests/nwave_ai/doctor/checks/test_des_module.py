"""Acceptance tests for DesModuleCheck.

Tests enter through the check's run() driving port.
Pass path: des.domain package present under context.claude_dir/lib/python/.
Fail path: lib/python/ absent or des/domain absent — check returns passed=False gracefully.

Regression-or-contradiction note: the original tests pinned phase_events.py as
the marker file.  That behaviour was WRONG (phase_events.py was renamed to
phase_event.py).  The corrected behaviour is: presence of des/domain package
under the context lib/python path, checked via PathFinder with a restricted
search path (immune to process sys.path and to internal module renames).
The old tests are replaced here — they were pinning a false positive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from nwave_ai.doctor.checks.des_module import DesModuleCheck
from nwave_ai.doctor.context import DoctorContext


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def context(tmp_path: Path) -> DoctorContext:
    return DoctorContext(home_dir=tmp_path)


def _stage_des_domain(context: DoctorContext) -> None:
    """Create a minimal des.domain package under context.claude_dir/lib/python/.

    Deliberately omits phase_events.py — verifies the check is stable across
    internal module renames (real module has phase_event.py, not phase_events.py).
    """
    lib_python = context.claude_dir / "lib" / "python"
    des_dir = lib_python / "des"
    domain_dir = des_dir / "domain"
    domain_dir.mkdir(parents=True)
    (des_dir / "__init__.py").write_text("")
    (domain_dir / "__init__.py").write_text("")
    (domain_dir / "phase_event.py").write_text("# stub\n")


def test_passes_when_des_domain_present_without_phase_events(
    context: DoctorContext,
) -> None:
    """run() returns passed=True when des/domain exists even without phase_events.py."""
    _stage_des_domain(context)

    result = DesModuleCheck().run(context)

    assert result.passed is True


def test_fails_gracefully_when_lib_python_absent(context: DoctorContext) -> None:
    """run() returns passed=False (no exception) when lib/python/ does not exist.

    No filesystem staging — the check searches only the context path, so
    process sys.path (which may contain the real DES) is irrelevant.
    """
    result = DesModuleCheck().run(context)

    assert result.passed is False
    assert result.remediation is not None


def test_fails_when_des_package_absent_but_lib_python_exists(
    context: DoctorContext,
) -> None:
    """run() returns passed=False when lib/python exists but contains no des package."""
    lib_python = context.claude_dir / "lib" / "python"
    lib_python.mkdir(parents=True)

    result = DesModuleCheck().run(context)

    assert result.passed is False
    assert result.remediation is not None
