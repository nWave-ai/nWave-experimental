"""
Tests for per-plugin timing in PluginRegistry.install_all().

Step 02-02: Instrument PluginRegistry.install_all() with per-plugin timing.

Acceptance Criteria:
  AC1: Each plugin install() call is timed via time.perf_counter_ns
  AC2: PluginResult.duration_ms populated for each plugin
  AC3: Total installation time logged
  AC4: Existing behavior unchanged (backward compatible)

Test Budget: 2 behaviors x 2 = 4 max unit tests.
"""

import pytest

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)
from scripts.install.plugins.registry import PluginRegistry


class SlowPlugin(InstallationPlugin):
    """Plugin that takes measurable time to install."""

    def __init__(self, name: str, priority: int = 100):
        super().__init__(name, priority)

    def install(self, context: InstallContext) -> PluginResult:
        # Do enough work to produce a non-zero duration
        total = 0
        for i in range(10_000):
            total += i
        return PluginResult(
            success=True,
            plugin_name=self.name,
            message=f"{self.name} installed",
        )

    def verify(self, context: InstallContext) -> PluginResult:
        return PluginResult(
            success=True,
            plugin_name=self.name,
            message=f"{self.name} verified",
        )


class FailingPlugin(InstallationPlugin):
    """Plugin that fails during install."""

    def __init__(self, name: str, priority: int = 100):
        super().__init__(name, priority)

    def install(self, context: InstallContext) -> PluginResult:
        return PluginResult(
            success=False,
            plugin_name=self.name,
            message=f"{self.name} failed",
            errors=["Something went wrong"],
        )

    def verify(self, context: InstallContext) -> PluginResult:
        return PluginResult(
            success=True,
            plugin_name=self.name,
            message=f"{self.name} verified",
        )


@pytest.fixture
def context(tmp_path):
    """Create a minimal install context for testing."""
    log_messages = []
    logger = type(
        "MockLogger",
        (),
        {
            "error": lambda self, msg: log_messages.append(("error", msg)),
            "info": lambda self, msg: log_messages.append(("info", msg)),
        },
    )()
    logger._messages = log_messages
    return InstallContext(
        claude_dir=tmp_path,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=logger,
        project_root=tmp_path,
        framework_source=tmp_path,
        dry_run=False,
    )


class TestPerPluginTiming:
    """PluginRegistry.install_all() should time each plugin and populate duration_ms."""

    def test_each_plugin_result_has_duration_ms_populated(self, context):
        """AC1 + AC2: After install_all(), every PluginResult has a non-None
        duration_ms that is >= 0."""
        registry = PluginRegistry()
        registry.register(SlowPlugin("alpha", priority=10))
        registry.register(SlowPlugin("beta", priority=20))

        results = registry.install_all(context)

        for plugin_name, result in results.items():
            assert result.duration_ms is not None, (
                f"Plugin '{plugin_name}' should have duration_ms populated"
            )
            assert result.duration_ms >= 0, (
                f"Plugin '{plugin_name}' duration_ms should be non-negative"
            )

    def test_failing_plugin_also_has_duration_ms(self, context):
        """AC2: Even a failing plugin gets its duration_ms populated."""
        registry = PluginRegistry()
        registry.register(FailingPlugin("broken", priority=10))

        results = registry.install_all(context)

        assert results["broken"].duration_ms is not None
        assert results["broken"].duration_ms >= 0

    def test_total_installation_time_logged(self, context):
        """AC3: Total installation time is logged after all plugins complete."""
        registry = PluginRegistry(logger=context.logger)
        registry.register(SlowPlugin("alpha", priority=10))
        registry.register(SlowPlugin("beta", priority=20))

        registry.install_all(context)

        log_texts = [msg for _, msg in context.logger._messages]
        total_time_logged = any("total" in msg.lower() for msg in log_texts)
        assert total_time_logged, (
            f"Expected a log message containing 'total' time. Got: {log_texts}"
        )
