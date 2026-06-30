@feature-f-finalize-verify-single-spine
Feature: The finalize integrity gate carries exactly one spine
  As an nWave maintainer carrying the spine surface
  I want des verify-integrity reduced to its atdd_pure body
  So that I finalize every feature through exactly one path
  And no directory can still be special-cased onto the dead classic finalize leg

  # f-finalize-verify-single-spine slice-01 (@walking-skeleton). The REDUCE
  # deletes the classic finalize leg from des verify-integrity: the
  # `workflow.mode == classic` branch, the `resolve_workflow_mode` dispatch,
  # and `--roadmap-only` are removed; `_verify_atdd_pure` becomes the whole
  # body of `main()`. The shipped `des verify-integrity` subcommand surface
  # and the 0/1/2 exit-code contract are preserved byte-for-byte.
  #
  # Driving surface (Mandate-13):
  #   * The walking skeleton drives the INSTALLED spine as a real subprocess
  #     through the shipped `des verify-integrity <dir>` console-script -- the
  #     one terminal-wiring proof that the surviving spine still runs
  #     end-to-end.
  #   * Every other scenario drives the SAME entry IN-PROCESS
  #     (`main(argv)` under redirect_stdout, real FS on tmp_path) -- the
  #     inverted-Driving default (Layer 2/3 composition).
  #
  # RED-readiness (atdd_pure active-RED -- NOT @skip; ADR-025 / ADR-029):
  #   * "still asks for the classic finalize leg" is the RED witness: a
  #     directory with EXPLICIT `workflow.mode: classic` is TODAY routed to the
  #     classic roadmap/execution-log cross-reference (exit 0, "complete DES
  #     traces"). After the REDUCE the dispatch is gone, so it runs the
  #     atdd_pure body and fails-closed with the missing-ledger diagnostic
  #     (exit 1). RED now (asserts the atdd_pure verdict), GREEN after.
  #   * NOTE on the unset case: `resolve_workflow_mode` ALREADY resolves an
  #     absent config to `atdd_pure` (DDD-7), so an unconfigured directory is
  #     ALREADY on the single spine today. The "was already on the single
  #     spine" scenario therefore pins that convergence (GREEN now AND after);
  #     it is the explicit-classic directory whose routing the REDUCE changes.
  #   * The walking skeleton + the exit-0 zero-shipped + exit-1 + exit-2
  #     scenarios are GREEN now and after -- the surviving-spine + cardinality-0
  #     + exit-contract regression fences.
  #
  # C3 ZERO-obligation (ADR-027): the "verified with no shipped slices"
  # scenario exercises the cardinality-0 success path -- a VALID completion
  # ledger whose full feature-end cycle ran but which records NO
  # SliceCommitVerified slice and carries NO `Slice-Id:` commit, so the
  # done-gate's `shipped` set is empty (`frozenset()`) and the verifier emits
  # the plain-text complete-trace verdict (exit 0), NOT the `FeatureReconciled`
  # JSON event of the non-empty-shipped path.
  #
  # The legacy audit-replay reader boundary guard (the Out-of-Scope
  # `PhaseEventParser` do-not-touch fence) is an ARCHITECTURAL contract, not a
  # port-to-port AT, so it lives at
  # `tests/des/unit/domain/test_arch_legacy_audit_replay_boundary.py` rather
  # than importing a domain class at this step boundary (Tier-2 S2).

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A maintainer finalizing the surviving single spine sees the feature verified
    Given a finalized atdd_pure feature whose completion ledger records the full feature-end cycle
    When the maintainer runs the integrity gate on the installed spine
    Then the integrity gate reports the feature verified

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: A finalized feature with zero shipped slices verifies on the single spine
    Given a finalized atdd_pure feature whose completion ledger records the full feature-end cycle but ships no slices
    When the maintainer runs the integrity gate for that feature
    Then the integrity gate reports the feature verified
    And the integrity gate reports a complete completion-ledger trace
    And the integrity gate does not report any reconciled slices

  @slice-01 @driving_port @error @contract-shape:bounded-change
  Scenario: A directory that still asks for the classic finalize leg is verified on the single spine instead
    Given a finalize directory holding only the classic roadmap and execution log
    And the directory still declares the classic finalize mode
    When the maintainer runs the integrity gate for that feature
    Then the integrity gate reports a missing completion ledger
    And the integrity gate does not run the classic execution-log cross-reference

  @slice-01 @driving_port @error @contract-shape:bounded-change
  Scenario: An unconfigured finalize directory was already on the single spine
    Given a finalize directory holding only the classic roadmap and execution log
    And the directory declares no finalize mode at all
    When the maintainer runs the integrity gate for that feature
    Then the integrity gate reports a missing completion ledger
    And the integrity gate does not run the classic execution-log cross-reference

  @slice-01 @driving_port @error @contract-shape:bounded-change
  Scenario: Finalizing with no target still fails with the structural usage error
    Given the maintainer names no finalize directory
    When the maintainer runs the integrity gate with no target
    Then the integrity gate reports a structural usage error
