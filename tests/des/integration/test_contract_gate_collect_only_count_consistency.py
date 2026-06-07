"""Integration guard: contract-gate collect-only count consistency.

Sibling-feature regression pin (F-CONTRACT-SUITE-COLLECTION-ERRORS). Verifies
that the contract gate's `--collect-only` digest scope stays consistent with
pytest's own in-process collected count, so the gate can never fingerprint a
different set than it actually runs.

Real I/O: the gate's real in-process collection over the live tree (via the
`_collect_scope` child worker).
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.integration
class TestContractGateCollectOnlyCountConsistency:
    """Pin the collect-only digest scope to the run-phase collected count."""

    def test_collect_only_node_id_count_matches_run_phase_count(self):
        """Collect-only digest scope must cover the run-phase collected scope.

        The contract gate's `--collect-only` digest path and its run path MUST
        fingerprint the SAME logical scope — divergence means the digest
        fingerprints a scope the run never executes (or vice-versa). This
        integration test pins the two together so the digest can never silently
        drift from the suite the gate actually runs.

        Since the digest derives from pytest's in-process collection
        (`session.items`) deduplicated to canonical `fspath::item.name`
        identities (ADR-001), the digested-set cardinality is the run-phase
        collected count MINUS the documented hypothesis-rerun duplicates — the
        only legitimate collapse (the same test re-collected under hypothesis
        rerun). The invariant is therefore parity WITHIN that tolerance.

        Both cardinalities come from the gate's OWN single collection
        (`_collect_scope` → `node_ids` + `collected_count`), the SAME-session
        pair the production parity guard enforces. A separate `-q` subprocess
        would (a) add cross-run collection drift on top of the rerun-dedup gap,
        and (b) be defeated by this repo's custom conftest collect-formatter
        (which prints a domain table, not a `<N> tests collected` line) — so the
        single-session pair is both the right invariant and the robust one. A
        real scope collapse (gap > tolerance, or a populated suite that dedups
        to zero) still fails here. The tolerance is imported from production so
        there is a single source of truth, no magic number duplicated here.
        """
        from des.cli.run_contract_gate import _RERUN_TOLERANCE, _collect_scope

        repo = Path(__file__).resolve().parents[3]
        scope = _collect_scope(repo)
        digest_count = len(scope.node_ids)
        collected_count = scope.collected_count
        gap = collected_count - digest_count

        assert collected_count > 0, (
            "pytest's in-process collection reports zero collected items for "
            "the contract marker — the live suite is unexpectedly empty"
        )
        assert digest_count > 0, (
            "the collect-only digest scope is empty — the gate would "
            "fingerprint nothing while the run executes the suite"
        )
        assert 0 <= gap <= _RERUN_TOLERANCE, (
            f"collect-only digest scope ({digest_count} node-ids) diverges "
            f"from the same-session collected count ({collected_count}) by "
            f"{gap}, outside the hypothesis-rerun tolerance {_RERUN_TOLERANCE} "
            "— the gate would fingerprint a different set than it runs"
        )
