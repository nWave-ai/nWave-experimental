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

  # RETIRED (ADR-098, 2026-06-24): the "missing-manifest reason" scenario asserted
  # the WS floor REFUSES naming `walking-skeleton.json` when no manifest is present.
  # ADR-098 reverses that fail-close-on-absence contract: an absent manifest now
  # COMPUTES applicability from the git-delta (NOT_APPLICABLE / FAIL / INDETERMINATE),
  # so a manifest-less feature is no longer refused for a "missing manifest" reason.
  # The new contract is covered comprehensively by the C6 ATs in
  # tests/des/acceptance/ws_gate_manifest_optional/. The surviving scenario below
  # keeps the slice's real-reason-not-freshness-notice assertion via a DIFFERENT
  # still-valid refusal cause (a malformed manifest missing its feature_root, which
  # ADR-098 leaves raising -- only ABSENCE computes).

  @ws-floor @anti-vacuity @slice-01
  Scenario: A different real refusal reason is reported unchanged
    Given a feature whose walking-skeleton manifest is missing its feature root
    When the operator runs the feature-end cycle on that feature
    Then the feature-end cycle refuses to certify the feature done
    And the reported reason names the missing feature root
    And the reported reason is not the runtime freshness notice
