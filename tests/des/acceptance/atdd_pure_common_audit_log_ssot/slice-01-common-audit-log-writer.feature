@feature-fix-atdd-pure-common-audit-log-ssot
Feature: A single common atdd_pure audit log preserves M7 integrity and surfaces operator-readable repair diagnostics
  As an nWave framework operator
  I want every atdd_pure spine event written to a single common audit log
    keyed by feature, slice and a derived correlation identifier
  So that cross-feature audit queries become trivial, integrity violations
    surface with a repair-doc-linked diagnostic, and per-feature ledger files
    can never be reintroduced by accident

  # carpaccio slice-01 (walking-skeleton): establishes the common-log writer +
  # reader API + the singleton-shape `AtCompletionLedger(project_root)` +
  # correlation_id derivation + the `LedgerIntegrityViolation` operator-readable
  # diagnostic surface co-shipped with `docs/operations/repair-instructions.md`
  # + the per-feature-path arch test gate (AMEND #1 ratification gate-blocker).
  #
  # Layer 3 (subprocess / FS acceptance against real production code):
  # examples drive the production `AtCompletionLedger` writer/reader and the
  # production `des verify-integrity` CLI through the driving port boundary
  # (composition.py calls `AtCompletionLedger(project_root)` and
  # `subprocess.run(["des", "verify-integrity", ...])`). Example-only per
  # Mandate 9/11 EXCEPT the correlation_id collision PBT which runs at layer 1
  # (pure-function determinism property — Mandate 9 layer-1 PBT allowed).
  #
  # Driving ports:
  # - `AtCompletionLedger(project_root)` — production composition-root API.
  # - `des verify-integrity <repo> --feature-id <id>` — production CLI subprocess.
  # - `pytest tests/build/test_no_per_feature_atdd_ledger_writes.py` — arch-test
  #   gate invoked as a subprocess (pytest is the driving adapter).

  # AT-1: the common-log writer API — `AtCompletionLedger(project_root)` accepts
  # per-call `feature_id=` kw-only and appends a single line to
  # `.nwave/audit/atdd-pure-events.jsonl`. The appended record carries the M7
  # `seq` + `record_hash` AND the new `correlation_id` derived from
  # `(feature_id, slice_id, dispatch_seq)`. The same record is then readable
  # via `read_records(feature_id=...)` — filter-by-feature.
  @slice-01 @walking_skeleton @driving_port @real-io @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The common audit log writer appends one record under the singleton-shape API for a <event_kind> event
    Given a fresh project repository with no atdd_pure audit log yet
    When the common audit log writer appends a <event_kind> event for feature "fix-example" slice "slice-01"
    Then the common audit log contains exactly one record for feature "fix-example"
    And that record carries event "<event_kind>" slice "slice-01" and a derived correlation identifier

    Examples:
      | event_kind                      |
      | CarpaccioGateCleared            |
      | SliceCommitVerified             |
      | WalkingSkeletonGateRan          |

  # AT-2: the reader filter — given multiple features sharing the common log,
  # `read_records(feature_id=...)` returns ONLY that feature's records. Cross-
  # feature isolation is preserved at read time even though the substrate is
  # one file. This is the compounding capability the SSOT consolidation
  # delivers (per design D3).
  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The common audit log reader filters by feature identifier
    Given a fresh project repository with no atdd_pure audit log yet
    And the common audit log has recorded a CarpaccioGateCleared event for feature "fix-alpha" slice "slice-01"
    And the common audit log has recorded a CarpaccioGateCleared event for feature "fix-beta" slice "slice-01"
    When the operator queries the common audit log filtered by feature "fix-alpha"
    Then exactly one record is returned
    And that record carries feature identifier "fix-alpha"

  # AT-3: M7 fail-closed on a tampered record — a hand-edit that flips a
  # verdict field surfaces as a `LedgerIntegrityViolation` with the `detail`
  # classifier AND the production `des verify-integrity` CLI reports the
  # violation with the line number AND directs the operator to the repair
  # instructions doc. This is the operator-recoverable diagnostic surface
  # (AMEND #1 ratification gate-blocker, design RES-2 perturbation 2).
  @slice-01 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: The verify-integrity CLI surfaces a tampered record as a repair-doc-linked diagnostic
    Given a fresh project repository with no atdd_pure audit log yet
    And the common audit log has recorded a CarpaccioGateCleared event for feature "fix-example" slice "slice-01"
    And the recorded record has been tampered with a hand-edit that breaks its record hash
    When the verify-integrity CLI is invoked on the project for feature "fix-example"
    Then the CLI exits with an integrity-violation verdict
    And the verdict names the violation class as "hash-mismatch"
    And the verdict names the offending line number
    And the verdict directs the operator to the repair instructions

  # AT-4: the arch-test ban — reintroducing the per-feature path pattern in
  # `src/` or `scripts/` causes the build-tier arch test to fail. The arch
  # test is invoked as a subprocess (pytest is the driving adapter). The
  # `_archive/` subdirectory is exempt from the ban (post-slice-03 archive
  # path stays readable). This gate makes the regression-vector mechanically
  # impossible per `feedback_gate_or_residue_policy_2026_05_21`.
  @slice-01 @driving_port @real-io @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The per-feature-ledger arch test gate verdict for caller scenario <caller_scenario>
    Given a temporary source tree seeded with a caller in the <caller_scenario> shape
    When the per-feature ledger ban arch test is invoked on the temporary source tree
    Then the arch test verdict is <arch_test_verdict>

    Examples:
      | caller_scenario                                              | arch_test_verdict |
      | a caller that writes a path under the per-feature pattern    | fail              |
      | a caller that writes a path under the archive subdirectory   | pass              |
      | a caller that uses only the common audit log path            | pass              |

  # AT-5 — the correlation_id derivation property (deterministic + collision-
  # free over realistic operational inputs) is a Mandate 9 layer-1 PBT. The
  # `Property:` framing lives outside this `.feature` (Gherkin's example-shape
  # would misrepresent the Hypothesis @given semantics); the executable spec
  # is the sibling
  # `steps/test_slice_01_correlation_id_property.py` Hypothesis module. The
  # human-readable contract is preserved here as a documentary anchor.
  #
  # Property (documentary, see PBT module for executable spec):
  #   For every (feature_id, slice_id, dispatch_seq) triple in the realistic
  #   operational input space:
  #   (1) determinism — two derivations of the correlation identifier return
  #       the same 16-hex digest;
  #   (2) collision-freedom — no two distinct triples collide on the digest
  #       within 10000 sampled triples (birthday-bound floor for the 64-bit
  #       truncated SHA-256 space).
