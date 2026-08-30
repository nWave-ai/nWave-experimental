#!/usr/bin/env python3
"""
Local CI/CD Validation Script

Runs the same validation checks as GitHub Actions CI/CD pipelines locally.
This allows catching issues before pushing to remote.

Since 2026-08-23 this is also the ON-DEMAND stand-in for the CI test run:
`ci.yml` no longer fires on a push to the trunk (GitHub Actions budget), so the
tiers are run here, deliberately, before a deliberate push.

Usage:
    python scripts/local_ci.py [--verbose] [--fast] [--python-quality]
    python scripts/local_ci.py --tier unit            # one tier
    python scripts/local_ci.py --tier all             # every tier, SERIALLY
    python scripts/local_ci.py --changed              # working tree vs HEAD
    python scripts/local_ci.py --changed origin/master

Options:
    --verbose    Show detailed output
    --fast       Skip slower checks (build validation)
    --python-quality
                 Run only the shared read-only Ruff lint and format contract
    --tier TIER  unit|integration|acceptance|e2e|all -- repeatable, serial,
                 each tier preceded by a MemAvailable gate (shared box)
    --changed [REF]
                 Only the tests covering files changed vs REF (default: the
                 working tree vs HEAD), untracked files included
    --help       Show this help message

Exit codes: 0 green, 1 red, 2 INDETERMINATE (a run the box killed, or one that
could not be decided -- never reported as a failure).
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    # Fallback if colorama not available
    HAS_COLOR = False

    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = ""

    class Style:
        RESET_ALL = BRIGHT = ""


# --------------------------------------------------------------------------
# On-demand local test tiers -- the Actions-free replacement for per-push CI
# --------------------------------------------------------------------------
# WHY HERE AND NOT IN A NEW SCRIPT (GDP-10, parsimony): this file already IS
# "run locally what CI would run" (`poe validate`). What it could not do was
# run the test tiers BY NAME, one at a time, under the shared-box memory
# discipline. Since 2026-08-23 `ci.yml` no longer fires on a push to the trunk
# (deliberate-dispatch triggers -- GitHub Actions budget), so that on-demand
# local run is the primary safety net and is completed here rather than added
# as a second, competing entry point.
#
# The tier -> targets mapping is NOT re-declared here: it delegates to the
# existing `[tool.poe.tasks]` entries, which remain the single source of truth
# for what a tier contains. A copy of those paths would drift.
TIER_POE_TASKS = {
    "unit": "test-unit",
    "integration": "test-integration",
    "acceptance": "test-acceptance",
    "e2e": "test-e2e",
}
# Ordered cheapest-first: a red unit tier stops the run before the expensive
# tiers are paid for.
TIER_ORDER = ("unit", "integration", "acceptance", "e2e")

# Shared-box floor. Same figure enforced by scripts/measure_serial_suite.py
# (`MIN_MEM_AVAILABLE_MIB`), same box, same reason: below it earlyoom starts
# killing processes, and it has corrupted `.git` here before. MemAvailable --
# never MemFree, never load.
MIN_MEM_AVAILABLE_MIB = 2000

# Bound every spawn (execution-perimeter invariant): a hang must not look like
# a slow run. 90 minutes covers the slowest tier (e2e) on this box.
TIER_TIMEOUT_SECONDS = 5400

# Distinct process exit codes, because "could not decide" is not "failed".
EXIT_GREEN = 0
EXIT_RED = 1
EXIT_INDETERMINATE = 2


def mem_available_mib() -> int | None:
    """MemAvailable in MiB, or None where /proc/meminfo does not exist."""
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    try:
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


class LocalCIValidator:
    """Local CI/CD validation orchestrator."""

    def __init__(self, verbose: bool = False, fast_mode: bool = False):
        self.verbose = verbose
        self.fast_mode = fast_mode
        self.project_root = Path(__file__).parent.parent
        self.tests_passed = 0
        self.tests_failed = 0

    def print_header(self, text: str) -> None:
        """Print a section header."""
        separator = "━" * 50
        print(f"\n{Fore.BLUE}{separator}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{text}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{separator}{Style.RESET_ALL}")

    def print_success(self, text: str) -> None:
        """Print a success message."""
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} {text}")

    def print_error(self, text: str) -> None:
        """Print an error message."""
        print(f"{Fore.RED}✗{Style.RESET_ALL} {text}")

    def print_warning(self, text: str) -> None:
        """Print a warning message."""
        print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} {text}")

    def print_info(self, text: str) -> None:
        """Print an info message."""
        if self.verbose:
            print(f"{Fore.CYAN}ℹ{Style.RESET_ALL} {text}")

    def run_command(
        self, command: list[str], check_name: str, cwd: Path | None = None
    ) -> bool:
        """
        Run a command and track success/failure.

        Args:
            command: Command to run as list of strings
            check_name: Human-readable name for the check
            cwd: Working directory (defaults to project root)

        Returns:
            True if command succeeded, False otherwise
        """
        if cwd is None:
            cwd = self.project_root

        self.print_info(f"Running: {' '.join(command)}")

        try:
            if self.verbose:
                # In verbose mode, show output directly
                subprocess.run(command, cwd=cwd, check=True, text=True)
            else:
                # In non-verbose mode, capture output
                subprocess.run(
                    command,
                    cwd=cwd,
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )

            self.print_success(check_name)
            self.tests_passed += 1
            return True

        except subprocess.CalledProcessError as e:
            self.print_error(check_name)
            if not self.verbose and hasattr(e, "output") and e.output:
                # In non-verbose mode, show output on error
                print(e.output)
            self.tests_failed += 1
            return False
        except FileNotFoundError:
            self.print_warning(f"{check_name} - command not found")
            return False

    def validate_yaml(self) -> None:
        """Validate YAML files using our validation script."""
        self.print_header("1. YAML File Validation")

        validator_script = (
            self.project_root / "scripts/validation/validate_yaml_files.py"
        )
        if validator_script.exists():
            self.run_command(
                [sys.executable, str(validator_script)], "YAML syntax validation"
            )
        else:
            self.print_warning("YAML validator script not found")

    def validate_uv_dependencies(self) -> None:
        """Validate uv dependencies match CI workflow requirements."""
        self.print_header("2. uv Dependency Validation")

        pyproject = self.project_root / "pyproject.toml"
        uv_lock = self.project_root / "uv.lock"

        if not pyproject.exists():
            self.print_error("pyproject.toml missing - uv sync will fail")
            self.tests_failed += 1
            return

        self.print_success("pyproject.toml exists")

        if not uv_lock.exists():
            self.print_warning("uv.lock missing - run: uv lock")
            # Generate lock file
            try:
                subprocess.run(
                    ["uv", "lock"],
                    cwd=self.project_root,
                    check=True,
                    capture_output=not self.verbose,
                    text=True,
                )
                self.print_success("uv.lock generated")
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                self.print_error(f"Failed to generate uv.lock: {e}")
                self.tests_failed += 1
                return

        self.print_success("uv.lock exists")

        # Validate the lockfile is in sync, then install (mirrors CI exactly)
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            self.run_command(
                ["uv", "lock", "--check"],
                "uv.lock in sync with pyproject.toml",
            )
            self.run_command(
                ["uv", "sync"],
                "uv sync (dependency installation)",
            )
        except FileNotFoundError:
            self.print_warning(
                "uv not available - install from https://docs.astral.sh/uv/"
            )

    def run_python_tests(self) -> None:
        """Run Python test suite."""
        self.print_header("3. Python Test Suite")

        # Use uv run poe test (mirrors CI exactly)
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            self.run_command(["uv", "run", "poe", "test"], "Python tests (pytest)")
        except FileNotFoundError:
            # Fall back to direct pytest if uv not available
            self.run_command(
                [sys.executable, "-m", "pytest", "tests/", "-v"],
                "Python tests (pytest)",
            )

    def validate_build(self) -> None:
        """Validate the build process."""
        if self.fast_mode:
            self.print_info("Skipping build (fast mode)")
            return

        self.print_header("4. Build Process Validation")

        # Use uv run poe build (mirrors CI exactly)
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            self.run_command(["uv", "run", "poe", "build"], "Build process")
        except FileNotFoundError:
            # Fall back to direct Python if uv not available
            build_script = self.project_root / "scripts" / "build_dist.py"
            if build_script.exists():
                self.run_command([sys.executable, str(build_script)], "Build process")
            else:
                self.print_warning("Build script not found")

    def validate_shell_scripts(self) -> None:
        """Validate shell scripts."""
        self.print_header("5. Shell Script Validation")

        scripts_dir = self.project_root / "scripts"
        shell_scripts = list(scripts_dir.glob("*.sh"))

        if not shell_scripts:
            self.print_info("No shell scripts found in scripts/")
            return

        shell_errors = 0

        # Syntax validation
        for script in shell_scripts:
            try:
                subprocess.run(
                    ["bash", "-n", str(script)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.print_success(f"Shell syntax: {script.name}")
            except subprocess.CalledProcessError:
                self.print_error(f"Shell syntax: {script.name}")
                shell_errors += 1

        # Shellcheck linting (non-blocking if not available)
        try:
            result = subprocess.run(
                ["shellcheck", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                self.print_info("Running shellcheck analysis...")
                all_scripts = list(scripts_dir.rglob("*.sh"))
                try:
                    subprocess.run(
                        ["shellcheck", "-x"] + [str(s) for s in all_scripts],
                        check=True,
                        capture_output=not self.verbose,
                        text=True,
                    )
                    self.print_success("Shellcheck linting passed")
                except subprocess.CalledProcessError:
                    self.print_warning("Shellcheck found issues (non-blocking)")
            else:
                self.print_warning(
                    "Shellcheck not available - install for additional validation"
                )
        except FileNotFoundError:
            self.print_warning(
                "Shellcheck not available - install for additional validation"
            )

        if shell_errors == 0:
            self.tests_passed += 1
        else:
            self.tests_failed += 1

    @staticmethod
    def _ruff_prefix() -> list[str] | None:
        """Resolve Ruff without changing the commands checked by every consumer."""
        if shutil.which("ruff"):
            return ["ruff"]
        if shutil.which("uv"):
            return ["uv", "run", "--frozen", "ruff"]
        return None

    def validate_python_quality(self) -> None:
        """Run the read-only Ruff contract shared by local hooks and CI."""
        self.print_header("6. Python Quality (Ruff)")
        prefix = self._ruff_prefix()
        if prefix is None:
            self.print_error(
                "Ruff is unavailable; install project dependencies with uv sync"
            )
            self.tests_failed += 1
            return
        scope = ["src/", "scripts/", "tests/"]
        self.run_command(
            [*prefix, "check", *scope, "--exit-non-zero-on-fix"],
            "Ruff linting passed",
        )
        self.run_command(
            [*prefix, "format", "--check", "--diff", *scope],
            "Ruff formatting check passed",
        )

    def validate_security(self) -> None:
        """Run basic security validation."""
        self.print_header("8. Security Validation")

        # Simple grep-based check for hardcoded credentials
        scripts_dir = self.project_root / "scripts"
        patterns = [
            r"password\s*=\s*['\"][^'\"]+['\"]",
            r"secret\s*=\s*['\"][^'\"]+['\"]",
            r"token\s*=\s*['\"][^'\"]+['\"]",
        ]

        found_issues = False
        for script_file in scripts_dir.rglob("*.sh"):
            content = script_file.read_text()
            for pattern in patterns:
                import re

                if re.search(pattern, content, re.IGNORECASE):
                    # Exclude examples, tests, comments
                    if not re.search(
                        r"(example|test|comment|TODO)", content, re.IGNORECASE
                    ):
                        self.print_error(
                            f"Potential credential in {script_file.relative_to(self.project_root)}"
                        )
                        found_issues = True

        if not found_issues:
            self.print_success("No hardcoded credentials detected")
            self.tests_passed += 1
        else:
            self.print_error("Potential hardcoded credentials detected")
            self.tests_failed += 1

    def validate_nwave_framework(self) -> None:
        """Validate nWave framework structure."""
        self.print_header("9. nWave Framework Validation")

        # Check agent definitions
        agents_dir = self.project_root / "nWave" / "agents"
        if agents_dir.exists():
            agent_count = len(list(agents_dir.glob("*.md")))
            if agent_count >= 10:
                self.print_success(f"Agent definitions: {agent_count} found")
                self.tests_passed += 1
            else:
                self.print_warning(
                    f"Agent definitions: only {agent_count} found (expected >= 10)"
                )
                self.tests_failed += 1
        else:
            self.print_info("nWave agents directory not found")

        # Check command/task definitions
        tasks_dir = self.project_root / "nWave" / "tasks"
        if tasks_dir.exists():
            command_count = len(list(tasks_dir.rglob("*.md")))
            self.print_success(f"Command definitions: {command_count} found")
            self.tests_passed += 1
        else:
            self.print_info("nWave tasks directory not found")

    def validate_documentation(self) -> None:
        """Validate required documentation exists."""
        self.print_header("10. Documentation Validation")

        required_docs = [
            "README.md",
            "docs/guides/installation-guide/README.md",
        ]

        doc_errors = 0
        for doc_path in required_docs:
            doc_file = self.project_root / doc_path
            if doc_file.exists():
                self.print_success(f"Documentation: {doc_path}")
            else:
                self.print_warning(f"Missing documentation: {doc_path}")
                doc_errors += 1

        if doc_errors == 0:
            self.tests_passed += 1
        else:
            self.tests_failed += 1

    # ----------------------------------------------------------------
    # On-demand test tiers (Actions-free local CI)
    # ----------------------------------------------------------------

    def _memory_gate(self, label: str) -> bool:
        """Refuse to start `label` when the shared box is too tight.

        Returns True when it is safe to proceed. A box we cannot measure is
        announced LOUD and allowed through: /proc/meminfo is a Linux fact, and
        a non-Linux dev box has no earlyoom to protect against.
        """
        available = mem_available_mib()
        if available is None:
            self.print_warning(
                f"{label}: MemAvailable unreadable (no /proc/meminfo) -- "
                "proceeding WITHOUT the shared-box guard."
            )
            return True
        if available < MIN_MEM_AVAILABLE_MIB:
            self.print_error(f"{label}: REFUSED -- box too tight.")
            print(
                f"  WHAT  MemAvailable={available} MiB < {MIN_MEM_AVAILABLE_MIB} MiB."
            )
            print("  WHY   Below this floor earlyoom kills processes on this box; it")
            print("        has corrupted .git mid-operation before. A run started here")
            print("        produces an INDETERMINATE result, never a trustworthy red.")
            print("  HOW   Close the other heavy process (another pytest, a browser),")
            print("        then re-run the same command. Nothing was executed.")
            return False
        self.print_info(f"{label}: MemAvailable={available} MiB -- gate open.")
        return True

    def _run_bounded(self, command: list[str], label: str) -> str:
        """Run one bounded, serial child. Returns green | red | indeterminate.

        An OOM kill arrives as a NEGATIVE return code (-signal) or as 137 from
        a shell layer. That is the box speaking, not the test suite: it is
        reported as INDETERMINATE and never counted as a failure.
        """
        self.print_info(f"Running: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                check=False,
                stdin=subprocess.DEVNULL,
                timeout=TIER_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            self.print_warning(f"{label} - command not found")
            return "indeterminate"
        except subprocess.TimeoutExpired:
            self.print_warning(
                f"{label}: INDETERMINATE -- exceeded its {TIER_TIMEOUT_SECONDS}s bound."
            )
            return "indeterminate"

        code = result.returncode
        if code in (0, 5):  # 5 = pytest collected nothing; not a failure
            self.print_success(label)
            self.tests_passed += 1
            return "green"
        if code < 0 or code == 137:
            signal_name = f"signal {-code}" if code < 0 else "SIGKILL (137)"
            self.print_warning(f"{label}: INDETERMINATE -- killed by {signal_name}.")
            print("  WHAT  The run did not finish; it was terminated by the kernel or")
            print("        by earlyoom. No verdict about the code was produced.")
            print("  WHY   An OOM-killed run is INDETERMINATE, never a red. Reporting")
            print(
                "        it as a failure would fabricate a defect that was never seen."
            )
            print("  HOW   Free memory on the box and re-run the same tier alone.")
            return "indeterminate"
        self.print_error(f"{label} (exit {code})")
        self.tests_failed += 1
        return "red"

    def run_test_tiers(self, tiers: list[str]) -> str:
        """Run the named tiers SERIALLY, one at a time, memory-gated.

        Never two tiers at once: the box is shared, and a MemAvailable dip
        under earlyoom's threshold kills work outside this process.
        """
        self.print_header(f"Local test tiers (serial): {', '.join(tiers)}")
        verdict = "green"
        for tier in tiers:
            label = f"Tier {tier}"
            if not self._memory_gate(label):
                return "indeterminate"
            outcome = self._run_bounded(
                ["uv", "run", "poe", TIER_POE_TASKS[tier]], label
            )
            if outcome == "indeterminate":
                return "indeterminate"
            if outcome == "red":
                verdict = "red"
                break  # cheapest-first: stop paying for the later tiers
        return verdict

    def _changed_paths(self, ref: str) -> list[str] | None:
        """Paths differing from `ref`, plus untracked files. None = cannot tell.

        Untracked files are in no diff -- omitting them silently narrows the
        selection, so they are queried separately. `git` is optional on this
        project (pure-Python runtime invariant); its absence degrades LOUD.
        """
        collected: list[str] = []
        for args in (
            ["git", "diff", "--name-only", ref],
            ["git", "ls-files", "--others", "--exclude-standard"],
        ):
            try:
                proc = subprocess.run(
                    args,
                    cwd=self.project_root,
                    check=False,
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                    timeout=60,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self.print_error("--changed needs `git` on PATH and it did not answer.")
                print("  WHAT  Cannot compute the changed-file set.")
                print("  WHY   Reporting 'no changes' here would silently run nothing")
                print("        and look green. INDETERMINATE instead of silent-wrong.")
                print("  HOW   Run a whole tier instead: --tier unit (or --tier all).")
                return None
            if proc.returncode != 0:
                self.print_error(f"git refused: {' '.join(args)}")
                print((proc.stderr or "").strip())
                return None
            collected.extend(p for p in proc.stdout.splitlines() if p.strip())
        return sorted(set(collected))

    def run_changed_tests(self, ref: str) -> str:
        """Run only the tests covering the files changed since `ref`.

        Selection is NOT re-implemented: it reuses `select()` from
        scripts/hooks/pytest_touched_files.py, the same mapping the pre-commit
        touched-file gate uses, so local and commit-time scoping cannot drift.
        """
        self.print_header(f"Local tests scoped to files changed vs {ref}")
        changed = self._changed_paths(ref)
        if changed is None:
            return "indeterminate"
        if not changed:
            self.print_success(f"No file differs from {ref}; nothing to run.")
            return "green"

        sys.path.insert(0, str(self.project_root / "scripts" / "hooks"))
        try:
            from pytest_touched_files import select
        except ImportError as exc:
            self.print_error(f"cannot load the touched-file selector: {exc}")
            return "indeterminate"

        runnable, deferred, uncovered = select(changed, self.project_root)
        for entry in uncovered:
            self.print_warning(f"UNCOVERED (no test maps to it): {entry}")
        if deferred:
            self.print_warning(
                f"Deferred ({len(deferred)} file(s)): Docker/multi-language tiers. "
                "Run them with --tier e2e when you want them."
            )
        if not runnable:
            self.print_success("No test file is impacted by these changes.")
            return "green"

        self.print_info(f"{len(runnable)} test file(s) impacted.")
        if not self._memory_gate("Changed-file run"):
            return "indeterminate"
        return self._run_bounded(
            ["uv", "run", "python", "-m", "pytest", *runnable, "--tb=short", "-q"],
            f"Changed-file tests ({len(runnable)} file(s))",
        )

    @staticmethod
    def print_tier_verdict(verdict: str) -> int:
        banner = {
            "green": (Fore.GREEN, "ALL SELECTED TESTS PASSED", EXIT_GREEN),
            "red": (Fore.RED, "TESTS FAILED", EXIT_RED),
            "indeterminate": (
                Fore.YELLOW,
                "INDETERMINATE -- no verdict was produced (this is NOT a red)",
                EXIT_INDETERMINATE,
            ),
        }[verdict]
        colour, text, code = banner
        print(f"\n{colour}{'-' * 50}{Style.RESET_ALL}")
        print(f"{colour}{text}{Style.RESET_ALL}")
        print(f"{colour}{'-' * 50}{Style.RESET_ALL}")
        return code

    def print_summary(self) -> None:
        """Print validation summary."""
        self.print_header("CI/CD Validation Results")

        if self.tests_failed == 0:
            print(f"{Fore.GREEN}{'━' * 50}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}✅ ALL CHECKS PASSED{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{'━' * 50}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}{'━' * 50}{Style.RESET_ALL}")
            print(f"{Fore.RED}❌ VALIDATION FAILED{Style.RESET_ALL}")
            print(f"{Fore.RED}{'━' * 50}{Style.RESET_ALL}")

        print(f"\n  Passed: {self.tests_passed}")
        print(f"  Failed: {self.tests_failed}")

        if self.tests_failed > 0:
            print(
                f"\n{Fore.YELLOW}⚠ Fix the above issues before pushing{Style.RESET_ALL}"
            )
            print(
                f"{Fore.YELLOW}⚠ CI/CD pipeline will fail with these errors{Style.RESET_ALL}"
            )
        else:
            print(f"\n{Fore.GREEN}✓ Your code is ready for CI/CD!{Style.RESET_ALL}")
            print(f"{Fore.GREEN}✓ Safe to push to remote repository{Style.RESET_ALL}")

    def run_all_validations(self) -> bool:
        """
        Run all validation checks.

        Returns:
            True if all validations passed, False otherwise
        """
        self.print_header("Local CI/CD Validation")
        print("Simulating GitHub Actions CI/CD pipeline locally")
        print(f"Project: {self.project_root}")

        # Run all validation phases
        self.validate_yaml()
        self.validate_uv_dependencies()
        self.run_python_tests()
        self.validate_build()
        self.validate_shell_scripts()
        self.validate_python_quality()
        self.validate_security()
        self.validate_nwave_framework()
        self.validate_documentation()

        # Print summary
        self.print_summary()

        return self.tests_failed == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Local CI/CD validation - mirrors GitHub Actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )
    parser.add_argument(
        "--fast",
        "-f",
        action="store_true",
        help="Skip slower checks (build validation)",
    )
    parser.add_argument(
        "--python-quality",
        action="store_true",
        help="Run only the shared read-only Ruff lint and format contract",
    )
    parser.add_argument(
        "--tier",
        action="append",
        choices=[*TIER_ORDER, "all"],
        metavar="TIER",
        help=(
            "Run a test tier by name (unit|integration|acceptance|e2e|all). "
            "Repeatable. Tiers run SERIALLY, one at a time, each preceded by a "
            "MemAvailable gate. This is the on-demand local stand-in for the CI "
            "run that no longer fires on every push."
        ),
    )
    parser.add_argument(
        "--changed",
        nargs="?",
        const="HEAD",
        metavar="REF",
        help=(
            "Run only the tests covering files changed vs REF (default HEAD, "
            "i.e. the working tree), untracked files included."
        ),
    )

    args = parser.parse_args()

    validator = LocalCIValidator(verbose=args.verbose, fast_mode=args.fast)

    if args.changed is not None:
        sys.exit(
            validator.print_tier_verdict(validator.run_changed_tests(args.changed))
        )

    if args.tier:
        tiers = (
            list(TIER_ORDER)
            if "all" in args.tier
            else [t for t in TIER_ORDER if t in set(args.tier)]
        )
        sys.exit(validator.print_tier_verdict(validator.run_test_tiers(tiers)))

    if args.python_quality:
        validator.validate_python_quality()
        validator.print_summary()
        success = validator.tests_failed == 0
    else:
        success = validator.run_all_validations()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
