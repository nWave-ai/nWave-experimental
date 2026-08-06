Feature: des-verify-integrity verifies the ATDD-pure delivery record
  As an nWave operator finalising a feature
  I want des-verify-integrity to verify the AT-completion ledger for ATDD-pure features
  So that a feature's ledger and feature-end evidence determine its verdict
  #
  # Driving port: the des-verify-integrity CLI, invoked via its argv entry
  # point IN-PROCESS (verify_integrity_main(argv) under redirect_stdout).
  # Layer 2 (component: driving port invoked directly, real filesystem on
  # tmp_path) -> example-only, no PBT (Mandate 9/11). The verifier has a
  # pure-read contract: the one state-observing step asserts via
  # assert_state_delta that NO project file is mutated (Mandate 8).
  #
  # The `des` kebab-dispatch routing + `sys.exit(main())` exit-code marshalling
  # are covered generically by the CLI dispatcher contract, so this suite is
  # honestly in-process and
  # does NOT re-prove the dispatch seam (slice-10 ice-cream-cone removal: the
  # per-CLI real-subprocess scenario TD-41 was O(N) redundant with that generic
  # parametrize-collapsed dispatch coverage).

  @component @driving_port @contract-shape:bounded-change
  Scenario: An ATDD-pure feature with a complete ledger is verified
    Given a deliver project directory for feature "atdd-pure-demo"
    And the project workflow mode is "atdd_pure"
    And the AT-completion ledger is present with every slice shipped
    When the operator runs des-verify-integrity for that feature
    Then des-verify-integrity reports the feature verified

  @component @driving_port @contract-shape:bounded-change
  Scenario: An ATDD-pure feature with no AT-completion ledger gets a structured diagnostic, not a crash
    Given a deliver project directory for feature "atdd-pure-demo"
    And the project workflow mode is "atdd_pure"
    And the AT-completion ledger is absent
    When the operator runs des-verify-integrity for that feature
    Then des-verify-integrity reports an integrity violation
    And the diagnostic message names the missing AT-completion ledger
    And des-verify-integrity does not crash
