@feature-fix-feature-end-ws-gate-applicability @slice-03 @real-io @walking-skeleton @contract-shape:bounded-change
Feature: The walking-skeleton floor decides applicability on what the feature SHIPS

  An operator who has shipped a monorepo-internal feature -- a hook-only change to
  the shared codebase that adds no new installable package -- wants the
  walking-skeleton floor to recognise that this particular feature ships no new
  walking skeleton and certify past it, even though the surrounding repository is
  itself installable. The earlier floor read the surrounding repository's
  installability and falsely blocked every monorepo-internal feature; the floor
  must instead decide on what THIS feature actually adds.

  The floor stays honest by keying its decision on the feature's own change rather
  than on a declared field: it honours "this feature is not applicable to the
  walking-skeleton floor" only when the feature's change adds no new installable
  package. A feature whose change DOES add a new installable package cannot dodge
  the floor by claiming it ships nothing -- the floor reads the change, sees the
  new package, and refuses the claim as a contradiction. And when the floor cannot
  determine what the feature added -- the feature lives outside any tracked change
  history -- it refuses loudly to decide rather than fabricate a pass.

  # Driving port (Mandate-13, Layer 3 subprocess): the real
  # `des walking-skeleton-gate` command -- the walking-skeleton floor itself --
  # invoked end-to-end over the real `des` single entry point as a subprocess,
  # exactly as the feature-end cycle runs it. The observable is the floor verdict
  # the command reports (its printed verdict token + reason) and its
  # certify/refuse/refuse-to-decide exit code. No production module is imported and
  # called at the step boundary (S2 driving-port-only boundary holds). Each staged
  # feature is a REAL tracked change-history: a baseline commit plus a feature
  # commit that either ADDS or does not ADD a new installable package -- so the
  # floor reads the feature's genuine change, not a declared field.

  @ws-floor @slice-03
  Scenario: A monorepo-internal feature that adds no new package is certified past the floor
    Given a feature whose change adds no new installable package and justifies that it ships no walking skeleton
    When the operator runs the walking-skeleton floor on that feature
    Then the floor certifies the feature as not applicable to the walking skeleton
    And the floor lets the feature-end proceed past the walking-skeleton floor

  @ws-floor @anti-vacuity @slice-03
  Scenario: A feature whose change adds a new package cannot dodge the floor by claiming it ships nothing
    Given a feature whose change adds a new installable package yet claims it ships no walking skeleton
    When the operator runs the walking-skeleton floor on that feature
    Then the floor refuses to certify the feature
    And the floor names the new installable package its change added

  @ws-floor @anti-vacuity @slice-03
  Scenario: A feature with no tracked change history makes the floor refuse to decide
    Given a feature that lives outside any tracked change history yet claims it ships no walking skeleton
    When the operator runs the walking-skeleton floor on that feature
    Then the floor refuses to decide because it cannot determine what the feature added
    And the floor names the missing change history as the reason it cannot decide
