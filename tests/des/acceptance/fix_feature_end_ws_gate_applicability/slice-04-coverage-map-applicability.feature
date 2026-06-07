@feature-fix-feature-end-ws-gate-applicability @slice-04 @coupled @real-io @contract-shape:bounded-change
Feature: The feature-end cycle treats the coverage attestation as not applicable only while the project has not yet adopted it

  An operator who has shipped a feature in a project that has not yet adopted the
  coverage attestation wants the feature-end cycle to certify past the coverage
  check and record that it was not applicable -- so a project mid-adoption is not
  blocked from certifying any feature done. But the operator equally wants the
  check to stay honest: a feature must not be able to escape a real coverage
  obligation by skipping the attestation, and a feature must not be able to declare
  for itself that the project has not adopted the check.

  The cycle stays honest by reading adoption as a single project-wide fact, from a
  place no individual feature can reach. While the project has not adopted the
  check, a feature that genuinely produced no coverage attestation is certified past
  it. The moment the project adopts the check, every feature is held to the real
  attestation -- no feature is grandfathered out. A feature that DID produce a
  coverage attestation is always really checked, never waved through as not
  applicable. A feature that tries to declare its own project-level adoption state
  is ignored -- the project's own setting decides. And when the project's adoption
  setting is unreadable, the cycle degrades toward the stricter real check, never
  toward the permissive not-applicable path.

  # Driving port (Mandate-13, Layer 3 subprocess): the real `des feature-end run`
  # command invoked end-to-end over the real `des` single entry point as a
  # subprocess. The observable is the cycle's certify/refuse outcome (exit code +
  # reported reason) and the audit records the cycle minted (raw audit substrate
  # read-back, not the SUT). No production module is imported and called at the
  # step boundary (S2 driving-port-only boundary holds). The project's adoption
  # setting lives at the project root -- a place no feature directory can shadow --
  # and each feature either does or does not carry a genuine coverage attestation.

  @coverage-map @slice-04 @coupled
  Scenario: A feature with no coverage attestation is certified past the coverage check while the project has not adopted it
    Given a project that has not adopted the coverage attestation and a feature that produced none
    When the operator runs the feature-end cycle on that feature
    Then the cycle is certified past the coverage check
    And the cycle records the coverage check as not applicable for that feature
    And the cycle never records the coverage check as verified for that feature

  @coverage-map @anti-vacuity @slice-04 @coupled
  Scenario: A feature that produced a half-baked coverage attestation is really checked, never waved through
    Given a project that has not adopted the coverage attestation and a feature that produced a half-baked one
    When the operator runs the feature-end cycle on that feature
    Then the cycle refuses to certify the feature
    And the cycle names the incomplete coverage attestation as the reason it refuses
    And the cycle never records the coverage check as not applicable for that feature

  @coverage-map @anti-vacuity @slice-04 @coupled
  Scenario: Once the project adopts the coverage attestation a feature with none is held to the real check
    Given a project that has adopted the coverage attestation and a feature that produced none
    When the operator runs the feature-end cycle on that feature
    Then the cycle refuses to certify the feature
    And the cycle names the missing coverage signoff as the reason it refuses
    And the cycle never records the coverage check as not applicable for that feature

  @coverage-map @anti-vacuity @slice-04 @coupled
  Scenario: A feature that produced a coverage attestation is really checked against it, never waved through as not applicable
    Given a project that has adopted the coverage attestation and a feature that produced one
    When the operator runs the feature-end cycle on that feature
    Then the cycle names the incomplete coverage attestation as the reason it refuses
    And the cycle never records the coverage check as not applicable for that feature

  @coverage-map @anti-vacuity @slice-04 @coupled
  Scenario: A feature that declares its own adoption state is ignored and held to the project setting
    Given a project that has adopted the coverage attestation and a feature declaring for itself that the project has not
    When the operator runs the feature-end cycle on that feature
    Then the cycle refuses to certify the feature
    And the cycle names the missing coverage signoff as the reason it refuses
    And the cycle never records the coverage check as not applicable for that feature

  @coverage-map @slice-04 @coupled
  Scenario: A project whose adoption setting omits the coverage key has not adopted it and certifies a feature with none
    Given a project whose adoption setting omits the coverage key and a feature that produced none
    When the operator runs the feature-end cycle on that feature
    Then the cycle records the coverage check as not applicable for that feature

  @coverage-map @anti-vacuity @slice-04 @coupled
  Scenario: A project whose adoption setting is unreadable degrades to the real check, never to not applicable
    Given a project whose adoption setting is unreadable and a feature that produced none
    When the operator runs the feature-end cycle on that feature
    Then the cycle refuses to certify the feature
    And the cycle names the missing coverage signoff as the reason it refuses
    And the cycle never records the coverage check as not applicable for that feature
