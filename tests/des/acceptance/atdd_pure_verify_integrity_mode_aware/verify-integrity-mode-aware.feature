Feature: des-verify-integrity respects the project's workflow mode
  As an nWave operator finalising a feature
  I want des-verify-integrity to verify the AT-completion ledger for ATDD-pure features
  So that a roadmap-free feature gets a correct integrity verdict
  And classic features keep their existing 0/1/2 exit-code contract unchanged

  # ADR-028 D4.2 / slice-02 of the atdd-pure-roadmap-free-rollout.
  # Regression ATs: FAIL on master (des-verify-integrity has no mode-awareness
  # -- it exits 2 the instant roadmap.json is absent, before any mode check),
  # PASS once slice-02 lands.
  #
  # D4.2 has FOUR contract limbs, one scenario group each:
  #   1. atdd_pure + complete ledger (roadmap absent or leftover) -> verified
  #   2. atdd_pure + absent ledger   -> structured diagnostic, exit 1, no crash
  #   3. atdd_pure + --roadmap-only  -> the flag is a no-op, same verified verdict
  #   4. classic / unset             -> the existing 0/1/2 contract, zero regression
  #
  # SUT workflow-mode state model (C2), revised by DDD-7 (slice-03
  # mode-resolution SSOT):
  #   workflow mode is resolved from {project_dir}/.nwave/config.yaml key
  #   `workflow.mode` -- the SAME path slice-01's des-init-log uses.
  #   States: {atdd_pure, unset, no-config-file} -> validate the AT-completion
  #           ledger ; {classic} -> the existing roadmap.json +
  #           execution-log.json cross-reference, byte-for-byte unchanged.
  #   DDD-7 flipped the absent-key default from classic to atdd_pure: an
  #   unconfigured project (unset / no config file) now resolves atdd_pure, so
  #   the verifier checks its AT-completion ledger rather than the classic
  #   roadmap/log cross-reference. Only an EXPLICIT `workflow.mode: classic`
  #   takes the classic limb.
  #
  # Driving port: the des-verify-integrity CLI, invoked via its argv entry
  # point IN-PROCESS (verify_integrity_main(argv) under redirect_stdout).
  # Layer 2 (component: driving port invoked directly, real filesystem on
  # tmp_path) -> example-only, no PBT (Mandate 9/11). The verifier has a
  # pure-read contract: the one state-observing step asserts via
  # assert_state_delta that NO project file is mutated (Mandate 8).
  #
  # The `des` kebab-dispatch routing + `sys.exit(main())` exit-code marshalling
  # are covered GENERICALLY (real subprocess, all 16 subcommands incl.
  # verify-integrity) by tests/des/acceptance/single_entry_point/
  # slice_02_all_subcommands_wired -- so this suite is honestly in-process and
  # does NOT re-prove the dispatch seam (slice-10 ice-cream-cone removal: the
  # per-CLI real-subprocess scenario TD-41 was O(N) redundant with that generic
  # parametrize-collapsed dispatch coverage).

  @component @driving_port @contract-shape:bounded-change
  Scenario Outline: An ATDD-pure feature with a complete ledger is verified regardless of any leftover roadmap
    Given a deliver project directory for feature "atdd-pure-demo"
    And the project workflow mode is "atdd_pure"
    And the AT-completion ledger is present with every slice shipped
    And a leftover roadmap is "<leftover_roadmap>" in the project directory
    When the operator runs des-verify-integrity for that feature
    Then des-verify-integrity reports the feature verified
    And the leftover roadmap is treated as "<roadmap_treatment>"

    Examples:
      | leftover_roadmap | roadmap_treatment            |
      | absent           | not required and not created |
      | present          | reported as a warning        |

  @component @driving_port @contract-shape:bounded-change
  Scenario: An ATDD-pure feature with no AT-completion ledger gets a structured diagnostic, not a crash
    Given a deliver project directory for feature "atdd-pure-demo"
    And the project workflow mode is "atdd_pure"
    And the AT-completion ledger is absent
    When the operator runs des-verify-integrity for that feature
    Then des-verify-integrity reports an integrity violation
    And the diagnostic message names the missing AT-completion ledger
    And des-verify-integrity does not crash

  # f-finalize-verify-single-spine slice-01: the "--roadmap-only treats the flag
  # as a no-op" scenario and the classic-mode Examples block were removed -- they
  # pinned the now-deleted classic finalize leg (the `--roadmap-only` mode + the
  # `workflow.mode == classic` roadmap/execution-log dispatch). The surviving
  # unset row pins the DDD-7 absent-key default (unset resolves atdd_pure).

  @component @driving_port @contract-shape:bounded-change
  Scenario Outline: An unset-mode feature resolves atdd_pure and is verified against its ledger
    Given a deliver project directory for feature "classic-demo"
    And the project workflow mode is "<workflow_mode>"
    And a classic deliver project with "<trace_completeness>"
    When the operator runs des-verify-integrity for that feature
    Then des-verify-integrity reports "<expected_verdict>"

    Examples: unset mode resolves atdd_pure (DDD-7 absent-key default)
      # DDD-7: an unset workflow.mode now resolves atdd_pure, so the verifier
      # checks the AT-completion ledger -- which this classic-shaped fixture
      # never provisions (it writes roadmap.json + execution-log.json only).
      # The absent ledger is an integrity violation. This pins the DDD-7
      # default flip: unset is no longer the classic no-regression alias.
      | workflow_mode | trace_completeness | expected_verdict       |
      | unset         | complete traces    | an integrity violation |
