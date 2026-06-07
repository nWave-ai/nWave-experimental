@feature-fix-feature-end-ws-gate-applicability @slice-02 @real-io @walking-skeleton @contract-shape:bounded-change
Feature: The walking-skeleton floor refuses an unjustified not-applicable claim

  An operator declaring a feature "not applicable to the walking-skeleton floor"
  must JUSTIFY the claim rather than assert it bare. The floor decides on a
  POSITIVE, EXPLICIT, JUSTIFIED claim: a declaration with no reason is refused as
  unjustified -- the claim is never a free pass.

  # slice-03 supersession (2026-06-05): the two installability divergence-pair
  # scenarios that previously lived here -- NON-installable -> NOT_APPLICABLE, and
  # installable-but-declared-NA -> FAIL -- were RETIRED when slice-03 made the
  # installability cross-check DELTA-AWARE. Their behaviour is subsumed, on the
  # stronger un-gameable git-delta basis, by
  # slice-03-delta-aware-installability.feature cases (b) NOT_APPLICABLE and (a)
  # FAIL (plus (c) INDETERMINATE on a non-git tree). The ambient
  # `_detect_installable(feature_root)` probe those scenarios exercised no longer
  # exists (DESIGN feature-delta.md DDD-2 / DDD-4; C_REVIEWER_AUDIT verdict
  # APPROVED + SUPERSESSION-CONFIRMED, agent a3fbbb11). slice-02's residual,
  # orthogonal contribution -- the explicit-declaration JUSTIFICATION guard below,
  # which runs BEFORE any installability probe -- is unaffected by delta-awareness
  # and is preserved.

  # Driving port (Mandate-13, Layer 3 subprocess): the real
  # `des walking-skeleton-gate` command -- the walking-skeleton floor itself --
  # invoked end-to-end over the real `des` entry point as a subprocess, exactly as
  # the feature-end cycle runs it. The observable is the floor verdict the command
  # reports (its printed verdict + reason) and its certify/refuse outcome. No
  # production module is imported and called at the step boundary.

  @ws-floor @anti-vacuity @slice-02
  Scenario: A claim of not-applicable with no justification is refused
    Given a feature that claims it ships no walking skeleton but gives no reason
    When the operator runs the walking-skeleton floor on that feature
    Then the floor refuses the claim as unjustified
    And the floor names the missing justification
