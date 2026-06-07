"""Wheel content validation scenarios.

Validates that the hatchling-built wheel (.whl) contains exactly
the expected packages and excludes private/internal files.

Contract assertions:
  - DES module is present with expected structure
  - Install module is present with expected structure
  - No private files leak into the wheel (docs/analysis, tests/, .github/)
  - Wheel metadata is well-formed

These tests operate on real wheel files built by `python -m build --wheel`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.validation.validate_wheel_contents import (
    WheelContents,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory) -> Path:
    """Build a wheel from the current project and return its path.

    Uses module scope to avoid rebuilding for every test.
    """
    output_dir = tmp_path_factory.mktemp("wheel_output")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(output_dir)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Wheel build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    wheels = list(output_dir.glob("*.whl"))
    assert len(wheels) == 1, f"Expected exactly 1 wheel, found {len(wheels)}"
    return wheels[0]


@pytest.fixture(scope="module")
def wheel_contents(built_wheel: Path) -> WheelContents:
    """Parse the built wheel into a WheelContents structure."""
    from scripts.validation.validate_wheel_contents import parse_wheel_contents

    return parse_wheel_contents(built_wheel)


# ---------------------------------------------------------------------------
# Scenario: Valid wheel passes all checks
# ---------------------------------------------------------------------------


class TestValidWheelPassesAllChecks:
    """A correctly built wheel should produce zero violations."""

    def test_no_violations_on_valid_wheel(self, wheel_contents: WheelContents):
        """The current project wheel should pass all validation rules."""
        from scripts.validation.validate_wheel_contents import (
            build_wheel_manifest,
            validate_contents,
        )

        manifest = build_wheel_manifest()
        violations = validate_contents(wheel_contents, manifest)
        assert violations == [], (
            f"Expected zero violations, got {len(violations)}:\n"
            + "\n".join(f"  - [{v.category}] {v.message}" for v in violations)
        )


# ---------------------------------------------------------------------------
# Scenario: Missing DES module fails the gate
# ---------------------------------------------------------------------------


class TestMissingDesModuleFails:
    """A wheel without the DES module must be flagged."""

    def test_missing_des_init_detected(self):
        """Removing des/__init__.py from contents triggers a violation."""
        from scripts.validation.validate_wheel_contents import (
            build_wheel_manifest,
            validate_contents,
        )

        # Simulate a wheel missing the entire des/ package
        contents = WheelContents(
            file_paths=frozenset(
                [
                    "scripts/install/install_nwave.py",
                    "scripts/install/install_nwave.py",
                    "nwave-0.0.0.dist-info/METADATA",
                ]
            ),
            wheel_name="nwave-0.0.0-py3-none-any.whl",
        )
        manifest = build_wheel_manifest()
        violations = validate_contents(contents, manifest)

        missing_violations = [v for v in violations if v.category == "missing"]
        des_violations = [v for v in missing_violations if "des/" in v.message.lower()]
        assert len(des_violations) > 0, (
            "Expected at least one 'missing' violation for DES module, "
            f"got: {violations}"
        )

    def test_missing_des_domain_detected(self):
        """A wheel with des/ but missing des/domain/ triggers a violation."""
        from scripts.validation.validate_wheel_contents import (
            build_wheel_manifest,
            validate_contents,
        )

        contents = WheelContents(
            file_paths=frozenset(
                [
                    "des/__init__.py",
                    "des/application/__init__.py",
                    "des/adapters/__init__.py",
                    "scripts/install/install_nwave.py",
                    "nwave-0.0.0.dist-info/METADATA",
                ]
            ),
            wheel_name="nwave-0.0.0-py3-none-any.whl",
        )
        manifest = build_wheel_manifest()
        violations = validate_contents(contents, manifest)

        missing_violations = [v for v in violations if v.category == "missing"]
        domain_violations = [
            v for v in missing_violations if "des/domain" in v.message.lower()
        ]
        assert len(domain_violations) > 0, (
            f"Expected violation for missing des/domain/, got: {violations}"
        )


# ---------------------------------------------------------------------------
# Scenario: Missing install module fails the gate
# ---------------------------------------------------------------------------


class TestMissingInstallModuleFails:
    """A wheel without the install module must be flagged."""

    def test_missing_install_package_detected(self):
        """Removing install/ from contents triggers a violation."""
        from scripts.validation.validate_wheel_contents import (
            build_wheel_manifest,
            validate_contents,
        )

        contents = WheelContents(
            file_paths=frozenset(
                [
                    "des/__init__.py",
                    "des/domain/__init__.py",
                    "des/application/__init__.py",
                    "des/adapters/__init__.py",
                    "des/ports/__init__.py",
                    "des/cli/__init__.py",
                    "des/config/__init__.py",
                    "nwave-0.0.0.dist-info/METADATA",
                ]
            ),
            wheel_name="nwave-0.0.0-py3-none-any.whl",
        )
        manifest = build_wheel_manifest()
        violations = validate_contents(contents, manifest)

        missing_violations = [v for v in violations if v.category == "missing"]
        install_violations = [
            v for v in missing_violations if "install" in v.message.lower()
        ]
        assert len(install_violations) > 0, (
            f"Expected violation for missing install/ module, got: {violations}"
        )


# ---------------------------------------------------------------------------
# Scenario: Private file in wheel fails the gate
# ---------------------------------------------------------------------------


class TestPrivateFileInWheelFails:
    """Private/internal files must not appear in the wheel."""

    @pytest.mark.parametrize(
        "forbidden_path,description",
        [
            ("docs/analysis/some_internal.md", "internal analysis docs"),
            ("tests/conftest.py", "test files"),
            (".github/workflows/ci.yml", "CI workflows"),
            ("docs/feature/d-zt-01/deliver/roadmap.json", "feature docs"),
            ("pyproject.toml", "build config at wheel root"),
        ],
    )
    def test_forbidden_file_detected(self, forbidden_path: str, description: str):
        """Injecting a forbidden file into contents triggers a violation."""
        from scripts.validation.validate_wheel_contents import (
            build_wheel_manifest,
            validate_contents,
        )

        # Valid base contents + one forbidden file
        base_paths = [
            "des/__init__.py",
            "des/domain/__init__.py",
            "des/application/__init__.py",
            "des/adapters/__init__.py",
            "des/ports/__init__.py",
            "des/cli/__init__.py",
            "des/config/__init__.py",
            "scripts/install/__init__.py",
            "scripts/install/install_nwave.py",
            "nwave-0.0.0.dist-info/METADATA",
        ]
        contents = WheelContents(
            file_paths=frozenset([*base_paths, forbidden_path]),
            wheel_name="nwave-0.0.0-py3-none-any.whl",
        )
        manifest = build_wheel_manifest()
        violations = validate_contents(contents, manifest)

        forbidden_violations = [v for v in violations if v.category == "forbidden"]
        assert len(forbidden_violations) > 0, (
            f"Expected 'forbidden' violation for {description} ({forbidden_path}), "
            f"got: {violations}"
        )

    def test_real_wheel_has_no_private_files(self, wheel_contents: WheelContents):
        """The actual built wheel must contain zero private files."""
        from scripts.validation.validate_wheel_contents import (
            build_wheel_manifest,
            check_no_forbidden_files,
        )

        manifest = build_wheel_manifest()
        violations = check_no_forbidden_files(
            wheel_contents, manifest.forbidden_prefixes
        )
        assert violations == [], "Private files found in wheel:\n" + "\n".join(
            f"  - {v.message}" for v in violations
        )


# ---------------------------------------------------------------------------
# Scenario: Script CLI exit codes
# ---------------------------------------------------------------------------


class TestScriptExitCodes:
    """The validation script must exit 0 on valid wheel, non-zero on violation."""

    def test_valid_wheel_exits_zero(self, built_wheel: Path):
        """Running the script against a valid wheel exits with code 0."""
        result = subprocess.run(
            [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "scripts"
                    / "validation"
                    / "validate_wheel_contents.py"
                ),
                str(built_wheel),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Expected exit code 0 for valid wheel, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_nonexistent_wheel_exits_nonzero(self, tmp_path: Path):
        """Running the script against a nonexistent file exits non-zero."""
        fake_wheel = tmp_path / "nonexistent.whl"
        result = subprocess.run(
            [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "scripts"
                    / "validation"
                    / "validate_wheel_contents.py"
                ),
                str(fake_wheel),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit for nonexistent wheel, got {result.returncode}"
        )
