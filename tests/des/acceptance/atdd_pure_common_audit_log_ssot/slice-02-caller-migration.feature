@feature-fix-atdd-pure-common-audit-log-ssot
Feature: All AtCompletionLedger callers migrate to the singleton-shape common audit log
  As an nWave framework operator
  I want every existing caller of the audit ledger
    rewired to the singleton-shape common audit log
  So that no caller can ever again write to the per-feature path,
    the SSOT consolidation gate is mechanically enforceable across the codebase,
    and the M7 integrity contract continues to hold under the new construction shape

  # carpaccio slice-02: migrate the 11 grep-verified caller files
  # (8 src/ + 3 scripts/) from the legacy per-feature
  # `AtCompletionLedger(feature_id, project_root)` instance signature to the
  # singleton-shape `AtCompletionLedger(project_root)` + per-call `feature_id=`
  # kw-only writer. Slice-01 shipped the dual-shape API + the arch-test gate
  # (currently in-tree-skipped per `--src-roots` flag); slice-02 makes the
  # in-tree invocation of that gate exit zero against the real `src/` and
  # `scripts/` trees, decommissioning the per-feature path entirely.
  #
  # Layer 3 (subprocess / FS acceptance against real production code):
  # ATs drive the migrated callers through their PRODUCTION driving ports --
  # CLI subprocess, hook payload subprocess, or the build-tier arch test
  # subprocess. Example-only per Mandate 9/11 (no PBT at layer 3).
  #
  # Driving ports exercised by this slice:
  # - the production CLIs and hook entry points of the 11 migrated callers
  #   (subprocess invocations) — substrate observation is the
  #   `.nwave/audit/atdd-pure-events.jsonl` common log file under tmp_path.
  # - `pytest tests/build/test_no_per_feature_atdd_ledger_writes.py` against
  #   the in-tree `src/` + `scripts/` roots (subprocess) — verdict observation.
  # - `AtCompletionLedger(feature_id, project_root)` legacy positional shape
  #   read/write round-trip (in-process call from composition root) — used
  #   ONLY by the regression-pin AT to confirm backward-compat preservation
  #   during the migration cutover window.

  # AT-1: every one of the 11 grep-verified caller files, when invoked through
  # its production driving port, writes its audit record to the common audit
  # log path (`.nwave/audit/atdd-pure-events.jsonl`) AND does NOT touch the
  # per-feature path (`.nwave/telemetry/atdd-pure/{feature_id}.jsonl`). The
  # observable contract per caller is the substrate location of the appended
  # record(s), measured AFTER one production driving-port invocation against
  # a fresh tmp-repo. Parametrize-collapse over all 11 callers — one row per
  # caller, same Given/When/Then shape.
  @slice-02 @driving_port @real-io @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The migrated caller <caller_id> writes to the common audit log and not the per-feature path
    Given a fresh project repository with no atdd_pure audit log yet
    When the production driving port for caller <caller_id> is invoked once for feature "fix-example"
    Then the common audit log file exists under the project repository
    And the per-feature ledger file for feature "fix-example" was not created

    Examples:
      | caller_id                                                                |
      | src/des/adapters/drivers/hooks/subagent_stop_handler.py                  |
      | src/des/cli/reverify_slice_commit.py                                     |
      | src/des/cli/verify_deliver_integrity.py                                  |
      | src/des/cli/verify_slice_commit_completeness.py                          |
      | src/des/cli/walking_skeleton_gate.py                                     |
      | src/des/domain/conversion_planner.py                                     |
      | src/des/adapters/driven/ledger/coverage_map_signoff_writer.py            |
      | src/des/adapters/drivers/hooks/carpaccio_intercept.py                    |
      | scripts/cli/verify_coverage_map.py                                       |
      | scripts/hooks/verify_slice_ledger_record.py                              |
      | scripts/cli/at_review_verdict.py                                         |

  # AT-2: post-migration, the per-feature-ledger ban arch test invoked WITHOUT
  # `--src-roots` (default scan of the in-tree `src/` + `scripts/` roots)
  # exits 0 with zero violations. Before slice-02, the arch test skips itself
  # in default mode (the slice-01 test body explicitly pytest.skip's when
  # `--src-roots` is None to preserve the green bar while the 11 pre-existing
  # callers still write the per-feature path). Slice-02 LIFTS the in-tree skip
  # by migrating every caller — the verdict observation is the boolean
  # "arch test exits 0 with zero violations under default in-tree scan".
  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The per-feature ledger ban arch test passes against the in-tree src and scripts roots
    Given the in-tree source roots src and scripts contain only migrated callers
    When the per-feature ledger ban arch test is invoked without a source-roots override
    Then the arch test verdict is pass
    And the arch test reports zero forbidden per-feature path literals

  # AT-3: regression-pin — the legacy per-feature `AtCompletionLedger(feature_id,
  # project_root)` positional shape continues to read AND write a per-feature
  # JSONL substrate (this is the dual-shape contract D3 commits to; the legacy
  # shape is preserved by construction until a future epic removes it). This
  # AT pins the contract so the slice-02 migration cannot regress
  # backward-compat: a future refactor that drops the legacy shape would fail
  # this AT immediately. Observable contract = round-trip semantic equality
  # of the appended record under the legacy shape against the per-feature
  # path.
  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The legacy per-feature ledger shape remains read-write functional under tmp_path
    Given a fresh project repository with no atdd_pure audit log yet
    When the legacy per-feature ledger appends a CarpaccioGateCleared event for feature "fix-legacy" slice "slice-01"
    Then the per-feature ledger file for feature "fix-legacy" exists under the project repository
    And the legacy per-feature ledger round-trip returns exactly one record carrying event "CarpaccioGateCleared"
