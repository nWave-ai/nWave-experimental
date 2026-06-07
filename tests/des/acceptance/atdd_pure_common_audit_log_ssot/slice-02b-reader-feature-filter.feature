@feature-fix-atdd-pure-common-audit-log-ssot
Feature: Aggregate readers expose a feature filter so singleton-shape callers stay feature-scoped
  As an nWave framework operator
  I want the audit-log aggregate readers (verified slices, feature-end events, environmental-e2e events)
    to accept an optional feature filter
  So that callers migrated to the singleton-shape ledger continue to observe
    only the records for the feature they verify,
    and the feature-end / verify-deliver-integrity contract is preserved
    end-to-end across the slice-02 caller-migration cascade

  # carpaccio slice-02b: cascade-regression mitigation for slice-02. The
  # slice-02 caller-migration unblocks 11 caller files moving from the
  # legacy per-feature `AtCompletionLedger(feature_id, project_root)`
  # construction to the singleton-shape `AtCompletionLedger(project_root)`
  # construction. The migration cascades through the aggregate reader API:
  # `verified_slices()`, `feature_end_events()`, `environmental_e2e_events()`,
  # `walking_skeleton_events()`, and `coverage_map_touchpoint_events()` ALL
  # iterate over `self.read_records()` WITHOUT a feature filter -- so the
  # singleton-shape constructor returns the union across every feature in
  # the substrate, breaking the per-feature isolation the legacy shape
  # provided implicitly via filename scoping.
  #
  # Slice-02b adds an optional `feature_id=` keyword-only parameter to every
  # affected reader (kw-only to surface positional-drift at type-check time).
  # When `feature_id=None` the reader retains its aggregate semantics
  # (backward-compat for any future cross-feature audit query). When
  # `feature_id="X"` the reader returns ONLY records whose `feature_id == X`.
  #
  # M36 amendment #2 (cascade coverage gap): ATs cover ALL FIVE aggregate
  # readers, not three. The original AT set parametrize-collapsed over the
  # three readers consumed by `verify_deliver_integrity._verify_atdd_pure`
  # and deferred walking_skeleton_events + coverage_map_touchpoint_events to
  # "lock-step crafter PR" -- creating a regression risk where a crafter
  # could mechanically drop the kwarg on the deferred two without any AT
  # failing. Five-reader coverage closes the class.
  #
  # Empirical anchor: F-DELIVER-INTEGRITY-LEDGER-TARGETING regression test
  # (`tests/des/unit/cli/test_verify_deliver_integrity.py:175-260`) reds
  # post-slice-02 caller migration when `verify_deliver_integrity._verify_
  # atdd_pure` reads `AtCompletionLedger(project_root=project_dir).verified
  # _slices()` without a filter -- it returns slices from EVERY feature, so
  # the target-feature-isolation contract collapses to a false-PASS.
  #
  # Layer 2/3 mix:
  # - AT-1 / AT-2: in-memory acceptance (subprocess-free) of the reader API
  #   driven through the production composition root. Layer 3 substrate is
  #   a tmp_path-scoped `.nwave/audit/atdd-pure-events.jsonl` populated via
  #   the writer (real I/O); the reader invocation is in-process. Example
  #   only (Mandate 9/11) -- sad-paths enumerated, not PBT-generated.
  # - AT-3: regression-pin against the post-migration `verify_deliver_
  #   integrity` CLI. Layer 3 real-I/O subprocess invocation.
  #
  # Driving ports exercised:
  # - `AtCompletionLedger(project_root).verified_slices(feature_id=...)`
  #   (new kw-only parameter; same contract for the four sibling readers).
  # - `des verify-integrity <repo> --feature-id <id>` CLI subprocess.
  #
  # Universe (Mandate 8) per scenario: the port-exposed slice/event sets
  # returned by the readers, AND the CLI exit code + stdout. No internal
  # field is observed; the assertions read frozenset cardinality + element
  # membership only.

  # AT-1: parametrize-collapse over FIVE aggregate readers (M36 amendment
  # #2: extended from three to five to close the cascade coverage gap; the
  # remaining two readers walking_skeleton_events + coverage_map_touchpoint_
  # events would otherwise have silently regressed). Given the common log
  # carries records for BOTH feature "alpha" (one event each of three kinds)
  # AND feature "beta" (one event each of the same three kinds), the named
  # reader called with `feature_id="alpha"` returns the alpha-only subset,
  # NOT the union. Verifies the new filter parameter preserves per-feature
  # isolation across all five aggregate readers the singleton-shape API
  # exposes.
  @slice-02b @driving_port @real-io @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The aggregate reader <reader_method> with feature filter returns only the named feature records
    Given a fresh project repository with no atdd_pure audit log yet
    And the common audit log has recorded a SliceCommitVerified event for feature "alpha" slice "slice-01"
    And the common audit log has recorded a WalkingSkeletonGateRan event for feature "alpha" slice "feature-scope"
    And the common audit log has recorded a EnvironmentalE2eGateRan event for feature "alpha" slice "feature-scope"
    And the common audit log has recorded a SliceCommitVerified event for feature "beta" slice "slice-01"
    And the common audit log has recorded a WalkingSkeletonGateRan event for feature "beta" slice "feature-scope"
    And the common audit log has recorded a EnvironmentalE2eGateRan event for feature "beta" slice "feature-scope"
    When the aggregate reader <reader_method> is invoked with feature filter "alpha"
    Then the reader returns the alpha-only subset for <reader_method>
    And the reader does not return any beta records

    Examples:
      | reader_method                  |
      | verified_slices                |
      | feature_end_events             |
      | environmental_e2e_events       |
      | walking_skeleton_events        |
      | coverage_map_touchpoint_events |

  # AT-2: backward-compat regression-pin. Same FIVE aggregate readers
  # (M36 amendment #2 extension), same multi-feature substrate, but called
  # WITHOUT the feature filter (the singleton-shape API surface that
  # existed before slice-02b). The reader MUST continue to return the
  # aggregate across both features -- a cross-feature audit query is a
  # legitimate use-case that future consumers (e.g. PRR scorecard rollup)
  # depend on. Verifies the new parameter is genuinely optional, not a
  # forced-migration.
  @slice-02b @driving_port @real-io @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The aggregate reader <reader_method> without filter returns the cross-feature aggregate
    Given a fresh project repository with no atdd_pure audit log yet
    And the common audit log has recorded a SliceCommitVerified event for feature "alpha" slice "slice-01"
    And the common audit log has recorded a WalkingSkeletonGateRan event for feature "alpha" slice "feature-scope"
    And the common audit log has recorded a EnvironmentalE2eGateRan event for feature "alpha" slice "feature-scope"
    And the common audit log has recorded a SliceCommitVerified event for feature "beta" slice "slice-01"
    And the common audit log has recorded a WalkingSkeletonGateRan event for feature "beta" slice "feature-scope"
    And the common audit log has recorded a EnvironmentalE2eGateRan event for feature "beta" slice "feature-scope"
    When the aggregate reader <reader_method> is invoked without a feature filter
    Then the reader returns the cross-feature aggregate for <reader_method>

    Examples:
      | reader_method                  |
      | verified_slices                |
      | feature_end_events             |
      | environmental_e2e_events       |
      | walking_skeleton_events        |
      | coverage_map_touchpoint_events |

  # AT-3: F-DELIVER-INTEGRITY-LEDGER-TARGETING end-to-end regression-pin.
  # Two features coexist in the singleton-shape common audit log:
  # "aaa-shipped-feature" has a COMPLETE feature-end cycle (all six
  # required heartbeats + verified slice); "zzz-under-test" has only a
  # SliceCommitVerified event for slice-01 (no feature-end cycle ran).
  # The verify-integrity CLI invoked with `--feature-id zzz-under-test`
  # MUST exit non-zero (the target feature is incomplete) and the verdict
  # MUST name the target feature, not silently verify the alphabetically
  # first feature. Closes the cascade-regression class at the CLI surface:
  # the slice-02 migration cannot land until the reader API supports the
  # feature filter that the CLI now relies on.
  @slice-02b @driving_port @real-io @contract-shape:bounded-change
  Scenario: The verify-integrity CLI targets the named feature against the singleton-shape ledger
    Given a fresh project repository with no atdd_pure audit log yet
    And the common audit log holds a complete feature-end cycle for feature "aaa-shipped-feature"
    And the common audit log has recorded a SliceCommitVerified event for feature "zzz-under-test" slice "slice-01"
    When the verify-integrity CLI is invoked on the project for feature "zzz-under-test"
    Then the CLI exits non-zero against the target feature
    And the CLI verdict names the target feature "zzz-under-test"
