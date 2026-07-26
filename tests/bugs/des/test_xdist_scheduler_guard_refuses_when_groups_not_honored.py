"""Regression: `xdist_group` pins must not silently go unenforced.

tests/conftest.py pins shared-repo-state tests (real_repo_scan,
e2e_docker_install) onto xdist_group markers so the "loadgroup" scheduler
runs every group member on one worker -- never concurrently. Only
"loadgroup" honors that marker; the default "load" scheduler and
"worksteal" (the "test-fast" poe task's scheduler, see
the-declared-fast-test-task-defeats-the-serialization-its-own-conftest-builds
in defects.md) both silently ignore it, letting pinned tests race across
workers on the shared .nwave state.

`scheduler_guard_violation` is the pure decision function
`pytest_collection_modifyitems` calls to refuse loudly when that assumption
does not hold, instead of proceeding on a broken promise.
"""

from __future__ import annotations

from tests.conftest import scheduler_guard_violation


def test_no_violation_when_loadgroup_is_active():
    """
    GIVEN: xdist active with 4 workers, scheduler is "loadgroup", a group is pinned
    WHEN: scheduler_guard_violation() is called
    THEN: Returns None -- the assumption holds, nothing to refuse
    """
    assert (
        scheduler_guard_violation(
            numprocesses=4, active_dist="loadgroup", has_pinned_group=True
        )
        is None
    )


def test_no_violation_when_xdist_is_off():
    """
    GIVEN: xdist not active (serial run), a group is pinned
    WHEN: scheduler_guard_violation() is called
    THEN: Returns None -- serial execution can't race, regardless of scheduler
    """
    assert (
        scheduler_guard_violation(
            numprocesses=None, active_dist="no", has_pinned_group=True
        )
        is None
    )
    assert (
        scheduler_guard_violation(
            numprocesses=0, active_dist="no", has_pinned_group=True
        )
        is None
    )


def test_no_violation_when_nothing_is_pinned():
    """
    GIVEN: xdist active with a non-honoring scheduler, but no item carries
           an xdist_group marker
    WHEN: scheduler_guard_violation() is called
    THEN: Returns None -- there is no pinned promise to break
    """
    assert (
        scheduler_guard_violation(
            numprocesses=4, active_dist="load", has_pinned_group=False
        )
        is None
    )


def test_violation_when_worksteal_ignores_pinned_group():
    """
    GIVEN: xdist active with 4 workers, scheduler is "worksteal" (the
           test-fast poe task's scheduler before this fix), a group is pinned
    WHEN: scheduler_guard_violation() is called
    THEN: Returns a non-None message naming the active scheduler and the
          required "loadgroup" fix
    """
    message = scheduler_guard_violation(
        numprocesses=4, active_dist="worksteal", has_pinned_group=True
    )
    assert message is not None
    assert "worksteal" in message
    assert "loadgroup" in message


def test_violation_when_default_load_scheduler_ignores_pinned_group():
    """
    GIVEN: xdist active (-n auto style) with the scheduler unspecified,
           which pytest-xdist defaults to "load" -- also non-honoring
    WHEN: scheduler_guard_violation() is called
    THEN: Returns a non-None message
    """
    message = scheduler_guard_violation(
        numprocesses="auto", active_dist="load", has_pinned_group=True
    )
    assert message is not None
    assert "load" in message
