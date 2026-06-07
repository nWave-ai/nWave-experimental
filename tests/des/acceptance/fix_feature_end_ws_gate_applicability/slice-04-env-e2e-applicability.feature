@feature-fix-feature-end-ws-gate-applicability @slice-04 @coupled @real-io @contract-shape:bounded-change
Feature: The feature-end cycle treats the real-environment check as not applicable when the feature ships nothing to install

  An operator who has shipped a monorepo-internal feature -- a hook-only change to
  the shared codebase that adds no new installable package -- wants the feature-end
  cycle to certify past the real-environment check the same way the walking-skeleton
  floor already certifies past it. The cycle cannot build, install, and exercise a
  feature that ships no installable artifact, so the real-environment check is not
  applicable to it. Earlier the cycle ran that check anyway and falsely refused the
  feature because the feature carries no real-environment scope; the cycle must
  instead recognise the same not-applicable basis the walking-skeleton floor used,
  certify past the check, and record that it was not applicable -- never pretend the
  check passed.

  The cycle stays honest by reusing the floor's own mechanical basis: it recognises
  the real-environment check as not applicable only because the walking-skeleton
  floor granted not-applicable, and the floor grants that only when the feature's
  change adds no new installable package. A feature whose change DOES add a new
  installable package cannot dodge the real-environment check by claiming it ships
  nothing -- the floor reads the change, sees the new package, refuses, and the
  cycle never reaches the not-applicable path for the real-environment check.

  # Driving port (Mandate-13, Layer 3 subprocess): the real `des feature-end run`
  # command -- the feature-end cycle itself -- invoked end-to-end over the real
  # `des` single entry point as a subprocess, exactly as an operator runs it. The
  # observable is the cycle's certify/refuse outcome (its exit code + reported
  # reason) and the audit records the cycle minted (read from the raw audit
  # substrate, not the SUT). No production module is imported and called at the
  # step boundary (S2 driving-port-only boundary holds). Each staged feature is a
  # REAL tracked change-history (a baseline commit plus a feature commit that
  # either ADDS or does not ADD a new installable package) so the cycle reads the
  # feature's genuine change.

  @env-e2e @slice-04 @coupled
  Scenario: A feature that ships nothing to install is certified past the real-environment check and recorded as not applicable
    Given a feature whose change adds no new installable package and ships nothing to install
    When the operator runs the feature-end cycle on that feature
    Then the cycle is certified past the real-environment check
    And the cycle records the real-environment check as not applicable for that feature
    And the cycle never records the real-environment check as verified for that feature

  @env-e2e @anti-vacuity @slice-04 @coupled
  Scenario: A feature whose change adds a new package cannot skip the real-environment check by claiming it ships nothing
    Given a feature whose change adds a new installable package yet claims it ships nothing to install
    When the operator runs the feature-end cycle on that feature
    Then the cycle refuses to certify the feature
    And the cycle names the new installable package its change added
    And the cycle never records the real-environment check as not applicable for that feature
