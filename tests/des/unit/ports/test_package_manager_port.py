"""Unit tests for PackageManagerPort Protocol and FakePackageManager test double.

Behaviors covered (budget: 3 behaviors x 2 = 6 tests max):
1. FakePackageManager conforms to PackageManagerPort (structural typing)
2. will_succeed() programs next upgrade to return success
3. will_fail(reason) programs next upgrade to return failure with reason
   (includes call recording as part of the behavioral assertion)
"""

from __future__ import annotations

import pytest

from des.adapters.driven.package_managers.fake_package_manager import (
    FakePackageManager,
)
from des.ports.driven_ports.package_manager_port import (
    PackageManagerPort,
    UpgradeResult,
)


class TestPackageManagerPortContract:
    def test_fake_package_manager_is_instance_of_port(self) -> None:
        fake = FakePackageManager()
        assert isinstance(fake, PackageManagerPort)


class TestFakePackageManagerBehavior:
    def test_will_succeed_causes_upgrade_to_return_success(self) -> None:
        fake = FakePackageManager()
        fake.will_succeed()

        result = fake.upgrade("/usr/local/bin/pipx", "2.0.0")

        assert result == UpgradeResult(success=True, error=None)

    def test_will_fail_causes_upgrade_to_return_failure_with_reason(self) -> None:
        fake = FakePackageManager()
        fake.will_fail("network unreachable")

        result = fake.upgrade("/usr/local/bin/pipx", "2.0.0")

        assert result == UpgradeResult(success=False, error="network unreachable")

    def test_upgrade_records_all_calls(self) -> None:
        fake = FakePackageManager()
        fake.will_succeed()
        fake.upgrade("/usr/bin/pipx", "1.0.0")
        fake.will_succeed()
        fake.upgrade("/usr/bin/uv", "2.0.0")

        assert fake.calls == [
            ("/usr/bin/pipx", "1.0.0"),
            ("/usr/bin/uv", "2.0.0"),
        ]

    def test_upgrade_without_programming_raises(self) -> None:
        fake = FakePackageManager()
        with pytest.raises(AssertionError):
            fake.upgrade("/usr/bin/pipx", "1.0.0")
