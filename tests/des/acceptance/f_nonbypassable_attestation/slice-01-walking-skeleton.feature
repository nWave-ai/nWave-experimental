@feature-f-nonbypassable-attestation @slice-01
Feature: A developer cannot declare a feature done unless the feature-end cycle ran
  As a developer (human or LLM) declaring a feature done
  I want the done state to be a READ of the ledger, not a self-report
  So that "I never ran feature-end" mechanically blocks progress instead of
    silently passing -- the exact 0/7 hole the flow-v2 incident exploited

  # slice-01 of f-nonbypassable-attestation (walking skeleton, KPI-1 + KPI-3).
  # Thinnest end-to-end vertical: the REAL done-gate reads the REAL ledger and
  # vetoes on absence of the required feature-end records (incl. the NEW
  # full-suite leg). Reuses verify_deliver_integrity.main verbatim as the SUT.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition): the real done-gate entry
  #   point  verify_deliver_integrity.main(["--repo", root, "--feature-id", id])
  #   observable = the process EXIT CODE (GateVerdict projection: 0 PASS / 1 FAIL
  #   / 4 INDETERMINATE) + the machine-readable record names it prints.
  #
  # DORMANT-SEAM (D11 / CT-5): the NET-NEW load-bearing seam this slice declares
  #   is FullSuiteLegRan becoming `required`. The done-gate (the REAL entry point)
  #   must REFUSE when FullSuiteLegRan is absent -- that is the witnessing AT for
  #   the seam, driven through the real entry point + asserting the exit-code
  #   observable effect, not a claim that the emitter "exists".
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD the `required` set does NOT
  #   contain FullSuiteLegRan, so the "complete-except-full-suite" fixture
  #   currently CLEARS (exit 0) where this scenario expects a REFUSAL -- a
  #   semantic AssertionError. GREEN once DELIVER adds FullSuiteLegRan to the
  #   `required` set in BOTH SSOTs + emits it from run_feature_end_cycle.

  @slice-01 @walking_skeleton @driving_port @real-io @us-attested-done @contract-shape:unbounded-preservation
  Scenario: Declaring done with no feature-end cycle is refused (the incident)
    Given a project where the feature-end cycle never ran
    When the developer declares the feature done
    Then the done-gate refuses with a definite failure
    And the refusal names the missing feature-end cycle

  @slice-01 @driving_port @real-io @us-attested-done @contract-shape:unbounded-preservation
  Scenario: Declaring done with every required record present clears
    Given a project whose feature-end ledger carries every required record
    When the developer declares the feature done
    Then the done-gate clears the feature

  @slice-01 @driving_port @real-io @us-attested-done @error @contract-shape:unbounded-preservation
  Scenario: Declaring done with the full-suite leg unrun is refused
    Given a project whose ledger carries every required record except the full-suite leg
    When the developer declares the feature done
    Then the done-gate refuses with a definite failure
    And the refusal names the missing full-suite leg

  # CT-2: the done-gate is auto-fired on the TERMINAL declare-done action via a
  # harness-neutral backstop (DDD-2), not only on a manual CLI run nor only on the
  # F_FINAL_REVIEW SubagentStop return the incident's hand-dispatch never reached.
  @slice-01 @driving_port @real-io @us-attested-done @error @contract-shape:unbounded-preservation
  Scenario: Declaring done on the terminal action auto-fires the done-gate
    Given a project where the feature-end cycle never ran
    When the developer declares the feature done on the terminal action
    Then the done-gate refuses with a definite failure
    And the terminal action auto-fired the done-gate
