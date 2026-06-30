"""Domain types for the fix-des-single-entry-point-consolidation acceptance suite.

Mandate-12 criterion 1: every domain noun used in Gherkin has a typed enum,
dataclass, or NewType here. Step bodies consume these typed parameters; raw
strings are forbidden where a domain enum already covers the value.

Note on the SubcommandTable: this is the SSOT for slice-02's parametrize list
and slice-03's grep-zero assertions. Architect's DESIGN table (16→16 naming
map) is the prose mirror; this Python literal is the executable mirror. The
two MUST stay in sync — the prose table is recorded in the feature-delta.md
under `## Wave: DESIGN / [REF] 16→16 subcommand naming map`.

Filesystem-grounded count: `src/des/cli/*.py` (excluding `__init__.py`)
contains 16 callable modules as of 2026-05-23 — the architect's table listed
15 and missed `check_slice_at_completeness.py`. This module records all 16;
DELIVER MUST reconcile this gap before slice-02 begins (see distill
upstream-issues.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HealthCheckVerdict(str, Enum):
    """The two terminal verdicts of the des health-check subcommand.

    Mirrors the exit-code contract documented in the existing
    `des-health-check` shim (0 = HEALTHY, 1 = UNHEALTHY).
    """

    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"


class OutputFormat(str, Enum):
    """Output formats supported by the health-check subcommand."""

    TEXT = "text"
    JSON = "json"


@dataclass(frozen=True)
class SubcommandRow:
    """One row of the subcommand registry — the dispatcher SSOT."""

    name: str  # kebab-case name exposed to operators (e.g. "health-check")
    module_path: str  # importable dotted path (e.g. "des.cli.health_check")
    function_name: str  # callable in the module (always "main" today)


# The complete 16-row subcommand table. SSOT for slice-02 parametrize, slice-03
# grep-zero assertions, and the dispatcher registry literal.
#
# Filesystem-grounded against `src/des/cli/*.py` (excluding `__init__.py`) on
# 2026-05-23. Row 16 (check-slice-at-completeness) is NOT in the architect's
# 15-row prose table — DELIVER MUST reconcile before slice-02. See distill
# upstream-issues.md.
SUBCOMMAND_TABLE: tuple[SubcommandRow, ...] = (
    SubcommandRow("log-phase", "des.cli.log_phase", "main"),
    SubcommandRow("init-log", "des.cli.init_log", "main"),
    SubcommandRow("verify-integrity", "des.cli.verify_deliver_integrity", "main"),
    SubcommandRow("roadmap", "des.cli.roadmap", "main"),
    SubcommandRow("health-check", "des.cli.health_check", "main"),
    SubcommandRow("verify-commit-trailers", "des.cli.verify_commit_trailers", "main"),
    SubcommandRow(
        "verify-slice-commit",
        "des.cli.verify_slice_commit_completeness",
        "main",
    ),
    SubcommandRow("walking-skeleton-gate", "des.cli.walking_skeleton_gate", "main"),
    SubcommandRow(
        "walking-skeleton-done-gate",
        "des.cli.walking_skeleton_done_gate",
        "main",
    ),
    SubcommandRow("carpaccio-slice-gate", "des.cli.carpaccio_slice_gate", "main"),
    SubcommandRow("classify-features", "des.cli.classify_features", "main"),
    SubcommandRow("convert-to-atdd-pure", "des.cli.convert_to_atdd_pure", "main"),
    SubcommandRow("reverify-slice-commit", "des.cli.reverify_slice_commit", "main"),
    SubcommandRow(
        "verify-environmental-e2e",
        "des.cli.verify_environmental_e2e",
        "main",
    ),
    SubcommandRow("run-contract-gate", "des.cli.run_contract_gate", "main"),
    # Row 16 — present in src/des/cli/ but missing from architect's DESIGN
    # naming map. Reconciliation pending in DELIVER.
    SubcommandRow(
        "check-slice-at-completeness",
        "des.cli.check_slice_at_completeness",
        "main",
    ),
    # Row 17 (doctor) + Row 18 (verify-readiness-pre-dispatch) live in
    # _REGISTRY but are not yet mirrored here -- they were added post-
    # 2026-05-23 and the SUBCOMMAND_TABLE is a parametrize SUBSET (used by
    # AT-04 / AT-05 / AT-06), not a length-pin. New row 19 below ships the
    # slice-04 spine-ledger aggregator subcommand.
    SubcommandRow(
        "verify-slice-ledger-evidence",
        "des.cli.verify_slice_ledger_evidence",
        "main",
    ),
    # commit-slice -- the mechanical correct-by-construction slice commit
    # (#67 facet-4 / AD-23 adjacent: committed-scope Gate-Scope: by construction).
    SubcommandRow("commit-slice", "des.cli.commit_slice", "main"),
    SubcommandRow("validate-feature-delta", "des.cli.validate_feature_delta", "main"),
    # record-discuss-review -- the O-4 keyless DISCUSS PO-review verdict
    # producer (nwave-flow-v2-enforcement slice-07b veto-gate, writes BOTH
    # approved + needs-revision).
    SubcommandRow("record-discuss-review", "des.cli.discuss_review_verdict", "main"),
    # record-at-review-verdict -- the AT-review verdict producer (D-register,
    # oss-review-verdict-demotion S2). Symmetric with record-discuss-review;
    # post-demotion the RECORD is the entire control so discoverability is
    # load-bearing.
    SubcommandRow("record-at-review-verdict", "des.cli.at_review_verdict", "main"),
    # fix-wave-bypass-recovery-truthful slice-02: the `des wave-clear` operator
    # subcommand is mirrored here so the single-entry-point AT verifies its
    # reachability (DISCUSS/DESIGN Reuse Posture required this mirror).
    SubcommandRow("wave-clear", "des.cli.wave_clear", "main"),
)


# The 7 canonical health-check check names — the contract surface for
# slice-01 AT-03 (json shape).
EXPECTED_HEALTH_CHECK_NAMES: tuple[str, ...] = (
    "version",
    "module_import",
    "templates",
    "hook_actions",
    "log_directory",
    "agents_installed",
    "skills_installed",
)
