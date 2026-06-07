"""Auto-lowercase the first letter of conventional commit subjects.

Runs as prepare-commit-msg hook — modifies the commit message file
BEFORE gitlint validates it. This prevents the recurring failure where
the subject starts with uppercase (e.g., "feat: Add X" → "feat: add X").

Only modifies the first character after "type(scope): " or "type: ".
Leaves the rest of the message untouched.
"""

import re
import sys


def fix_subject_case(msg: str) -> str:
    """Lowercase the first letter after the conventional commit prefix."""
    lines = msg.split("\n", 1)
    subject = lines[0]

    # Match conventional commit: type(scope): Subject or type: Subject
    match = re.match(r"^(\w+(?:\([^)]*\))?\s*:\s*)", subject)
    if match:
        prefix = match.group(1)
        rest = subject[len(prefix) :]
        if rest and rest[0].isupper():
            rest = rest[0].lower() + rest[1:]
            lines[0] = prefix + rest

    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        return 0

    msg_file = sys.argv[1]
    # Only run for regular commits (not merge, squash, etc.)
    commit_source = sys.argv[2] if len(sys.argv) > 2 else ""
    if commit_source in ("merge", "squash"):
        return 0

    with open(msg_file) as f:
        original = f.read()

    fixed = fix_subject_case(original)
    if fixed != original:
        with open(msg_file, "w") as f:
            f.write(fixed)

    return 0


if __name__ == "__main__":
    sys.exit(main())
