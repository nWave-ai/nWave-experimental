#!/usr/bin/env python3
"""Skill Hash Validation Hook

Fast pre-commit check that verifies monitored skill file hashes match
the expected values in test_skill_restructuring.py. Catches hash drift
before CI — saves time and tokens.

Runs only when nWave/skills/ files are staged.
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"

SKILLS_DIR = Path("nWave/skills")
HASH_TEST_FILE = Path("tests/build/unit/test_skill_restructuring.py")


def get_staged_skill_files() -> list[str]:
    """Return staged files under nWave/skills/."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    return [
        f
        for f in result.stdout.strip().split("\n")
        if f and f.startswith("nWave/skills/")
    ]


def extract_bulk_hashes() -> dict[str, str]:
    """Parse BULK_HASHES dict from test file."""
    if not HASH_TEST_FILE.exists():
        return {}

    content = HASH_TEST_FILE.read_text(encoding="utf-8")

    # Extract the BULK_HASHES dictionary content
    match = re.search(
        r"BULK_HASHES\s*=\s*\{(.*?)\}",
        content,
        re.DOTALL,
    )
    if not match:
        return {}

    hashes = {}
    for line_match in re.finditer(r'"(nw-[^"]+)":\s*"([a-f0-9]{32})"', match.group(1)):
        hashes[line_match.group(1)] = line_match.group(2)

    return hashes


def compute_drift() -> list[tuple[str, str, str]]:
    """Compare every monitored skill's on-disk hash against the baseline.

    Returns a sorted list of (skill_name, baseline_hash, actual_hash) for
    monitored skills whose SKILL.md exists and whose md5 no longer matches
    the baseline recorded in HASH_TEST_FILE.
    """
    bulk_hashes = extract_bulk_hashes()

    drift: list[tuple[str, str, str]] = []
    for skill_name in sorted(bulk_hashes):
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_file.exists():
            continue

        actual = hashlib.md5(skill_file.read_bytes()).hexdigest()
        expected = bulk_hashes[skill_name]

        if actual != expected:
            drift.append((skill_name, expected, actual))

    return drift


def repin(drift: list[tuple[str, str, str]]) -> int:
    """Rewrite HASH_TEST_FILE's baseline entries to match drifted skills.

    Surgical: only the drifted entries are touched, and only after every
    entry has been located in the baseline text (fail loud before writing
    anything if any drifted skill is absent from the baseline).
    """
    if not drift:
        print(f"{GREEN}No hash drift detected -- nothing to re-pin.{NC}")
        return 0

    content = HASH_TEST_FILE.read_text(encoding="utf-8")

    for name, old, new in drift:
        needle = f'"{name}": "{old}"'
        if needle not in content:
            print(
                f"{RED}Cannot re-pin {name}: baseline entry {needle!r} not "
                f"found in {HASH_TEST_FILE}{NC}"
            )
            return 1
        content = content.replace(needle, f'"{name}": "{new}"')
        print(f"  re-pinned {name}: {old} -> {new}")

    HASH_TEST_FILE.write_text(content, encoding="utf-8")
    print()
    print(f"Re-pinned {len(drift)} skill(s). Review the diff before committing.")
    return 0


def preview_repin(drift: list[tuple[str, str, str]]) -> int:
    """Dry-run preview for `--repin` without `--apply`: never writes the baseline.

    Names every drifted monitored skill (old -> new hash) so the maintainer
    can see the full blast radius -- including a skill they never meant to
    touch -- before choosing to bless it.
    """
    if not drift:
        print(f"{GREEN}No hash drift detected -- nothing to re-pin.{NC}")
        return 0

    print(f"{YELLOW}Preview: {len(drift)} skill(s) would be re-pinned:{NC}")
    for name, old, new in drift:
        print(f"  {name}: {old} -> {new}")
    print()
    print("This is a preview. Re-run with --repin --apply to write the baseline.")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--repin" in args:
        drift = compute_drift()
        if "--apply" in args or "--yes" in args:
            return repin(drift)
        return preview_repin(drift)

    staged = get_staged_skill_files()
    if not staged:
        return 0

    bulk_hashes = extract_bulk_hashes()
    if not bulk_hashes:
        print(f"{YELLOW}Warning: could not parse BULK_HASHES from test file{NC}")
        return 0

    # Map staged files to skill names
    changed_skills: set[str] = set()
    for filepath in staged:
        parts = Path(filepath).parts
        # nWave/skills/{skill-name}/SKILL.md → skill-name
        if len(parts) >= 3:
            changed_skills.add(parts[2])

    # Check only monitored skills that were changed
    mismatches: list[tuple[str, str, str]] = []
    for skill_name in sorted(changed_skills):
        if skill_name not in bulk_hashes:
            continue

        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_file.exists():
            continue

        actual = hashlib.md5(skill_file.read_bytes()).hexdigest()
        expected = bulk_hashes[skill_name]

        if actual != expected:
            mismatches.append((skill_name, expected, actual))

    if not mismatches:
        return 0

    print(f"{RED}COMMIT BLOCKED: Skill hash mismatch{NC}")
    print()
    print("The following monitored skills were modified but their hashes")
    print(f"in {HASH_TEST_FILE} were not updated:")
    print()

    for name, expected, actual in mismatches:
        print(f"  {name}:")
        print(f"    expected: {expected}")
        print(f"    actual:   {actual}")
    print()
    print("Update BULK_HASHES in the test file with the actual values above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
