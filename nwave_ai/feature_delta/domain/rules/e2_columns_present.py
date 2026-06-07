"""E2: ColumnsPresent rule — commitments table header validation.

Rule: every ``### [REF] Inherited commitments`` block MUST have a header row
containing exactly the four columns: Origin | Commitment | DDD | Impact (in
that order, case-insensitive).

Missing or reordered columns are reported as E2 violations with file:line
and a remediation string.
"""

from __future__ import annotations

import re

from nwave_ai.feature_delta.domain.violations import ValidationViolation


# The four required column names, in order.
_REQUIRED_COLUMNS = ("Origin", "Commitment", "DDD", "Impact")

_COMMITMENTS_HEADING = re.compile(
    r"###\s+\[REF\]\s+Inherited commitments", re.IGNORECASE
)
_TABLE_HEADER = re.compile(r"^\|(.+)\|")
_SEPARATOR_ROW = re.compile(r"^\|[-|: ]+\|")


def _parse_header_columns(line: str) -> list[str]:
    """Extract column names from a pipe-delimited header row."""
    inner = line.strip().strip("|")
    return [c.strip() for c in inner.split("|")]


def check(text: str, file_path: str) -> tuple[ValidationViolation, ...]:
    """Check E2 rule on raw text.

    Returns a tuple of ValidationViolation objects (empty = clean).
    For each ``### [REF] Inherited commitments`` block, the next non-empty
    line that starts with ``|`` is treated as the header row.  If it is
    missing one or more of the required columns the violation is reported
    at that line number.
    """
    violations: list[ValidationViolation] = []

    lines = text.splitlines()
    in_commitments_block = False
    awaiting_header = False

    for lineno, line in enumerate(lines, start=1):
        if _COMMITMENTS_HEADING.search(line):
            in_commitments_block = True
            awaiting_header = True
            continue

        if not in_commitments_block:
            continue

        if awaiting_header:
            # Skip blank lines before the header.
            if not line.strip():
                continue

            if line.startswith("|") and not _SEPARATOR_ROW.match(line):
                # This is the header row — validate it.
                columns = _parse_header_columns(line)
                columns_upper = [c.upper() for c in columns]
                missing = [
                    col for col in _REQUIRED_COLUMNS if col.upper() not in columns_upper
                ]
                if missing:
                    missing_str = ", ".join(f"'{m}'" for m in missing)
                    violations.append(
                        ValidationViolation(
                            rule="E2",
                            severity="error",
                            file=file_path,
                            line=lineno,
                            offender=line.strip(),
                            remediation=(
                                f"Add missing column(s) {missing_str} to the "
                                f"commitments table header. "
                                f"Expected: | Origin | Commitment | DDD | Impact |"
                            ),
                        )
                    )
                awaiting_header = False
            elif not line.startswith("|"):
                # Non-table line encountered before finding the header.
                awaiting_header = False
                in_commitments_block = False

        # Once we've processed the header, reset on the next ## Wave heading.
        elif line.startswith("## Wave"):
            in_commitments_block = False
            awaiting_header = False

    return tuple(violations)
