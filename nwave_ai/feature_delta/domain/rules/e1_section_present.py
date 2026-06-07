"""E1: SectionPresent rule — wave heading structure validation.

Rule: every ``## Wave: <NAME>`` heading must match the canonical pattern.
Near-misses (typos, extra spaces) are reported with a did-you-mean suggestion
derived from difflib over the set of known wave names.

Empty files are handled by the orchestrator before calling this rule.
"""

from __future__ import annotations

import difflib
import re

from nwave_ai.feature_delta.domain.violations import ValidationViolation


# Canonical wave names for did-you-mean matching.
_KNOWN_WAVES = ("DISCOVER", "DISCUSS", "DESIGN", "DEVOPS", "DISTILL", "DELIVER")
_KNOWN_WAVES_UPPER = frozenset(_KNOWN_WAVES)

# Correct format: ## Wave: <NAME> — captures the wave name.
_FORMAT_CORRECT = re.compile(r"^##\s+Wave:\s+(\w+)")

# Loose detector: any line that looks like a wave heading attempt.
# Catches "## Wave : DISCUSS" (extra space before colon) and similar.
_LOOSE_HEADING = re.compile(r"^##\s+Wave\s*[:\s]+\s*(\w+)", re.IGNORECASE)


def _is_fully_valid(line: str) -> bool:
    """Return True only when the heading is format-correct AND wave name is known."""
    match = _FORMAT_CORRECT.match(line)
    if not match:
        return False
    return match.group(1).upper() in _KNOWN_WAVES_UPPER


def check(text: str, file_path: str) -> tuple[ValidationViolation, ...]:
    """Check E1 rule on raw text.

    Returns a tuple of ValidationViolation objects (empty = clean).
    Any line that looks like a wave heading but is not fully valid
    (correct format + known name) is reported as an E1 violation.
    """
    violations: list[ValidationViolation] = []

    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        # Skip lines that clearly are not wave headings.
        if "Wave" not in line and "wave" not in line:
            continue
        if not line.startswith("#"):
            continue

        # Does this line look like a wave heading attempt?
        loose = _LOOSE_HEADING.match(line)
        if loose is None:
            continue

        # Is it fully valid (format-correct + known name)?
        if _is_fully_valid(line):
            continue

        # It's a near-miss — compute did-you-mean.
        wave_name = loose.group(1).upper()
        suggestions = difflib.get_close_matches(
            wave_name, _KNOWN_WAVES, n=1, cutoff=0.4
        )
        if suggestions:
            best_wave = suggestions[0]
            did_you_mean = f"## Wave: {best_wave}"
        else:
            did_you_mean = f"## Wave: <{' | '.join(_KNOWN_WAVES)}>"

        violations.append(
            ValidationViolation(
                rule="E1",
                severity="error",
                file=file_path,
                line=lineno,
                offender=line.strip(),
                remediation=(
                    "Replace the malformed heading with the canonical form: "
                    "'## Wave: <NAME>' (e.g., '## Wave: DISCUSS')."
                ),
                did_you_mean=did_you_mean,
            )
        )

    return tuple(violations)
