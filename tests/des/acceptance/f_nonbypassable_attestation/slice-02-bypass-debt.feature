@feature-f-nonbypassable-attestation @slice-02
Feature: A silent --no-verify commit becomes recorded, veto-able debt
  As a developer (or LLM) who issues git commit --no-verify
  I want the bypass to leave an indelible debt record a downstream gate refuses
    to pass over until reconciled
  So that bypass becomes recorded debt, never the ~17 silent skips the incident
    declared "done" over

  # slice-02 of f-nonbypassable-attestation (KPI-2). Closes the silent --no-verify
  # hole. Two driving surfaces:
  #   * CT-3 WRITE: the REAL shipped PreToolUse/Bash spine hook
  #       scripts.hooks.spine_ledger_pre_commit_hook (Layer-3 subprocess), which
  #       fires BEFORE git runs (so --no-verify cannot skip it). Observable = the
  #       SliceCommitBypassed record it appends to the real ledger.
  #   * CT-4 READ: the REAL done-gate verify_deliver_integrity.main (Layer-3
  #       composition). Observable = exit code (INDETERMINATE=4 over unreconciled
  #       debt; PASS=0 once des reverify-slice-commit flips it).
  #
  # DISTINCT FIXTURE PER VERDICT (§22.0 gap): none / unreconciled / reconciled are
  #   three GENUINELY different ledger states, not one fixture with three asserts.
  #
  # CAUSE-DISCRIMINATOR: the unreconciled-debt INDETERMINATE names "SliceCommitBypassed"
  #   so it is told apart from the git-absent INDETERMINATE (slice-01/CT-7 path).
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD the spine hook does NOT parse
  #   --no-verify nor write SliceCommitBypassed, and the done-gate does NOT read
  #   bypass-debt, so the WRITE scenario observes an empty debt set and the READ
  #   scenario clears (exit 0) where INDETERMINATE is expected -- semantic
  #   AssertionErrors. GREEN once DELIVER extends the hook + done-gate.

  @slice-02 @walking_skeleton @driving_port @real-io @us-bypass-as-debt @error @contract-shape:bounded-change
  Scenario: A --no-verify slice-commit leaves an indelible bypass-debt record
    Given a git work-tree with the spine hook in scope
    When the developer commits the slice with git commit --no-verify
    Then a bypass-debt record is written for that slice
    And the bypass is never silent

  @slice-02 @driving_port @real-io @us-bypass-as-debt @contract-shape:bounded-change
  Scenario: A normal verified slice-commit leaves no bypass-debt record
    Given a git work-tree with the spine hook in scope
    When the developer commits the slice with git commit
    Then no bypass-debt record is written

  @slice-02 @driving_port @real-io @us-bypass-as-debt @error @contract-shape:bounded-change
  Scenario: Done over an unreconciled bypass-debt cannot be certified
    Given a complete feature whose ledger carries an unreconciled bypass-debt
    When the developer declares the feature done
    Then the done-gate cannot certify the feature
    And the refusal names the unreconciled bypass-debt

  @slice-02 @driving_port @real-io @us-bypass-as-debt @contract-shape:bounded-change
  Scenario: Reverifying the bypass-debt lets the done-gate clear
    Given a complete feature whose bypass-debt has been reverified
    When the developer declares the feature done
    Then the done-gate clears the feature

  # AT-A5 (self-application, Principle 13): a probe that the bypass-debt EMITTER is
  # actually wired into the real PreToolUse/Bash surface -- not merely that the
  # record type exists. Drives a real LLM-style --no-verify command through the
  # shipped hook subprocess in a real work-tree and asserts the record lands.
  @slice-02 @driving_port @real-io @adapter-integration @us-bypass-as-debt @error @contract-shape:bounded-change
  Scenario: The bypass-debt emitter is wired into the real commit surface
    Given a git work-tree with a no-verify commit ready
    When the developer commits the slice with git commit --no-verify
    Then a bypass-debt record is written for that slice
