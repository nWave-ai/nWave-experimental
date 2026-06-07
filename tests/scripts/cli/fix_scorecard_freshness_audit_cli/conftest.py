"""pytest-bdd configuration for the fix-scorecard-freshness-audit-cli AT set.

ATDD-pure carpaccio walking-skeleton: slice-01 only. The driving-port CLI
(``scripts/cli/check_scorecard_freshness.py``) is a RED scaffold on master --
authored by the DELIVER crafter (NOT in this DISTILL phase). The scaffold's
entry point raises ``AssertionError`` (RED: missing functionality, Mandate 7),
so scenarios FAIL for the right reason rather than erroring on a broken
import.

Until the crafter ships the scaffold, the slice-01 ATs will FAIL with
``ModuleNotFoundError`` at subprocess invocation (the CLI module does not
exist yet). The DELIVER step-01 brief is to author the RED scaffold first
so the failure mode flips to ``AssertionError`` (Mandate 7), then step-02+
implement the freshness-detection logic until the three slice-01 ATs go
GREEN.

The walking skeleton hosts three ATs (one happy path, one sad path, one
read-only preservation invariant) — the minimum proof of wiring across the
sibling-gate CLI convention.
"""

from __future__ import annotations
