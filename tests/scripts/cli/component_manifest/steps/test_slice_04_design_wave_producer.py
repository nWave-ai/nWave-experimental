"""Step definitions -- slice-04: the DESIGN-wave producer change.

F-DESIGN-COMPONENT-MANIFEST slice-04. Layer 3 (FS acceptance), framework-asset
edit slice -- example-based, no PBT universe (Mandate 11). Reads the real repo
framework assets (Pillar 3 -- production files, not fixtures).

AT3 dogfoods: it drives the real validate_component_manifest CLI against this
feature's own component-manifest.yaml (residuality V2). Step bodies delegate to
``FrameworkAssetComposition`` / ``ComponentManifestComposition``; no inline
parsing logic (Mandate-12 criterion 3).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .framework_assets import FrameworkAssetComposition


scenarios("../slice-04-design-wave-producer.feature")

_REPO_ROOT = Path(__file__).resolve().parents[5]


@pytest.fixture
def assets() -> FrameworkAssetComposition:
    """Reads the production framework assets the producer change touches."""
    return FrameworkAssetComposition()


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Given -------------------------------------------------------------------


@given("the design wave's framework assets")
def given_framework_assets(assets: FrameworkAssetComposition) -> None:
    pass  # the assets fixture IS the production framework asset surface


@given("this feature's own component manifest")
def given_own_manifest(
    assets: FrameworkAssetComposition, result_box: dict[str, object]
) -> None:
    result_box["manifest_path"] = assets.own_manifest_path
    result_box["manifest_exists"] = assets.own_manifest_exists()


# --- When --------------------------------------------------------------------


@when("the architect validates the component manifest")
def when_validate_own_manifest(result_box: dict[str, object]) -> None:
    """Drive the production validate CLI against this feature's own manifest."""
    manifest_path = result_box["manifest_path"]
    assert result_box["manifest_exists"], (
        f"this feature ships no component-manifest.yaml at {manifest_path} "
        "-- residuality V2: the feature must dogfood its own contract"
    )
    result_box["result"] = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.cli.validate_component_manifest",
            str(manifest_path),
        ],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )


# --- Then --------------------------------------------------------------------


@then("the design task lists the component manifest as an expected output")
def then_design_task_lists_manifest(assets: FrameworkAssetComposition) -> None:
    assert assets.design_task_lists_manifest_as_output(), (
        "nWave/tasks/nw/design.md does not name component-manifest.yaml "
        "in its Expected Outputs"
    )


@then("the architect's quality gates require a validated component manifest")
def then_architect_quality_gate(assets: FrameworkAssetComposition) -> None:
    assert assets.architect_quality_gates_check_manifest(), (
        "nw-solution-architect Quality Gates do not require a validated "
        "component manifest"
    )


@then("the architecture patterns guidance documents the component manifest")
def then_arch_patterns_documents(assets: FrameworkAssetComposition) -> None:
    assert assets.architecture_patterns_skill_documents_manifest(), (
        "nw-architecture-patterns SKILL does not document the Component Manifest"
    )


@then("the component manifest is accepted")
def then_own_manifest_accepted(result_box: dict[str, object]) -> None:
    result = result_box["result"]
    assert result.returncode == 0, (
        f"this feature's own component-manifest.yaml is not valid "
        f"(exit {result.returncode}): {result.stderr}"
    )
