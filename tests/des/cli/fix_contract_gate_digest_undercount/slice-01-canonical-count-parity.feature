@feature-fix-contract-gate-digest-undercount
Feature: The contract gate digest fingerprints the full canonical collected scope
  As an nWave framework developer
  I want the contract gate's gate-scope fingerprint to cover EVERY collected test,
    not a collapsed proper subset
  So that a change to ANY test in the suite is mechanically visible to the
    --verify-gate-scope exit gate, and a non-Lyra customer can trust the
    Gate-Scope trailer covers the whole contract -- not 74% of it

  # === DISTILL reconciliation note (Code-is-SSOT, 2026-05-30) ===
  # This file REPLACES IN PLACE the stale scaffold that encoded the WRONG
  # mechanism (a non-existent custom conftest collect-formatter) and a 2-slice
  # structure with a @skip'd regression-pin. Per ADR-001 the real defect is
  # stock-pytest `-q` collect-stdout collapse, and the fix derives the digest
  # from pytest's IN-PROCESS collection API (session.items, identity
  # fspath::item.name). One slice, unskipped, no @skip theater.
  #
  # === The oracle: PARITY, scale-invariant (revision 2026-05-30) ===
  # The witness for "the digest fingerprints the FULL canonical scope" is a
  # SCALE-INVARIANT parity oracle -- a dimensionless equality, NOT any magnitude
  # constant. A magnitude threshold would only prove "more than N node-ids" and
  # would silently pass a future grown-then-re-collapsed suite, exactly the
  # regression class this gate exists to catch. The oracle is:
  #
  #   node_id_count == collected_count  (within the hypothesis-rerun tolerance)
  #
  # where `node_id_count` is the digested-set cardinality and `collected_count`
  # is pytest's OWN in-process `len(session.items)` from the SAME in-process
  # collection session (ADR-001 §82-86 -- production already computes this for
  # the fail-closed parity guard). The tolerance is the documented
  # hypothesis-rerun duplicates (ADR-001 §98: the (fspath,item.name) identity
  # measured 4504 / 4523 -- exactly 19 reruns are the same test re-collected,
  # whose collapse is correct). So the oracle is
  # `0 <= collected_count - node_id_count <= 19` with a `> 0` non-vacuity lower
  # bound. It reads pytest's in-process count, immune to the very stdout-parse
  # heuristic being removed -- strictly stronger than any magnitude floor AND
  # stronger than `== stdout _collected_count`. The only constant is the rerun
  # tolerance, sourced from ADR-001; no suite-size magic lives in this AT, so it
  # never re-derives when the suite grows.
  #
  # === Driving port (Mandate-13, Layer 3 subprocess) ===
  # `des run-contract-gate --collect-only --print-digest` invoked as a child
  # process. The AT NEVER imports `_collect_node_ids`. The observable surface is
  # the CLI exit code + the bare digest on stdout + the GateScopeDigest JSON
  # event on stderr.
  #
  # === Outside-In driver (the AT demands TWO observables the code lacks) ===
  # Master's GateScopeDigest event exposes ONLY {event, gate_scope_digest} --
  # no cardinalities. To assert the parity oracle THROUGH the driving port (no
  # direct import), the GREEN crafter MUST surface BOTH fields on the
  # GateScopeDigest event: `node_id_count` (digested-set cardinality) AND
  # `collected_count` (= len(session.items), the SAME in-process session ADR-001
  # already computes for the parity guard). Both are already-computed
  # observables -- the same legitimate Outside-In move. The AT requires them;
  # this is the Outside-In way the AT drives the production change.
  #
  # Confirmed RED 2026-05-30 (pipenv): assert_state_delta reports 3 semantic
  # violations -- digest_covers_full_scope expected True got False (neither
  # cardinality emitted -> parity cannot hold), exit_code expected 0 got 2,
  # digest_idempotent expected True got False (no digest on stdout to compare).
  # Semantic AssertionError, not a collection/import/skip error.
  #
  # Layer 3 subprocess + real I/O -> example-only, no PBT (Mandate 9 / 11).

  # S1-WS-1: the walking-skeleton. Drives the REAL CLI subprocess against the
  # live canonical contract suite; asserts the digest fingerprints the FULL
  # canonical scope (node_id_count parity-matches collected_count within the
  # hypothesis-rerun tolerance), is idempotent across two consecutive runs,
  # exits 0, and never mutates the repo. On master the GateScopeDigest event
  # carries neither cardinality -> the full-canonical parity assertion FAILS for
  # the right reason (semantic assert_state_delta mismatch, not a
  # collection/import/skip error).
  @slice-01 @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: The print-digest CLI fingerprints the full canonical collected scope of the live contract suite
    Given the contract gate is pointed at the canonical-live contract suite
    When the operator runs the print-digest CLI twice over the suite
    Then the emitted digest fingerprints the full-canonical collected scope
