#!/usr/bin/env python3
"""
nWave-TDD-PHASE-VALIDATION
Pre-commit hook to enforce TDD phase completeness.

Cross-platform: Works on Windows, Mac, and Linux.
No external dependencies beyond Python standard library.

Installed by /nw:develop command.

Exit codes:
    0 - All validations passed
    1 - Validation failures found (commit blocked)
    2 - Configuration/runtime error
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import Dict, List, Tuple, Any


# Required TDD phases - support v1.0 (14 phases), v2.0 (7 phases), and v4.0 (5 phases)
REQUIRED_PHASES_V1 = [
    "PREPARE",
    "RED_ACCEPTANCE",
    "RED_UNIT",
    "GREEN_UNIT",
    "CHECK_ACCEPTANCE",
    "GREEN_ACCEPTANCE",
    "REVIEW",
    "REFACTOR_L1",
    "REFACTOR_L2",
    "REFACTOR_L3",
    "REFACTOR_L4",
    "POST_REFACTOR_REVIEW",
    "FINAL_VALIDATE",
    "COMMIT",
]

REQUIRED_PHASES_V2 = [
    "PREPARE",
    "RED_ACCEPTANCE",
    "RED_UNIT",
    "GREEN",
    "REVIEW",
    "REFACTOR_CONTINUOUS",
    "COMMIT",
]

REQUIRED_PHASES_V4 = [
    "PREPARE",
    "RED_ACCEPTANCE",
    "RED_UNIT",
    "GREEN",
    "COMMIT",
]

# Default to v1.0 for backward compatibility
REQUIRED_PHASES = REQUIRED_PHASES_V1

# Valid prefixes for SKIPPED phases that allow commit
VALID_SKIP_PREFIXES = [
    "BLOCKED_BY_DEPENDENCY:",
    "NOT_APPLICABLE:",
    "APPROVED_SKIP:",
    "CHECKPOINT_PENDING:",  # NEW: For TDD checkpoint commits
]

# Prefixes that indicate incomplete work - blocks commit
BLOCKS_COMMIT_PREFIXES = [
    "DEFERRED:",
]

# TDD Checkpoint Strategy:
# CHECKPOINT_PENDING allows intermediate commits during TDD cycle:
# - GREEN checkpoint (phases 0-5 complete, 6-13 pending)
# - REVIEW checkpoint (phases 0-6 complete, 7-13 pending)
# - REFACTOR checkpoint (phases 0-10 complete, 11-13 pending)
# - FINAL checkpoint (all 14 phases complete)

# Bypass logging configuration
BYPASS_LOG_FILE = ".git/nwave-bypass.log"
VALIDATION_MARKER_FILE = ".git/nwave-validation-marker"


def get_git_info() -> Dict[str, str]:
    """Get current git user and branch information."""
    info = {"user": "unknown", "branch": "unknown", "email": "unknown"}

    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["user"] = result.stdout.strip() or "unknown"

        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["email"] = result.stdout.strip() or "unknown"

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip() or "unknown"
    except Exception:
        pass

    return info


def get_staged_step_files() -> List[str]:
    """Get list of step files staged for commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        files = result.stdout.strip().split("\n")

        # Filter for step files (pattern: steps/XX-XX.json or similar patterns)
        step_patterns = [
            re.compile(r"steps/\d+-\d+\.json$"),
            re.compile(r"steps/step-\d+-\d+\.json$"),
            re.compile(r"docs/.*/steps/\d+-\d+\.json$"),
        ]

        step_files = []
        for f in files:
            if f and any(pattern.search(f) for pattern in step_patterns):
                step_files.append(f)

        return step_files
    except subprocess.CalledProcessError:
        return []
    except subprocess.TimeoutExpired:
        print("Warning: git command timed out", file=sys.stderr)
        return []


def detect_schema_version(data: Dict[str, Any]) -> str:
    """
    Detect schema version from step file data.

    Returns:
        "4.0" if v4.0 schema detected, "2.0" if v2.0, "1.0" for backward compatibility default
    """
    # Check root level
    version = data.get("schema_version", "")

    # Check nested in tdd_cycle as fallback
    if not version:
        version = data.get("tdd_cycle", {}).get("schema_version", "")

    if version in ("4.0", "4.0.0"):
        return "4.0"
    if version in ("3.0", "3.0.0", "2.0", "2.0.0"):
        return "2.0"

    # Default to v1.0 for backward compatibility
    return "1.0"


