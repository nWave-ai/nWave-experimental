"""FakePackageManager - in-memory test double for PackageManagerPort."""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.ports.driven_ports.package_manager_port import UpgradeResult


if TYPE_CHECKING:
    from collections.abc import Callable


class FakePackageManager:
    """Test double that records calls and returns programmed outcomes.

    Program the next upgrade result via `will_succeed()` or `will_fail(reason)`.
    Call history is available via the `calls` attribute as a list of
    (pm_binary_abspath, target_version) tuples.

    For ordering assertions (e.g. banner emitted before upgrade invoked),
    tests may assign ``pre_call_hook`` -- a zero-arg callable fired at the
    top of ``upgrade()`` before the result is returned.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._next_result: UpgradeResult | None = None
        self.pre_call_hook: Callable[[], None] | None = None

    def will_succeed(self) -> None:
        self._next_result = UpgradeResult(success=True, error=None)

    def will_fail(self, reason: str) -> None:
        self._next_result = UpgradeResult(success=False, error=reason)

    def will_fail_in_phase(self, phase: str, reason: str) -> None:
        """Program the next upgrade to fail in a specific phase.

        ``phase`` is either ``"pm_upgrade"`` or ``"nwave_install"`` and maps
        onto the two-phase upgrade model orchestrated by the real adapter
        (``pipx upgrade nwave-ai`` followed by ``nwave-ai install``).
        """
        self._next_result = UpgradeResult(success=False, error=reason, phase=phase)

    def upgrade(self, pm_binary_abspath: str, target_version: str) -> UpgradeResult:
        assert self._next_result is not None, (
            "FakePackageManager must be programmed via will_succeed() or "
            "will_fail(reason) before upgrade() is called"
        )
        if self.pre_call_hook is not None:
            self.pre_call_hook()
        self.calls.append((pm_binary_abspath, target_version))
        result = self._next_result
        self._next_result = None
        return result
