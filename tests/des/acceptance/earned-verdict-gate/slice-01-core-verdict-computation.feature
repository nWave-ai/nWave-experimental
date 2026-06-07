@feature-oss-earned-verdict-gate
Feature: The earned-verdict gate computes an honest verdict over two test runs
  As an nWave framework developer trusting a green acceptance test
  I want the target-blind CORE to compare a baseline run against a perturbed
    run and rule whether the green was EARNED -- causally bound to the thing it
    asserts -- or merely held against broken code
  So that a green that survives breaking its own dependency is mechanically
    exposed as theater, and the spec-to-code drift becomes impossible to fake

  # carpaccio slice-01 (DISCUSS [REF] Slice Plan). THE walking skeleton: the
  # deterministic CORE is the smallest self-contained end-to-end value -- pure,
  # target-blind, driving-port-testable. Runner / seam-injection / hook follow
  # in later slices. Exactly THREE ATs (carpaccio_slice_max=3), one per verdict
  # class. AT-1 (GREEN) and AT-3 (ABSTAIN) are Scenario Outlines because each
  # verdict rule is a DISJUNCTION -- every limb of the OR is a distinct
  # decision-table branch and gets its own Examples row (HARD INVARIANT 4).
  #
  # CONTRACT SOURCE: authored against the two FROZEN cross-tree contracts
  #   nWave/schemas/nwave.test_result.v1.schema.json   (the RUN -- input)
  #   nWave/schemas/nwave.earned_verdict.v1.schema.json (the VERDICT -- output)
  # Deterministic rule (CORE-only, NEVER LLM-judged):
  #   GREEN   <=> baseline.passed>0 AND baseline.failed==0
  #              AND (perturbed.failed>0 OR perturbed.exit_code!=0)   [flipped = honest]
  #   RED     <=> baseline green AND perturbed STILL green            [theater]
  #   ABSTAIN <=> baseline NOT green (failed>0 OR passed==0)          [fail-safe]
  #
  # Driving port (Mandate-13): the `earned-verdict` CLI invoked as a
  # `python -m des.cli.earned_verdict` subprocess, reading two
  # `nwave.test_result.v1` JSON inputs and emitting one `nwave.earned_verdict.v1`
  # JSON. ZERO direct domain import. Layer 3 (subprocess + JSON assertion):
  # example-only, no PBT machinery (Mandate 9/11); the emitted verdict's
  # port-exposed fields are the universe (Mandate 8).
  #
  # target-blind: every scenario stages runs by their observable count/exit
  # shape only. No language or runner literal appears in any expected CORE
  # behaviour -- the verdict is identical for any runner string on the envelope.

  # AT-1 -- WALKING SKELETON (verdict class GREEN): the baseline green was
  # EARNED because the perturbed run flipped. Two Examples rows witness the two
  # limbs of the GREEN rule's perturbed disjunction: the perturbed run flips by
  # FAILING (failed>0), OR it flips by ERRORING (failed==0 but exit_code!=0).
  @walking_skeleton @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario Outline: A green that breaks when its dependency is broken is ruled earned
    Given a baseline run that is "green"
    And a perturbed run that is "<perturbed>"
    When the earned-verdict gate computes the verdict over the two runs
    Then the earned verdict status is "GREEN"
    And the earned verdict reason is "verdict-flipped"
    And the emitted verdict conforms to the earned-verdict contract
    And the emitted verdict echoes the seam and node it was asked about

    Examples: perturbed-run flip limbs
      | perturbed                          |
      | failed                             |
      | errored with a nonzero exit code   |

  # AT-2 -- THEATER DETECTION (verdict class RED): the perturbed run stays green
  # even though its dependency was broken. The test asserts nothing real ->
  # theater. The CORE emits status=RED reason=theater-held.
  @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: A green that survives breaking its own dependency is ruled theater
    Given a baseline run that is "green"
    And a perturbed run that is "green"
    When the earned-verdict gate computes the verdict over the two runs
    Then the earned verdict status is "RED"
    And the earned verdict reason is "theater-held"
    And the emitted verdict conforms to the earned-verdict contract
    And the emitted verdict echoes the seam and node it was asked about

  # AT-3 -- FAIL-SAFE ABSTAIN (verdict class ABSTAIN): there is no honest green
  # to perturb because the baseline is not green. Two Examples rows witness the
  # two limbs of the baseline-not-green disjunction: the baseline FAILED
  # (failed>0), OR the baseline is VACUOUS (passed==0 -- the canonical zero
  # boundary). Either way: never a false GREEN, never a false RED.
  @driving_port @real-io @slice-01 @error @contract-shape:bounded-change
  Scenario Outline: A baseline that is not green yields a fail-safe abstain
    Given a baseline run that is "<baseline>"
    And a perturbed run that is "<perturbed>"
    When the earned-verdict gate computes the verdict over the two runs
    Then the earned verdict status is "ABSTAIN"
    And the earned verdict reason is "baseline-not-green"
    And the emitted verdict conforms to the earned-verdict contract
    And the emitted verdict echoes the seam and node it was asked about

    Examples: baseline-not-green limbs
      | baseline                       | perturbed |
      | failed                         | failed    |
      | vacuous with nothing passing   | green     |
