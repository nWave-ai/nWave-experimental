@feature-feature-end-ws-gate-manifest-optional @real-io @walking-skeleton
Feature: The walking-skeleton floor computes applicability when no manifest is present

  An operator sealing an atdd_pure feature has NO walking-skeleton.json manifest --
  an atdd_pure feature's walking skeleton is its walking-skeleton .feature scenario,
  not a hand-written JSON. Today the floor fail-closes (usage exit 2) the moment the
  manifest is absent, so `des feature-end run` cannot complete on any manifest-less
  feature. Per ADR-098 the floor must instead DERIVE applicability from the feature's
  git delta when no manifest is present: certify NOT_APPLICABLE when the delta adds no
  new installable root, refuse (FAIL) when the delta DOES add one without a
  walking-skeleton acceptance test, and degrade LOUD when the delta cannot be
  established -- never fail-close on absence, never let an installer dodge the floor by
  omitting the manifest.

  A feature that DOES ship a manifest is unchanged -- the explicit-manifest path
  governs exactly as before.

  # Driving port (Mandate-13, Layer 3 subprocess): the real
  # `des walking-skeleton-gate` command -- the walking-skeleton floor itself --
  # invoked end-to-end over the real `des` single entry point as a subprocess,
  # exactly as the feature-end cycle runs it. The observable is the floor verdict the
  # command reports (its printed verdict token + reason) and its
  # certify/refuse/refuse-to-decide/fail-close exit code. No production module is
  # imported and called at the step boundary (S2 driving-port-only boundary holds).
  # Each staged feature is a REAL tracked change-history (a baseline commit plus a
  # feature commit that either ADDS or does not ADD a new installable root) or a
  # non-git tree (the delta is undecidable) -- so the floor reads the feature's
  # genuine change, never a declared field.

  @slice-01 @contract-shape:bounded-change @manifest-optional
  Scenario: A manifest-less feature that adds no new installable root is certified past the floor
    Given a manifest-less feature whose change adds no new installable root
    When the operator runs the walking-skeleton floor on that feature
    Then the floor certifies the feature as not applicable to the walking skeleton
    And the floor does not fail-close on the absent manifest

  @slice-01 @contract-shape:bounded-change @manifest-optional @anti-vacuity
  Scenario: A manifest-less feature whose change adds a new installable root cannot dodge the floor
    Given a manifest-less feature whose change adds a new installable root
    When the operator runs the walking-skeleton floor on that feature
    Then the floor refuses to certify the feature
    And the floor does not fail-close on the absent manifest

  @slice-01 @contract-shape:bounded-change @manifest-optional @anti-vacuity
  Scenario: A manifest-less feature with no tracked change history makes the floor refuse to decide
    Given a manifest-less feature that lives outside any tracked change history
    When the operator runs the walking-skeleton floor on that feature
    Then the floor refuses to decide because it cannot determine what the feature added
    And the floor does not fail-close on the absent manifest

  @slice-01 @contract-shape:unbounded-preservation @manifest-present
  Scenario: A feature that ships a manifest is governed by the manifest exactly as before
    Given a feature that ships a manifest declaring it not applicable with a justified rationale
    When the operator runs the walking-skeleton floor on that feature
    Then the floor certifies the feature as not applicable to the walking skeleton
    And the floor does not fail-close on the absent manifest
