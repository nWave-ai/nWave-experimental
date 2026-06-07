@feature-fix-atdd-pure-common-audit-log-ssot
Feature: The gate-event affinity bundle migrates six production callsites atomically with their fixture-fanout
  As an nWave framework operator stabilising the atdd_pure spine
  I want the six gate-event-affinity production callsites
  (subagent_stop_handler L529 + L738,
   carpaccio_intercept L217 + L322,
   reverify_slice_commit L199 + L452)
  to write and read through the singleton-shape audit log substrate scoped by feature
  And I want records seeded under one feature to be invisible to a reader filtered by another feature
  So that the F-M40-SLICE-02C-N1-PRODUCTION-FIXTURE-NOT-ATOMIC class is structurally closed by
    substrate-affinity bundling
  And so that the singleton common audit log preserves per-feature isolation under multi-feature load

  # carpaccio sub-slice slice-02c-A: ships AFTER slice-02d-N0 (helper SHIPPED M45
  # commit 7aca0369e). This bundle is the FIRST production-callsite-migration
  # bundle authored under the M51 H3 SUBSTRATE-AFFINITY decomposition (commit
  # b5e647e1b) + M56 amendment cycle 2 (commit fbdebd371). Three ATs:
  #
  # 1. AT-A1 -- regression-pin (parametrize-collapse over 6 callsites). For
  #    each of the 6 production callsites, the post-migration driver writes
  #    one representative event through the singleton-shape API and the AT
  #    asserts the common audit log substrate is present AND the per-feature
  #    legacy substrate is absent. Pre-DELIVER the production source still
  #    references the legacy per-feature path so this AT reds for the right
  #    reason (MISSING_FUNCTIONALITY: production migration absent).
  #
  # 2. AT-A2 -- forward-pin (`read_records(feature_id=X)` filter retrieves
  #    seeded records under the singleton-shape substrate). Slice-02b shipped
  #    the reader extension (`feature_id=` kw-only on `read_records`); this AT
  #    seeds a multi-feature substrate and asserts the filtered reader
  #    returns exactly the target feature's records.
  #
  # 3. AT-A3 (PBT layer 1) -- cross-feature isolation property. Hypothesis
  #    @given over (feature_a, feature_b, dispatch_seq) triples where
  #    feature_a != feature_b; asserts records seeded under feature_a are
  #    NEVER visible via `read_records(feature_id=feature_b)`. The property
  #    runs in a sibling pure-function PBT module at layer 1 (per Mandate 9
  #    layer-dependent PBT mode); not expressed as a Gherkin scenario.
  #
  # Atomic-bundle contract (per M51 R-S02D-A): the three ATs in this slice are
  # the test-side commitment. The crafter that takes Bundle A into A_GREEN_ATS
  # MUST migrate the 6 production callsites AND the 16 fixture-fanout rows
  # (per M51 H1 verified empirically 2026-05-25) in ONE atomic commit. A
  # production-only ship without paired fixture migration reproduces the M50
  # cascade-block failure mode.
  #
  # Q3-b mirror -- the slice-02c-A delivery also ships the fixture-side
  # cascade-detector arch test at `tests/des/unit/test_fixture_migration_cascade_detector.py`
  # (NEW; per M51 Q3-b deliverable). The arch test is layer-1 structural
  # invariant (live-grep over `tests/`) and ships WITH this bundle so the
  # F-RECURSIVE-MIGRATION-CASCADE-REGRESSION fixture-side recurrence vector
  # closes mechanically at slice-02c-A GREEN.
  #
  # Mandate-13 boundary (HARD): every production invocation runs in a
  # spawned subprocess; the `from des.adapters.*` import lives ONLY inside
  # the stub script string (child-process scope). The composition.py
  # module-level import set adds ZERO new `des.adapters.*` symbols for
  # slice-02c-A. AT-A3 runs in a sibling PBT module at layer 1 (pure
  # function calls on the production correlation_id helper -- same Mandate-13
  # pattern as slice-01 AT-5).
  #
  # Driving ports exercised by slice-02c-A:
  # - the production `AtCompletionLedger(project_root)` singleton-shape API
  #   writer/reader invoked via 6 per-callsite subprocess stubs (AT-A1) and
  #   via the multi-feature seeded substrate reader (AT-A2).
  # - the production `AtCompletionLedger.read_records(feature_id=...)`
  #   filtered reader (AT-A2 + AT-A3) -- the slice-02b reader extension
  #   shipped this kwarg.

  # AT-A1: regression-pin (parametrize-collapse over 6 production callsites).
  # The post-migration driver writes one representative event through the
  # singleton-shape API at each callsite; the AT asserts the common audit log
  # substrate is present AND the per-feature legacy substrate is absent under
  # the same feature_id. Pre-DELIVER the production source still references
  # the legacy per-feature path at most of these callsites; this AT reds for
  # the right reason (the legacy file gets created somewhere in the call
  # graph, breaking the "only common log present" assertion). Post-A_GREEN
  # the production code matches what the stubs do, the per-feature substrate
  # stays absent, and the AT passes.
  @slice-02c-A @driving_port @real-io @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The post-migration driver for callsite <slice_02c_a_callsite> writes only to the common audit log substrate
    Given a fresh project repository with no atdd_pure audit log yet
    When the slice-02c-A production driver for callsite "<slice_02c_a_callsite>" is invoked once for feature "fix-example"
    Then the common audit log substrate exists under the project repository for feature "fix-example"
    And the per-feature legacy substrate for feature "fix-example" was not created

    Examples: gate-event affinity production callsites (M51 H1 6-callsite bundle)
      | slice_02c_a_callsite                                              |
      | src/des/adapters/drivers/hooks/subagent_stop_handler.py:529       |
      | src/des/adapters/drivers/hooks/subagent_stop_handler.py:738       |
      | src/des/adapters/drivers/hooks/carpaccio_intercept.py:217         |
      | src/des/adapters/drivers/hooks/carpaccio_intercept.py:322         |
      | src/des/cli/reverify_slice_commit.py:199                          |
      | src/des/cli/reverify_slice_commit.py:452                          |

  # AT-A2: forward-pin. Multi-feature substrate seeded via the production
  # singleton-shape writer (two distinct feature_ids); the filtered reader
  # `read_records(feature_id="fix-alpha")` must return EXACTLY the alpha
  # records, NEVER beta records. Pre-DELIVER the production reader honors
  # the kwarg only after slice-02b's reader extension shipped (it did, commit
  # a473593a0) -- if slice-02b's filter regresses, AT-A2 reds; if the
  # singleton-shape writer at this callsite mis-tags records, AT-A2 reds.
  @slice-02c-A @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The filtered reader retrieves only the target feature's records from a multi-feature substrate
    Given a fresh project repository with no atdd_pure audit log yet
    And the common audit log has recorded a CarpaccioGateCleared event for feature "fix-alpha" slice "slice-01"
    And the common audit log has recorded a SliceCommitVerified event for feature "fix-alpha" slice "slice-02"
    And the common audit log has recorded a CarpaccioGateCleared event for feature "fix-beta" slice "slice-01"
    When the operator queries the common audit log filtered by feature "fix-alpha"
    Then the operator sees exactly 2 records for feature "fix-alpha"
    And no record returned for feature "fix-alpha" carries feature_id "fix-beta"
