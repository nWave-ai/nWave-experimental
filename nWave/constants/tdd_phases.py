"""
Single Source of Truth: TDD Phase Constants

This module defines the canonical 5-phase TDD cycle (schema v4.0).
All validators and tests should import from here.

Schema v4.0 (5 phases) - Streamlined from 7-phase v3.0:
- GREEN: Merges GREEN_UNIT + CHECK_ACCEPTANCE + GREEN_ACCEPTANCE
- COMMIT: Absorbs FINAL_VALIDATE metadata checks
- REVIEW: Moved to deliver-level Phase 4 (Adversarial Review via /nw:review)
- REFACTOR_CONTINUOUS: Moved to deliver-level Phase 3 (Complete Refactoring L1-L4)
"""

# Canonical 5-phase TDD cycle (schema v4.0)
REQUIRED_PHASES = [
    "PREPARE",
    "RED_ACCEPTANCE",
    "RED_UNIT",
    "GREEN",
    "COMMIT",
]

PHASE_COUNT = 5

# Phase descriptions for documentation and validation messages
PHASE_DESCRIPTIONS = {
    "PREPARE": "Remove @skip, verify only 1 scenario enabled",
    "RED_ACCEPTANCE": "Test must FAIL initially",
    "RED_UNIT": "Write failing unit tests",
    "GREEN": "Implement minimum code + verify acceptance (green acceptance is consequence of green unit)",
    "COMMIT": "Commit with detailed message (absorbs FINAL_VALIDATE metadata checks)",
}

# Legacy 7-phase cycle (schema v3.0) - for backward compatibility
LEGACY_PHASES_V3 = [
    "PREPARE",
    "RED_ACCEPTANCE",
    "RED_UNIT",
    "GREEN",
    "REVIEW",
    "REFACTOR_CONTINUOUS",
    "COMMIT",
]

LEGACY_PHASE_COUNT_V3 = 7

# Legacy 14-phase cycle (schema v1.0) - for backward compatibility
LEGACY_PHASES_V1 = [
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

LEGACY_PHASE_COUNT_V1 = 14
