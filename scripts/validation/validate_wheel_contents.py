#!/usr/bin/env python3
"""Wheel content assertion gate.

Validates that a hatchling-built wheel (.whl) contains exactly the
expected Python packages and excludes private/internal files.

Pure validation pipeline:
  parse_wheel_contents(path) -> WheelContents
  build_wheel_manifest()     -> WheelManifest
  validate_contents(contents, manifest) -> list[Violation]

Usage:
    python scripts/validation/validate_wheel_contents.py dist/nwave-*.whl
"""

from __future__ import annotations

import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """A single wheel content violation."""

    category: str  # "missing" | "forbidden" | "structure"
    message: str


@dataclass(frozen=True)
class WheelContents:
    """Parsed contents of a wheel file."""

    file_paths: frozenset[str]
    wheel_name: str


@dataclass(frozen=True)
class WheelManifest:
    """Expected wheel contents specification."""

    required_prefixes: list[str] = field(default_factory=list)
    forbidden_prefixes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure functions: parsing
# ---------------------------------------------------------------------------


def parse_wheel_contents(wheel_path: Path) -> WheelContents:
    """Extract the file listing from a wheel ZIP archive.

    Returns a WheelContents with all file paths inside the wheel.
    Raises FileNotFoundError if the wheel does not exist.
    Raises zipfile.BadZipFile if the file is not a valid ZIP.
    """
    if not wheel_path.exists():
        msg = f"Wheel file not found: {wheel_path}"
        raise FileNotFoundError(msg)

    with zipfile.ZipFile(wheel_path) as zf:
        paths = frozenset(zf.namelist())

    return WheelContents(file_paths=paths, wheel_name=wheel_path.name)


# ---------------------------------------------------------------------------
# Pure functions: manifest construction
# ---------------------------------------------------------------------------


def build_wheel_manifest() -> WheelManifest:
    """Build the expected manifest for the nwave wheel.

    The nwave wheel (built by hatchling) should contain:
      - des/ package (DES runtime: domain, application, adapters, ports, cli, config)
      - install/ package (installer scripts and plugins)

    It must NOT contain (mirrors the e2e privacy contract in
    ``tests/e2e/test_wheel_privacy_contract.py``; SSOT pinned by
    ``tests/build/test_wheel_manifest_ssot.py``):
      - docs/analysis/      (internal RCA reports, audits)
      - docs/feature/       (in-flight feature tracking + acks)
      - .github/            (CI workflows, secrets references)
      - src/des/            (DES source — wheel ships ``des/`` rewritten)
      - tests/              (test suite)
      - pyproject.toml      (internal build config; METADATA is fine)
      - scripts/release/    (release-automation tooling, private)
      - scripts/hooks/      (pre-commit hook scripts, dev-only)
      - scripts/framework/  (framework build utilities, dev-only)
      - scripts/validation/ (CI validators, dev-only)
    """
    return WheelManifest(
        required_prefixes=[
            "des/__init__.py",
            "des/domain/",
            "des/application/",
            "des/adapters/",
            "des/ports/",
            "des/cli/",
            "des/config/",
            "scripts/install/install_nwave.py",
            "scripts/install/plugins/",
        ],
        forbidden_prefixes=[
            "docs/analysis/",
            "docs/feature/",
            ".github/",
            "src/des/",
            "tests/",
            "pyproject.toml",
            "scripts/release/",
            "scripts/hooks/",
            "scripts/framework/",
            "scripts/validation/",
        ],
    )


# ---------------------------------------------------------------------------
# Pure functions: validation rules
# ---------------------------------------------------------------------------


def check_required_prefixes(
    contents: WheelContents, required_prefixes: list[str]
) -> list[Violation]:
    """Check that all required prefixes have at least one matching file."""
    violations: list[Violation] = []

    for prefix in required_prefixes:
        has_match = any(
            path == prefix or path.startswith(prefix) for path in contents.file_paths
        )
        if not has_match:
            violations.append(
                Violation(
                    category="missing",
                    message=f"Required path not found in wheel: {prefix}",
                )
            )

    return violations


def check_no_forbidden_files(
    contents: WheelContents, forbidden_prefixes: list[str]
) -> list[Violation]:
    """Check that no file in the wheel matches a forbidden prefix."""
    violations: list[Violation] = []

    for path in sorted(contents.file_paths):
        for prefix in forbidden_prefixes:
            if path == prefix or path.startswith(prefix):
                violations.append(
                    Violation(
                        category="forbidden",
                        message=f"Forbidden file in wheel: {path}",
                    )
                )
                break  # one violation per file is enough

    return violations


# ---------------------------------------------------------------------------
# Composition: full validation pipeline
# ---------------------------------------------------------------------------


def validate_contents(
    contents: WheelContents, manifest: WheelManifest
) -> list[Violation]:
    """Run all validation rules against wheel contents.

    Returns an empty list if the wheel is valid.
    """
    violations: list[Violation] = []
    violations.extend(check_required_prefixes(contents, manifest.required_prefixes))
    violations.extend(check_no_forbidden_files(contents, manifest.forbidden_prefixes))
    return violations


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Validate a wheel file from the command line.

    Usage: python validate_wheel_contents.py <path-to-wheel>

    Returns 0 if valid, 1 if violations found, 2 if file error.
    """
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <wheel-file>", file=sys.stderr)
        return 2

    wheel_path = Path(sys.argv[1])

    try:
        contents = parse_wheel_contents(wheel_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except zipfile.BadZipFile as exc:
        print(f"ERROR: Not a valid wheel/ZIP file: {exc}", file=sys.stderr)
        return 2

    manifest = build_wheel_manifest()
    violations = validate_contents(contents, manifest)

    if not violations:
        print(
            f"PASS: Wheel {wheel_path.name} contains "
            f"{len(contents.file_paths)} files, all checks passed."
        )
        return 0

    print(f"FAIL: {len(violations)} violation(s) found in {wheel_path.name}:")
    for violation in violations:
        print(f"  [{violation.category.upper()}] {violation.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
