"""Attempt-cap acceptance tests for auto-update-deferred (step 03-01).

Hardens the ``PendingUpdateService.apply()`` state machine beyond the
walking-skeleton happy path:

- Example scenario: "Third consecutive failure drops the flag and prompts
  manual retry" — drives the full failure trajectory from attempt_count=0.
- Property scenario: "Attempt count never exceeds 3 regardless of repeated
  failures" — hypothesis-based invariant over arbitrary initial counts and
  call volumes.

Strategy C: real temp-filesystem I/O, FakePackageManager at the
PackageManagerPort boundary. Enters through the ``PendingUpdateService``
driving port only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.package_managers.fake_package_manager import (
    FakePackageManager,
)
from des.application.pending_update_service import PendingUpdateService
from des.domain.pending_update_flag import PendingUpdateFlag


if TYPE_CHECKING:
    from collections.abc import Callable


pytestmark = [pytest.mark.acceptance]


class _AlwaysFailPackageManager(FakePackageManager):
    """FakePackageManager variant that auto-reprograms a failure before each call.

    The base FakePackageManager requires `will_fail()` to be invoked before
    every `upgrade()` call. For property-based testing with arbitrary call
    volumes this is unwieldy, so we self-program on each invocation.
    """

    def __init__(self, reason: str = "network error: unreachable") -> None:
        super().__init__()
        self._reason = reason

    def upgrade(self, pm_binary_abspath: str, target_version: str):  # type: ignore[no-untyped-def]
        self.will_fail(self._reason)
        return super().upgrade(pm_binary_abspath, target_version)


# --- Example scenario -------------------------------------------------------


def test_third_consecutive_failure_drops_flag_and_prompts_manual_retry(
    des_config: DESConfig,
    fake_package_manager_factory: Callable[[], FakePackageManager],
    existing_pm_binary: Callable[[str], str],
) -> None:
    """Scenario: Third consecutive failure drops the flag and prompts manual retry.

    Given: a fresh pending-update flag (attempt_count=0).
    When:  apply() runs three times with a failing package manager.
    Then:  after the 3rd attempt, the flag is GONE and the caller receives
           a manual-intervention message; the package manager was invoked
           exactly 3 times, never more.
    """
    pipx_path = existing_pm_binary("pipx")
    # Given: fresh flag, no prior attempts
    initial = PendingUpdateFlag(
        pm="pipx",
        pm_binary_abspath=pipx_path,
        target_version="3.11.0",
        requested_at=datetime.now(timezone.utc).isoformat(),
    )
    des_config.save_pending_update_state(initial)

    pm = fake_package_manager_factory()
    service = PendingUpdateService(config=des_config, pm=pm)

    # When: 1st failure — flag retained with attempt_count=1
    pm.will_fail("net err 1")
    r1 = service.apply()
    assert r1.success is False
    flag1 = des_config.read_pending_update()
    assert flag1 is not None and flag1.attempt_count == 1

    # When: 2nd failure — flag retained with attempt_count=2
    pm.will_fail("net err 2")
    r2 = service.apply()
    assert r2.success is False
    flag2 = des_config.read_pending_update()
    assert flag2 is not None and flag2.attempt_count == 2

    # When: 3rd failure — flag retained with attempt_count=3 (cap reached)
    pm.will_fail("net err 3")
    r3 = service.apply()
    assert r3.success is False
    flag3 = des_config.read_pending_update()
    assert flag3 is not None
    assert flag3.attempt_count == 3

    # When: subsequent apply() runs with flag already at cap
    calls_before = len(pm.calls)
    r4 = service.apply()

    # Then: PM NOT invoked; flag dropped; manual-intervention message surfaced
    assert len(pm.calls) == calls_before, (
        "apply() must not invoke the package manager once the attempt cap "
        "has been reached"
    )
    assert des_config.read_pending_update() is None
    assert r4.success is False
    assert r4.error is not None
    err_lower = r4.error.lower()
    assert "manual" in err_lower or "re-run" in err_lower or "rerun" in err_lower

    # And: PM was called exactly 3 times across the whole trajectory
    assert len(pm.calls) == 3


# --- Property scenario ------------------------------------------------------


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    initial_attempt_count=st.integers(min_value=0, max_value=2),
    extra_calls=st.integers(min_value=0, max_value=10),
)
def test_attempt_count_never_exceeds_three_regardless_of_repeated_failures(
    tmp_path_factory: pytest.TempPathFactory,
    initial_attempt_count: int,
    extra_calls: int,
) -> None:
    """Scenario: Attempt count never exceeds 3 regardless of repeated failures.

    Invariant: starting from any initial attempt_count in [0, 2] and calling
    apply() any number of times against an always-failing package manager:

    - The package manager is invoked at most (3 - initial_attempt_count) times.
    - At every observable moment the persisted flag is either absent OR has
      attempt_count <= 3.
    - Once the cap is reached the flag is eventually dropped and subsequent
      calls do not invoke the package manager again.
    """
    # Fresh temp dir per hypothesis example — isolate DESConfig state.
    tmp = tmp_path_factory.mktemp("attempt_cap_prop")
    config = DESConfig(config_path=tmp / ".nwave" / "des-config.json")
    pipx_bin = tmp / "bin" / "pipx"
    pipx_bin.parent.mkdir(parents=True, exist_ok=True)
    pipx_bin.write_text("#!/bin/sh\n")

    initial = PendingUpdateFlag(
        pm="pipx",
        pm_binary_abspath=str(pipx_bin),
        target_version="9.9.9",
        requested_at=datetime.now(timezone.utc).isoformat(),
        attempt_count=initial_attempt_count,
        last_error="prior failure" if initial_attempt_count > 0 else None,
    )
    config.save_pending_update_state(initial)

    pm = _AlwaysFailPackageManager()
    service = PendingUpdateService(config=config, pm=pm)

    # Need (3 - initial) failing calls to reach cap, plus ONE more call to
    # trigger the cap-drop path. Extra calls beyond that must be no-ops.
    required_calls = (3 - initial_attempt_count) + 1
    total_calls = required_calls + extra_calls
    for _ in range(total_calls):
        service.apply()
        # Invariant after each call: flag absent OR attempt_count <= 3.
        flag = config.read_pending_update()
        if flag is not None:
            assert 0 <= flag.attempt_count <= 3

    # Terminal state: flag MUST be gone (cap dropped it).
    assert config.read_pending_update() is None
    # PM invocations bounded by the remaining-attempts budget. The cap-drop
    # call and any extra post-cap calls MUST NOT invoke the PM.
    expected_pm_calls = 3 - initial_attempt_count
    assert len(pm.calls) == expected_pm_calls, (
        f"expected exactly {expected_pm_calls} PM calls from initial count "
        f"{initial_attempt_count}, got {len(pm.calls)}"
    )
