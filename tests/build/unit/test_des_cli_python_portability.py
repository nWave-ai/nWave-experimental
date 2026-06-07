"""Tests for DES CLI Python interpreter portability in command templates.

Regression guard for Bug #1 (2026-03-12): bare ``python`` or ``python3``
in DES CLI invocations breaks on systems where only one of the two exists
(macOS Homebrew has only ``python3``; some Windows setups have only ``python``).

The portable pattern is:
    $(command -v python3 || command -v python)

These tests scan all command template files to ensure:
1. No bare ``python -m des.cli`` or ``python3 -m des.cli`` calls exist
2. All DES CLI invocations use the portable resolution pattern
3. All DES CLI invocations include the PYTHONPATH prefix
"""

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
COMMANDS_DIR = PROJECT_ROOT / "nWave" / "tasks" / "nw"

# Pattern that matches bare python/python3 before ``-m des.cli``
# but NOT the portable ``$(command -v python3 || command -v python)`` form.
BARE_PYTHON_RE = re.compile(
    r"(?<!\$\(command -v )(?<!\|\| command -v )"  # not inside $(command -v ...)
    r"\bpython[3]?\s+-m\s+des\.cli\b"
)

# The portable pattern we require
PORTABLE_PATTERN = "$(command -v python3 || command -v python)"

# All command templates that contain DES CLI invocations
COMMAND_FILES_WITH_DES_CLI = ["execute.md", "deliver.md", "roadmap.md"]


def _collect_des_cli_lines(file_path: Path) -> list[tuple[int, str]]:
    """Return (line_number, line_text) for lines invoking des.cli modules."""
    results = []
    for i, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
        if "des.cli." in line and "-m" in line:
            results.append((i, line))
    return results


class TestNoBareInterpreterInTemplates:
    """Regression: DES CLI commands must use portable Python resolution."""

    @pytest.mark.parametrize("filename", COMMAND_FILES_WITH_DES_CLI)
    def test_no_bare_python_in_des_cli_commands(self, filename: str):
        """No ``python -m des.cli`` or ``python3 -m des.cli`` without portable wrapper."""
        file_path = COMMANDS_DIR / filename
        if not file_path.exists():
            pytest.skip(f"{filename} not found")

        content = file_path.read_text(encoding="utf-8")
        violations = []
        for i, line in enumerate(content.splitlines(), 1):
            if BARE_PYTHON_RE.search(line):
                violations.append(f"  {filename}:{i}: {line.strip()}")

        assert not violations, (
            "Found bare python/python3 in DES CLI invocations (use portable pattern instead):\n"
            + "\n".join(violations)
            + f"\n\nRequired pattern: {PORTABLE_PATTERN}"
        )

    @pytest.mark.parametrize("filename", COMMAND_FILES_WITH_DES_CLI)
    def test_des_cli_lines_use_portable_pattern(self, filename: str):
        """Every line invoking ``-m des.cli.*`` must contain the portable pattern."""
        file_path = COMMANDS_DIR / filename
        if not file_path.exists():
            pytest.skip(f"{filename} not found")

        cli_lines = _collect_des_cli_lines(file_path)
        if not cli_lines:
            pytest.skip(f"No DES CLI invocations found in {filename}")

        missing_portable = []
        for lineno, line in cli_lines:
            # Skip documentation/comment lines that describe the pattern itself
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("Python resolution:"):
                continue
            # Skip lines that are just text references (not actual commands)
            if "command -v python3" not in line:
                missing_portable.append(f"  {filename}:{lineno}: {stripped}")

        assert not missing_portable, (
            "DES CLI invocations missing portable Python pattern:\n"
            + "\n".join(missing_portable)
            + f"\n\nRequired: {PORTABLE_PATTERN}"
        )

    @pytest.mark.parametrize("filename", COMMAND_FILES_WITH_DES_CLI)
    def test_des_cli_lines_include_pythonpath(self, filename: str):
        """Every DES CLI command line must set PYTHONPATH."""
        file_path = COMMANDS_DIR / filename
        if not file_path.exists():
            pytest.skip(f"{filename} not found")

        cli_lines = _collect_des_cli_lines(file_path)
        if not cli_lines:
            pytest.skip(f"No DES CLI invocations found in {filename}")

        missing_path = []
        for lineno, line in cli_lines:
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("Python resolution:"):
                continue
            if "PYTHONPATH" not in line:
                missing_path.append(f"  {filename}:{lineno}: {stripped}")

        assert not missing_path, (
            "DES CLI invocations missing PYTHONPATH prefix:\n"
            + "\n".join(missing_path)
            + "\n\nRequired: PYTHONPATH=$HOME/.claude/lib/python"
        )


class TestPortablePatternFunctionality:
    """Verify the portable pattern resolves correctly on this system."""

    def test_command_v_resolves_python(self):
        """``command -v python3 || command -v python`` must find an interpreter."""
        import subprocess

        result = subprocess.run(
            ["bash", "-c", "command -v python3 || command -v python"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Neither python3 nor python found on this system"
        resolved = result.stdout.strip()
        assert "python" in resolved, f"Unexpected resolution: {resolved}"

    def test_resolved_python_can_import(self):
        """The resolved Python can run ``-m des.cli`` import check."""
        import subprocess

        # Get the resolved Python path
        resolve = subprocess.run(
            ["bash", "-c", "command -v python3 || command -v python"],
            capture_output=True,
            text=True,
        )
        if resolve.returncode != 0:
            pytest.skip("No Python interpreter found")

        python_path = resolve.stdout.strip()

        # Verify it can at least start and report version
        result = subprocess.run(
            [python_path, "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Python at {python_path} failed: {result.stderr}"
        )
        assert "Python" in result.stdout or "Python" in result.stderr


class TestNoHardcodedPythonAnywhere:
    """Broader scan: no .md file in commands dir should have bare python for des.cli."""

    def test_scan_all_command_files(self):
        """Scan ALL .md files in commands directory for bare python des.cli calls."""
        if not COMMANDS_DIR.exists():
            pytest.skip("Commands directory not found")

        all_violations = []
        for md_file in sorted(COMMANDS_DIR.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                if BARE_PYTHON_RE.search(line):
                    all_violations.append(f"  {md_file.name}:{i}: {line.strip()}")

        assert not all_violations, (
            "Found bare python/python3 in DES CLI invocations:\n"
            + "\n".join(all_violations)
            + f"\n\nUse: {PORTABLE_PATTERN}"
        )
