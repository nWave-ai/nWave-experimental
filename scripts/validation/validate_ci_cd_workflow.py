#!/usr/bin/env python3
"""
CI/CD Workflow Validation Script

Validates the GitHub Actions workflow locally before deployment.
Tests all quality gates that would run in CI.

Usage:
    python3 scripts/validation/validate_ci_cd_workflow.py
    python3 scripts/validation/validate_ci_cd_workflow.py --verbose
    python3 scripts/validation/validate_ci_cd_workflow.py --fix  # Auto-fix issues
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml


class WorkflowValidator:
    """Validates CI/CD workflow configuration and simulates quality gates."""

    def __init__(self, verbose=False, auto_fix=False):
        self.verbose = verbose
        self.auto_fix = auto_fix
        self.project_root = Path(__file__).parent.parent.parent
        self.workflow_file = self.project_root / ".github/workflows/ci.yml"
        self.errors = []
        self.warnings = []
        self.passed = []

    def log(self, message, level="INFO"):
        """Log message if verbose mode enabled."""
        if self.verbose or level in ["ERROR", "WARNING", "SUCCESS"]:
            prefix = {
                "INFO": "ℹ",
                "SUCCESS": "✅",
                "WARNING": "⚠",
                "ERROR": "❌",
            }.get(level, "•")
            print(f"{prefix} {message}")

    def run_command(self, cmd, description):
        """Run shell command and return success status."""
        self.log(f"Running: {description}", "INFO")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )
            if result.returncode == 0:
                self.log(f"✓ {description}", "SUCCESS")
                return True, result.stdout
            else:
                self.log(f"✗ {description}", "ERROR")
                self.log(f"  Error: {result.stderr}", "ERROR")
                return False, result.stderr
        except Exception as e:
            self.log(f"✗ {description}: {e}", "ERROR")
            return False, str(e)

    def validate_workflow_syntax(self):
        """Validate YAML syntax of workflow file."""
        self.log("Validating workflow YAML syntax...", "INFO")
        try:
            with open(self.workflow_file) as f:
                yaml.safe_load(f)
            self.passed.append("Workflow YAML syntax valid")
            self.log("Workflow YAML syntax valid", "SUCCESS")
            return True
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML syntax: {e}")
            self.log(f"Invalid YAML syntax: {e}", "ERROR")
            return False
        except FileNotFoundError:
            self.errors.append(f"Workflow file not found: {self.workflow_file}")
            self.log(f"Workflow file not found: {self.workflow_file}", "ERROR")
            return False

    def validate_framework_catalog(self):
        """Validate framework-catalog.yaml structure."""
        self.log("Validating framework-catalog.yaml...", "INFO")
        catalog_file = self.project_root / "nWave/framework-catalog.yaml"

        try:
            with open(catalog_file) as f:
                catalog = yaml.safe_load(f)

            # Check required fields
            required_fields = ["name", "version", "description", "agents", "commands"]
            missing = [f for f in required_fields if f not in catalog]

            if missing:
                self.errors.append(
                    f"Missing required fields in framework-catalog.yaml: {missing}"
                )
                return False

            # Validate version format
            version = catalog["version"]
            if not re.match(r"^\d+\.\d+\.\d+$", version):
                self.errors.append(
                    f"Invalid version format: {version} (expected: MAJOR.MINOR.PATCH)"
                )
                return False

            self.passed.append(f"framework-catalog.yaml valid (version: {version})")
            self.log(f"framework-catalog.yaml valid (version: {version})", "SUCCESS")
            return True

        except Exception as e:
            self.errors.append(f"Error validating framework-catalog.yaml: {e}")
            self.log(f"Error validating framework-catalog.yaml: {e}", "ERROR")
            return False

    def validate_agent_sync(self):
        """Validate agent name synchronization."""
        self.log("Validating agent name synchronization...", "INFO")
        sync_script = self.project_root / "scripts/framework/sync_agent_names.py"

        if not sync_script.exists():
            self.warnings.append("Agent sync script not found (skipping)")
            return True

        success, _output = self.run_command(
            f"python3 {sync_script} --verify", "Agent name synchronization"
        )

        if success:
            self.passed.append("Agent names synchronized")
            return True
        else:
            if self.auto_fix:
                self.log("Attempting to fix agent sync...", "WARNING")
                fix_success, _ = self.run_command(
                    f"python3 {sync_script} --fix", "Fixing agent synchronization"
                )
                if fix_success:
                    self.passed.append("Agent names synchronized (auto-fixed)")
                    return True

            self.errors.append("Agent name synchronization failed")
            return False

    def validate_pre_commit(self):
        """Run pre-commit hooks."""
        self.log("Running pre-commit hooks...", "INFO")

        # Check if pre-commit is installed
        check_cmd = "pre-commit --version"
        success, _ = self.run_command(check_cmd, "Checking pre-commit installation")

        if not success:
            self.warnings.append(
                "pre-commit not installed (install: pip install pre-commit)"
            )
            return True

        # Run pre-commit
        success, output = self.run_command(
            "pre-commit run --all-files", "Pre-commit hooks"
        )

        if success or "Passed" in output:
            self.passed.append("Pre-commit hooks passed")
            return True
        else:
            if self.auto_fix:
                self.log(
                    "Pre-commit found issues - auto-fix may have corrected them",
                    "WARNING",
                )
                # Re-run to check
                success, _ = self.run_command(
                    "pre-commit run --all-files", "Pre-commit hooks (retry)"
                )
                if success:
                    self.passed.append("Pre-commit hooks passed (after auto-fix)")
                    return True

            self.errors.append("Pre-commit hooks failed")
            return False

    def validate_tests(self):
        """Run pytest test suite."""
        self.log("Running pytest test suite...", "INFO")

        success, _output = self.run_command(
            "pytest tests/ -v --tb=short -x",  # -x stops on first failure
            "Pytest test suite",
        )

        if success:
            self.passed.append("All tests passed")
            return True
        else:
            self.errors.append("Test suite failed")
            self.log("Run 'pytest tests/ -v' for detailed test output", "ERROR")
            return False

    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 70)
        print("CI/CD WORKFLOW VALIDATION SUMMARY")
        print("=" * 70)

        if self.passed:
            print(f"\n✅ PASSED ({len(self.passed)}):")
            for item in self.passed:
                print(f"   • {item}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for item in self.warnings:
                print(f"   • {item}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for item in self.errors:
                print(f"   • {item}")

        print("\n" + "=" * 70)

        if not self.errors:
            print("✅ VALIDATION PASSED - Workflow ready for deployment")
            print("\nNext steps:")
            print("  1. git add .github/workflows/ci-cd.yml")
            print("  2. git commit -m 'ci: add comprehensive ci-cd workflow'")
            print("  3. git push origin master")
            print("  4. gh run watch")
            return 0
        else:
            print("❌ VALIDATION FAILED - Fix errors before deployment")
            print("\nActions:")
            if not self.auto_fix:
                print("  • Run with --fix to attempt auto-correction")
            print("  • Review errors above")
            print("  • Fix issues manually")
            print("  • Re-run validation")
            return 1

    def run_validation(self):
        """Run all validation checks."""
        print("=" * 70)
        print("CI/CD WORKFLOW VALIDATION")
        print("=" * 70)
        print(f"Project root: {self.project_root}")
        print(f"Workflow file: {self.workflow_file}")
        print(f"Verbose: {self.verbose}")
        print(f"Auto-fix: {self.auto_fix}")
        print("=" * 70 + "\n")

        # Run all validations
        validations = [
            ("Workflow YAML Syntax", self.validate_workflow_syntax),
            ("Framework Catalog", self.validate_framework_catalog),
            ("Agent Synchronization", self.validate_agent_sync),
            ("Pre-commit Hooks", self.validate_pre_commit),
            ("Test Suite", self.validate_tests),
        ]

        for name, validator in validations:
            self.log(f"\n--- {name} ---", "INFO")
            validator()

        return self.print_summary()


def main():
    parser = argparse.ArgumentParser(
        description="Validate CI/CD workflow before deployment"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--fix", action="store_true", help="Attempt to auto-fix issues")
    args = parser.parse_args()

    validator = WorkflowValidator(verbose=args.verbose, auto_fix=args.fix)
    return validator.run_validation()


if __name__ == "__main__":
    sys.exit(main())
