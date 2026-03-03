#!/usr/bin/env python3
"""Pre-push Test Validation Hook: Integration, E2E & Build Acceptance Tests

Runs tests that are excluded from the pre-commit hook:
  - integration/ and e2e/ directories (cross-component paths)
  - build/acceptance/ (slow plugin assembly tests)
"""

import os
import re
import subprocess
import sys
from pathlib import Path


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def clear_git_environment():
    """Clear git environment variables that pre-commit sets."""
    git_vars = [
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_AUTHOR_DATE",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
    ]
    for var in git_vars:
        os.environ.pop(var, None)


def collect_test_dirs():
    """Find all integration/, e2e/, and build/acceptance/ directories under tests/."""
    tests_root = Path("tests")
    if not tests_root.is_dir():
        return []

    dirs = []
    for pattern in ("**/integration", "**/e2e"):
        for d in sorted(tests_root.glob(pattern)):
            if d.is_dir():
                dirs.append(str(d))

    # Build acceptance tests (slow plugin assembly, moved from pre-commit)
    build_acceptance = tests_root / "build" / "acceptance"
    if build_acceptance.is_dir():
        dirs.append(str(build_acceptance))

    return dirs


def has_xdist() -> bool:
    """Check if pytest-xdist is available."""
    try:
        import importlib.util

        return importlib.util.find_spec("xdist") is not None
    except Exception:
        return False


def main():
    """Run integration, e2e, and build acceptance test validation."""
    clear_git_environment()

    test_dirs = collect_test_dirs()
    if not test_dirs:
        print(f"{YELLOW}No slow test directories found, skipping{NC}")
        return 0

    print(f"{BLUE}Running pre-push tests ({len(test_dirs)} directories)...{NC}")

    # Determine pytest command
    use_pipenv = False
    try:
        subprocess.run(
            ["pipenv", "run", "python3", "-m", "pytest", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        use_pipenv = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(
                ["python3", "-m", "pytest", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"{YELLOW}Warning: pytest not available, skipping tests{NC}")
            return 0

    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + ":" + env.get("PYTHONPATH", "")

    base_args = [*test_dirs, "-x", "--tb=short"]

    # Parallel execution with pytest-xdist (if available)
    # --dist loadfile keeps tests from the same file on one worker
    if has_xdist():
        base_args.extend(["-n", "auto", "--dist", "loadfile"])
    else:
        base_args.append("-v")

    cmd = (
        ["pipenv", "run", "python3", "-m", "pytest", *base_args]
        if use_pipenv
        else ["python3", "-m", "pytest", *base_args]
    )

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        test_output = result.stdout + result.stderr
        test_exit_code = result.returncode
    except Exception as e:
        print(f"{RED}Error running pre-push tests: {e}{NC}")
        return 1

    passed_match = re.search(r"(\d+) passed", test_output)
    failed_match = re.search(r"(\d+) failed", test_output)

    total_tests = int(passed_match.group(1)) if passed_match else 0
    failed_tests = int(failed_match.group(1)) if failed_match else 0

    if test_exit_code == 0:
        print(f"{GREEN}Pre-push tests passing ({total_tests}/{total_tests}){NC}")
        return 0
    elif test_exit_code == 5:
        print(f"{YELLOW}No pre-push tests collected, skipping{NC}")
        return 0
    else:
        print()
        print(f"{RED}PUSH BLOCKED: Pre-push tests failed{NC}")
        print()
        print(f"{RED}Full pytest output:{NC}")
        print(test_output)
        print()

        print(f"{RED}Failed tests:{NC}")
        for line in test_output.split("\n"):
            if "FAILED" in line or "ERROR" in line:
                print(f"  {line}")

        print()
        if failed_tests > 0:
            passing_tests = total_tests - failed_tests
            print(
                f"{RED}Test Results: {passing_tests}/{total_tests} passing"
                f" ({failed_tests} failed){NC}"
            )
        print()
        print(f"{YELLOW}Fix failing tests before pushing.{NC}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
