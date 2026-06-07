@feature-fix-feature-end-ws-gate-applicability @slice-01 @real-io @walking-skeleton @contract-shape:bounded-change
Feature: The feature-end gate reports its real refusal reason

  An operator running the feature-end cycle on a developer checkout wants a gate
  refusal to hand back the REAL reason the gate refused -- not the runtime
  freshness-autoskip notice that every developer-checkout run prints alongside
  it. When the gate refuses, the operator must be able to read WHY straight from
  the refusal, so they can fix the real cause without re-running the gate by hand
  to see past the noise.

  Anti-theater-NEUTRAL: this changes only WHICH text the operator reads in a
  refusal; it never changes whether the gate refuses. The refusal still happens,
  with the same outcome -- only the reported reason becomes truthful.

  # Driving port (Mandate-13, Layer 3 subprocess): the real `des feature-end run`
  # command, invoked end-to-end over the real `des` entry point as a subprocess
  # against a staged feature on a developer checkout. The observable is the
  # refusal the command reports (its reported reason + its refuse outcome). No
  # production module is imported and called at the step boundary.

  Background:
    Given an operator on a developer checkout running the feature-end cycle

  @ws-floor @slice-01
  Scenario: A refusal reports the missing-manifest reason, not the freshness notice
    Given a feature whose walking-skeleton floor has no manifest to check
    When the operator runs the feature-end cycle on that feature
    Then the feature-end cycle refuses to certify the feature done
    And the reported reason names the missing walking-skeleton manifest
    And the reported reason is not the runtime freshness notice

  @ws-floor @anti-vacuity @slice-01
  Scenario: A different real refusal reason is reported unchanged
    Given a feature whose walking-skeleton manifest is missing its feature root
    When the operator runs the feature-end cycle on that feature
    Then the feature-end cycle refuses to certify the feature done
    And the reported reason names the missing feature root
    And the reported reason is not the runtime freshness notice
