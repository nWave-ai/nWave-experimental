Feature: des-init-log respects the project's workflow mode
  As an nWave operator delivering a feature
  I want des-init-log to refuse creating an execution log for ATDD-pure features
  So that the roadmap-free, execution-log-free spine (ADR-028) is honoured
  And classic features keep their execution log exactly as before

  # ADR-028 D4.1 / slice 1 of 6. Regression ATs: FAIL on master
  # (des-init-log has no mode-awareness), PASS once slice 1 lands.
  #
  # SUT workflow-mode state model (C2), revised by DDD-7 (slice-03
  # mode-resolution SSOT):
  #   workflow mode is resolved from .nwave/config.yaml key `workflow.mode`.
  #   States: {atdd_pure, unset, no-config-file} -> refuse ; {classic} -> create.
  #   DDD-7 flipped the absent-key default from classic to atdd_pure: an
  #   unconfigured project (unset / no config file) is now an atdd_pure spine
  #   project, so des-init-log refuses for it exactly as for an explicit
  #   atdd_pure. Only an EXPLICIT `workflow.mode: classic` reaches the create
  #   path. The refuse early-exit is the only state transition this feature
  #   introduces.
  #
  # Driving port: the des-init-log CLI, invoked via its argv entry point
  # IN-PROCESS (init_log_main(argv) under redirect_stdout). Layer 2 (component:
  # driving port invoked directly, real filesystem on tmp_path) -> example-only,
  # no PBT (Mandate 9/11). The `des` kebab-dispatch routing + `sys.exit(main())`
  # exit-code marshalling are covered GENERICALLY (real subprocess, all 16
  # subcommands incl. init-log) by tests/des/acceptance/single_entry_point/
  # slice_02_all_subcommands_wired -- so this suite is honestly in-process and
  # does NOT re-prove the dispatch seam (slice-10 ice-cream-cone removal: the
  # per-CLI real-subprocess scenario TD-45 was O(N) redundant with that generic
  # parametrize-collapsed dispatch coverage).

  @component @driving_port @contract-shape:unbounded-preservation
  Scenario Outline: An unconfigured or ATDD-pure feature has its execution-log creation refused
    Given a deliver project directory for feature "atdd-pure-demo"
    And the project workflow mode is "<workflow_mode>"
    When the operator runs des-init-log for that feature
    Then des-init-log refuses with a non-zero exit code
    And the refusal message explains ATDD-pure is execution-log-free
    And no execution log is created in the project directory

    Examples: explicit atdd_pure and the DDD-7 absent-key default (unset)
      | workflow_mode |
      | atdd_pure     |
      | unset         |

  @component @driving_port @contract-shape:bounded-change
  # Converted, not deleted. This scenario used to pin "classic succeeds"; with
  # classic removed there is no longer an authority that can grant it, and the
  # invariant worth protecting is the OPPOSITE one -- that a project still
  # carrying the removed selector is refused rather than quietly served. A
  # deleted scenario would have left that refusal unpinned.
  Scenario: a project still carrying the removed classic selector is refused, not served
    Given a deliver project directory for feature "classic-demo"
    And the project workflow mode is "classic"
    When the operator runs des-init-log for that feature
    Then des-init-log refuses with a non-zero exit code
    And the refusal names the removed classic selector and the migration route
    And no execution log is created in the project directory
