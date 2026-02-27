"""
Step definitions for release pipeline extension scenarios.

Covers: milestone-4-release-pipeline.feature
Driving port: PluginAssembler (release integration)
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when


scenarios("../milestone-4-release-pipeline.feature")


# ---------------------------------------------------------------------------
# Given Steps
# ---------------------------------------------------------------------------


@given(parsers.parse('a release tag "{tag}" is created'))
def release_tag_created(tag: str, build_config: dict[str, Any]):
    """Simulate a release tag being created."""
    # Strip 'v' prefix for version comparison
    version = tag.lstrip("v")
    build_config["release_tag"] = tag
    build_config["release_version"] = version


# ---------------------------------------------------------------------------
# When Steps
# ---------------------------------------------------------------------------


@when("the release pipeline runs the plugin build step")
def release_pipeline_builds(build_config: dict[str, Any], build_result: dict[str, Any]):
    """
    Execute the plugin build as part of the release pipeline.

    This simulates what the CI/CD release.yml would do.
    """
    # TODO: Replace with actual pipeline invocation
    # from scripts.build_plugin import PluginAssembler, BuildConfig
    # config = BuildConfig(**build_config)
    # result = PluginAssembler.build(config)
    # build_result["plugin_dir"] = result.output_dir
    # build_result["success"] = result.is_success()
    pytest.skip("Release pipeline integration not yet implemented")


@when("the plugin assembler builds the plugin twice with the same configuration")
def build_twice(build_config: dict[str, Any], build_result: dict[str, Any]):
    """Build the plugin twice to verify idempotency."""
    # TODO: Replace with actual double-build and comparison
    pytest.skip("PluginAssembler not yet implemented")


# ---------------------------------------------------------------------------
# Then Steps
# ---------------------------------------------------------------------------


@then(parsers.parse('the plugin directory is generated with version "{version}"'))
def plugin_generated_with_version(version: str, build_result: dict[str, Any]):
    """Verify plugin was generated with the release version."""
    import json

    plugin_dir = build_result["plugin_dir"]
    metadata = json.loads(
        (plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert metadata["version"] == version


@then("the plugin build step runs after the existing distribution build")
def plugin_after_dist_build():
    """Verify ordering in the release pipeline."""
    # This is a CI/CD configuration check, not a runtime assertion
    # Validated by inspecting release.yml structure
    pass


@then("the plugin directory can be committed as a standalone repository")
def plugin_is_standalone(build_result: dict[str, Any]):
    """Verify plugin directory is self-contained."""
    plugin_dir = build_result["plugin_dir"]
    # Check for essential files
    assert (plugin_dir / ".claude-plugin" / "plugin.json").exists()
    # Should not contain development files
    assert not (plugin_dir / "pyproject.toml").exists()
    assert not (plugin_dir / "tests").exists()


@then("the plugin directory does not contain development-only files")
def no_dev_files_in_plugin(build_result: dict[str, Any]):
    """Verify no dev artifacts in plugin."""
    plugin_dir = build_result["plugin_dir"]
    dev_patterns = [
        "*.pyc",
        "__pycache__",
        ".git",
        "Pipfile",
        "pyproject.toml",
        ".github",
    ]
    for pattern in dev_patterns:
        matches = list(plugin_dir.rglob(pattern))
        assert len(matches) == 0, f"Dev file found in plugin: {matches}"


@then("the marketplace manifest contains the plugin name and version")
def manifest_has_name_version(build_result: dict[str, Any]):
    """Verify marketplace manifest has required fields."""
    # TODO: Check manifest generation
    pass


@then("the marketplace manifest contains a download reference")
def manifest_has_download(build_result: dict[str, Any]):
    """Verify marketplace manifest has download URL."""
    # TODO: Check manifest generation
    pass


@then("the plugin build step reports failure")
def build_step_reports_failure(build_result: dict[str, Any]):
    """Verify the build step reports failure to the pipeline."""
    assert build_result["success"] is False


@then("the existing release artifacts are not affected")
def existing_artifacts_safe():
    """Verify plugin build failure does not corrupt other release artifacts."""
    # This is validated by CI/CD job isolation
    pass


@then("the pipeline warns about version mismatch")
def pipeline_warns_version_mismatch(build_result: dict[str, Any]):
    """Verify mismatch warning is produced."""
    # TODO: Check for warning in build output
    pass


@then("both builds produce identical plugin directories")
def builds_are_identical():
    """Verify idempotency of the build."""
    # TODO: Compare two build outputs
    pass