def validate_skipped_phase(entry: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate a SKIPPED phase has proper blocked_by reason.

    Returns:
        Tuple of (is_valid, message)
    """
    blocked_by = entry.get("blocked_by", "")

    if not blocked_by:
        return False, "SKIPPED without blocked_by reason"

    # Check if it's a valid skip prefix that allows commit
    if any(blocked_by.startswith(p) for p in VALID_SKIP_PREFIXES):
        return True, "OK"

    # Check if it's a DEFERRED prefix that blocks commit
    if any(blocked_by.startswith(p) for p in BLOCKS_COMMIT_PREFIXES):
        return False, f"DEFERRED phases block commit: {blocked_by}"

    # Unknown prefix - not valid
    valid_examples = ", ".join(VALID_SKIP_PREFIXES + BLOCKS_COMMIT_PREFIXES)
    return False, f"Invalid blocked_by format. Must start with one of: {valid_examples}"


def validate_step_file(file_path: str) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Validate a step file has all TDD phases properly executed.

    Returns:
        Tuple of (is_valid, list_of_issues, schema_version)
    """
    issues: List[Dict[str, Any]] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return (
            False,
            [{"phase": "N/A", "status": "ERROR", "issue": f"Invalid JSON: {e}"}],
            "1.0",
        )
    except FileNotFoundError:
        return (
            False,
            [{"phase": "N/A", "status": "ERROR", "issue": "File not found"}],
            "1.0",
        )
    except Exception as e:
        return (
            False,
            [{"phase": "N/A", "status": "ERROR", "issue": f"Cannot read file: {e}"}],
            "1.0",
        )

    # Detect schema version (v1.0 = 14 phases, v2.0 = 7 phases, v4.0 = 5 phases)
    schema_version = detect_schema_version(data)
    if schema_version == "4.0":
        required_phases = REQUIRED_PHASES_V4
    elif schema_version == "2.0":
        required_phases = REQUIRED_PHASES_V2
    else:
        required_phases = REQUIRED_PHASES_V1

    # REJECT OLD/WRONG FORMAT PATTERNS
    if "step_id" in data:
        return (
            False,
            [
                {
                    "phase": "N/A",
                    "status": "WRONG_FORMAT",
                    "issue": "Found 'step_id' - use 'task_id'. This is an obsolete format.",
                }
            ],
            schema_version,
        )
    if "phase_id" in data:
        expected_phases = len(required_phases)
        return (
            False,
            [
                {
                    "phase": "N/A",
                    "status": "WRONG_FORMAT",
                    "issue": f"Found 'phase_id' - this field should not exist. Each step has ALL {expected_phases} phases (schema v{schema_version}).",
                }
            ],
            schema_version,
        )
    if "tdd_phase" in data and "tdd_cycle" not in data:
        return (
            False,
            [
                {
                    "phase": "N/A",
                    "status": "WRONG_FORMAT",
                    "issue": "Found 'tdd_phase' at top level. Phases must be in tdd_cycle.phase_execution_log.",
                }
            ],
            schema_version,
        )

    # Get phase execution log
    phase_log = data.get("tdd_cycle", {}).get("phase_execution_log", [])

    if not phase_log:
        # Check old location for backwards compatibility
        phase_log = (
            data.get("tdd_cycle", {})
            .get("tdd_phase_tracking", {})
            .get("phase_execution_log", [])
        )

    if not phase_log:
        return (
            False,
            [
                {
                    "phase": "N/A",
                    "status": "MISSING",
                    "issue": "No phase_execution_log found - file may need migration",
                }
            ],
            schema_version,
        )

    # Check if we have correct number of phases for schema version
    expected_count = len(required_phases)
    if len(phase_log) < expected_count:
        issues.append(
            {
                "phase": "N/A",
                "status": "INCOMPLETE",
                "issue": f"Schema v{schema_version}: Expected {expected_count} phases, found {len(phase_log)} - file may need migration",
            }
        )

    # Build lookup by phase name
    phase_lookup = {p.get("phase_name"): p for p in phase_log}

    last_executed_index = -1

    for i, phase_name in enumerate(required_phases):
        entry = phase_lookup.get(phase_name)

        if not entry:
            issues.append(
                {
                    "phase": phase_name,
                    "phase_index": i,
                    "status": "MISSING",
                    "issue": "Phase not found in log",
                }
            )
            continue

        status = entry.get("status", "NOT_EXECUTED")

        if status == "EXECUTED":
            # Check for gaps (executed phases after non-executed ones)
            # But allow gaps if they contain only valid SKIPPED phases
            if last_executed_index >= 0 and i > last_executed_index + 1:
                for j in range(last_executed_index + 1, i):
                    gap_phase = required_phases[j]
                    gap_entry = phase_lookup.get(gap_phase)

                    # Check if gap phase is a valid SKIPPED
                    if gap_entry:
                        gap_status = gap_entry.get("status", "NOT_EXECUTED")
                        if gap_status == "SKIPPED":
                            # Verify it's a valid SKIPPED (with proper blocked_by)
                            is_valid_skip, _ = validate_skipped_phase(gap_entry)
                            if is_valid_skip:
                                continue  # Valid SKIPPED, not a gap issue

                    # Only add gap error if not already in issues
                    if not any(iss.get("phase") == gap_phase for iss in issues):
                        issues.append(
                            {
                                "phase": gap_phase,
                                "phase_index": j,
                                "status": "SKIPPED_GAP",
                                "issue": f"Phase skipped (gap between {required_phases[last_executed_index]} and {phase_name})",
                            }
                        )
            last_executed_index = i

            # Validate that EXECUTED phases have outcome with valid value
            outcome = entry.get("outcome")
            if not outcome:
                issues.append(
                    {
                        "phase": phase_name,
                        "phase_index": i,
                        "status": "INCOMPLETE",
                        "issue": "EXECUTED phase missing outcome (PASS/FAIL)",
                    }
                )
            elif outcome not in ["PASS", "FAIL"]:
                issues.append(
                    {
                        "phase": phase_name,
                        "phase_index": i,
                        "status": "INVALID_OUTCOME",
                        "issue": f"Invalid outcome '{outcome}' - must be PASS or FAIL",
                    }
                )

        elif status == "IN_PROGRESS":
            issues.append(
                {
                    "phase": phase_name,
                    "phase_index": i,
                    "status": "IN_PROGRESS",
                    "issue": "Phase left in progress (incomplete execution)",
                }
            )

        elif status == "NOT_EXECUTED":
            issues.append(
                {
                    "phase": phase_name,
                    "phase_index": i,
                    "status": "NOT_EXECUTED",
                    "issue": "Phase not executed",
                }
            )

        elif status == "SKIPPED":
            # Validate SKIPPED has proper blocked_by
            is_valid_skip, skip_message = validate_skipped_phase(entry)
            if not is_valid_skip:
                issues.append(
                    {
                        "phase": phase_name,
                        "phase_index": i,
                        "status": "INVALID_SKIP",
                        "issue": skip_message,
                        "blocked_by": entry.get("blocked_by", ""),
                    }
                )

        else:
            # Unknown status
            issues.append(
                {
                    "phase": phase_name,
                    "phase_index": i,
                    "status": status,
                    "issue": f"Unknown status: {status}",
                }
            )

    return len(issues) == 0, issues, schema_version


def write_validation_marker(step_files: List[str], passed: bool) -> None:
    """
    Write a validation marker file that the post-commit hook can check.
    This enables detection of --no-verify bypass.
    """
    try:
        marker_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "step_files_validated": step_files,
            "validation_passed": passed,
            "hook_version": "2.0.0",
        }

        # Use atomic write pattern: write to temp, then rename
        marker_dir = os.path.dirname(VALIDATION_MARKER_FILE)
        if marker_dir and not os.path.exists(marker_dir):
            os.makedirs(marker_dir, exist_ok=True)

        # Write to temp file first
        fd, temp_path = tempfile.mkstemp(dir=marker_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(marker_data, f, indent=2)
            # Atomic rename
            os.replace(temp_path, VALIDATION_MARKER_FILE)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    except Exception as e:
        # Silent fail - marker is optional
        print(f"Warning: Could not write validation marker: {e}", file=sys.stderr)


def log_bypass_attempt(reason: str, files: List[str], issues: List[Dict]) -> None:
    """
    Log when validation fails but commit might be bypassed with --no-verify.
    This is written by pre-commit when validation fails.
    """
    try:
        git_info = get_git_info()

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": "VALIDATION_FAILED",
            "user": git_info["user"],
            "email": git_info["email"],
            "branch": git_info["branch"],
            "reason": reason,
            "files": files,
            "issues_count": len(issues),
            "issues_summary": [
                {
                    "phase": iss.get("phase"),
                    "status": iss.get("status"),
                    "issue": iss.get("issue"),
                }
                for iss in issues[:5]  # Limit to first 5 issues
            ],
        }

        # Ensure directory exists
        log_dir = os.path.dirname(BYPASS_LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        with open(BYPASS_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        pass  # Silent fail - logging is best effort


def print_validation_result(
    file_path: str, is_valid: bool, issues: List[Dict], schema_version: str = "1.0"
) -> None:
    """Print validation result for a file."""
    print(f"\n  Checking: {file_path}")

    if is_valid:
        phase_counts = {"4.0": 5, "2.0": 7, "1.0": 14}
        phase_count = phase_counts.get(schema_version, 14)
        print(f"    [OK] All {phase_count} phases completed (schema v{schema_version})")
    else:
        for issue in issues:
            phase = issue.get("phase", "?")
            status = issue.get("status", "?")
            issue_text = issue.get("issue", "Unknown issue")

            # Color-code by severity
            if status in ["IN_PROGRESS", "NOT_EXECUTED", "MISSING"]:
                print(f"    [FAIL] {phase}: {status} - {issue_text}")
            elif status == "INVALID_SKIP":
                blocked_by = issue.get("blocked_by", "")
                print(f"    [FAIL] {phase}: {status} - {issue_text}")
                if blocked_by:
                    print(f'           blocked_by: "{blocked_by}"')
            else:
                print(f"    [WARN] {phase}: {status} - {issue_text}")


def print_failure_summary(failed_files: List[Dict]) -> None:
    """Print detailed failure summary with recovery instructions."""
    print("\n" + "=" * 70)
    print("  COMMIT BLOCKED: TDD phases incomplete")
    print("=" * 70)

    print("\nFiles with incomplete phases:")

    for failed in failed_files:
        file_path = failed["file"]
        issues = failed["issues"]

        print(f"\n  {file_path}:")

        # Group issues by type for clearer output
        not_executed = [i for i in issues if i.get("status") == "NOT_EXECUTED"]
        in_progress = [i for i in issues if i.get("status") == "IN_PROGRESS"]
        invalid_skip = [i for i in issues if i.get("status") == "INVALID_SKIP"]
        missing = [i for i in issues if i.get("status") == "MISSING"]
        gaps = [i for i in issues if i.get("status") == "SKIPPED_GAP"]
        other = [
            i
            for i in issues
            if i.get("status")
            not in [
                "NOT_EXECUTED",
                "IN_PROGRESS",
                "INVALID_SKIP",
                "MISSING",
                "SKIPPED_GAP",
            ]
        ]

        if in_progress:
            print(
                f"    IN_PROGRESS (abandoned): {', '.join(i['phase'] for i in in_progress)}"
            )
        if not_executed:
            print(f"    NOT_EXECUTED: {', '.join(i['phase'] for i in not_executed)}")
        if invalid_skip:
            print(f"    INVALID_SKIP: {', '.join(i['phase'] for i in invalid_skip)}")
            for iss in invalid_skip:
                print(f"      - {iss['phase']}: {iss.get('issue', '')}")
        if missing:
            print(f"    MISSING: {', '.join(i['phase'] for i in missing)}")
        if gaps:
            print(f"    GAPS: {', '.join(i['phase'] for i in gaps)}")
        if other:
            for iss in other:
                print(
                    f"    {iss.get('status', '?')}: {iss.get('phase', '?')} - {iss.get('issue', '')}"
                )

        # Suggest resume point
        all_phases_with_issues = [i["phase"] for i in issues if i.get("phase") != "N/A"]
        if all_phases_with_issues:
            # Find first incomplete phase by index
            first_issue = min(
                issues,
                key=lambda x: x.get("phase_index", 999)
                if x.get("phase") != "N/A"
                else 999,
            )
            if first_issue.get("phase") != "N/A":
                print(f"    Resume from: {first_issue['phase']}")

    print("\n" + "-" * 70)
    print("To fix:")
    print("  1. Complete the missing TDD phases")
    print("  2. For SKIPPED phases, add valid blocked_by reason:")
    print("     - BLOCKED_BY_DEPENDENCY: <reason>")
    print("     - NOT_APPLICABLE: <reason>")
    print("     - APPROVED_SKIP: <approver and reason>")
    print("  3. Note: DEFERRED: prefix blocks commit (incomplete work)")
    print("  4. Update the step file with phase status")
    print("  5. Stage changes: git add <step-file>")
    print("  6. Try commit again")
    print("")
    print("To bypass (NOT RECOMMENDED - will be logged):")
    print("  git commit --no-verify")
    print("=" * 70)


def main() -> int:
    """Main entry point."""
    print("nWave TDD Phase Validation...")

    # Get staged step files
    step_files = get_staged_step_files()

    if not step_files:
        print("  [OK] No step files in commit")
        write_validation_marker([], True)
        return 0

    print(f"  Found {len(step_files)} step file(s) to validate")

    # Validate each file
    all_valid = True
    failed_files: List[Dict] = []
    all_issues: List[Dict] = []

    for file_path in step_files:
        is_valid, issues, schema_version = validate_step_file(file_path)
        print_validation_result(file_path, is_valid, issues, schema_version)

        if not is_valid:
            all_valid = False
            failed_files.append({"file": file_path, "issues": issues})
            all_issues.extend(issues)

    # Write validation marker
    write_validation_marker(step_files, all_valid)

    # Final result
    if all_valid:
        print("\n[OK] TDD phase validation passed")
        return 0
    else:
        # Log the failure (for bypass detection)
        log_bypass_attempt(
            "TDD phase validation failed", [f["file"] for f in failed_files], all_issues
        )

        # Print detailed failure summary
        print_failure_summary(failed_files)

        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
