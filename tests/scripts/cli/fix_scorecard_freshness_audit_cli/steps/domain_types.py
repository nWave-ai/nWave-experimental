"""Domain types for the fix-scorecard-freshness-audit-cli acceptance set.

F-CROSS-TREE-SCORECARD-FRESHNESS-AUDIT-CLI (Mandate-12 criterion 1). Every
domain noun used in the slice-01 Gherkin is expressed once here as a typed
enum / NewType / frozen dataclass. The composition root consumes these typed
parameters; step bodies delegate -- no raw ``str`` where a domain enum exists,
no inline business logic.

Vocabulary shared across the slice-01 walking-skeleton feature file and its
step module -- the SSOT for the scorecard-freshness-audit domain language.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-scorecard-freshness-audit-cli").
FeatureId = NewType("FeatureId", str)

# A scorecard F-id citation (e.g. "F-01", "F-PRR-SCORECARD-STALENESS-AUDIT").
ScorecardFId = NewType("ScorecardFId", str)

# Filesystem path string for a cited file (POSIX-relative to repo root).
CitedFilePath = NewType("CitedFilePath", str)


class CellFreshness(str, Enum):
    """Per-cell freshness verdict the CLI emits in the per-cell results record.

    Three-way verdict: a cell is FRESH (evidence found within threshold), STALE
    (cited F-id has no recent commit OR cited file path's mtime/blame is older
    than threshold), or MISSING (cited evidence cannot be located at all --
    file does not exist, F-id never named in git history).
    """

    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"


class ScorecardFreshnessVerdict(str, Enum):
    """The top-level verdict the CLI emits in the stdout token + exit code.

    Two-way top-level verdict: PASS (every cell is FRESH) or FAIL (at least
    one cell is STALE or MISSING). The malformed-input case (exit 2) is a
    SEPARATE verdict shape (no PASS/FAIL emitted) -- handled at slice-02; out
    of scope for the slice-01 walking skeleton.
    """

    PASS = "PASS"
    FAIL = "FAIL"


# ScorecardFreshnessVerdict -> process exit code (SSOT for the exit-code
# contract). The malformed-input exit 2 is intentionally absent from this
# table -- it is a distinct verdict shape introduced in slice-02.
EXIT_CODE_BY_VERDICT: dict[ScorecardFreshnessVerdict, int] = {
    ScorecardFreshnessVerdict.PASS: 0,
    ScorecardFreshnessVerdict.FAIL: 1,
}


# The stdout token shape (L1.x contract style; mirrors sibling-gate CLIs).
# The CLI emits exactly this prefix followed by space-separated
# key=value pairs; the AT asserts the prefix + key set + verdict value.
STDOUT_TOKEN_PREFIX: str = "scorecard_freshness"


# Default stale-threshold (days). Configurable via --stale-threshold-days.
# The slice-01 walking-skeleton ATs author git history far INSIDE this
# threshold (recent commits for AT1 happy path; one old commit for AT2 sad
# path) so the default value drives every walking-skeleton verdict.
DEFAULT_STALE_THRESHOLD_DAYS: int = 14


@dataclass(frozen=True)
class FreshnessCliResult:
    """Observable result of one check_scorecard_freshness invocation.

    Port-exposed observable surface for the layer-3 subprocess driving port.
    Used in Then-step assertions to extract exit code + stdout/stderr without
    exposing internal struct details.
    """

    exit_code: int
    stdout: str
    stderr: str
