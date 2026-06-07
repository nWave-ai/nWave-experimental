@feature-fix-reverify-e1-via-scoped-wrapper @walking_skeleton @wiring_e2e @driving_port @real-io
@contract-shape:pure-function
Feature: A feature-scoped completeness wrapper exposes a JSON verdict
  As an operator composing the reverify gate
  I want a thin read-only CLI that returns a feature-scoped completeness
  verdict for one slice commit
  So that the reverify gate can run E1 against a single feature without
  inheriting the atomic verify-then-record mode of the existing CLI.

  # Decision-table rows witnessed by this slice:
  #   R3 (single-feature, feature-scoped) ............... AT-(b) below
  #   wrapper malformed-input + required --feature-id ... AT-(c) below
  # The SSOT pure-function scoping property (AT-(a)) lives as a layer-2
  # parametrize-collapse in test_slice_01_pure_function_scoping.py -- the
  # bounded domain (1..5 features) is finite, so parametrize beats PBT
  # per the falsifier-gate (nw-property-based-testing).
  #
  # Driving port (Pillar 3): subprocess invocation of
  #   des check-slice-at-completeness
  # against a real temp-git repo (the F3 bootstrap-blind probe).

  @slice-01
  Scenario: An operator gets a complete verdict for a single-feature slice
    Given a repository with 1 features sharing the slice tag
    When the operator checks completeness for feature "fix-reverify-e1-via-scoped-wrapper"
    Then the completeness verdict is "complete"
    And the verdict payload names exactly the primary feature's slice file

  @slice-01 @error
  Scenario: An operator who omits the feature scope is refused
    Given a repository with 1 features sharing the slice tag
    When the operator checks completeness without a feature scope
    Then the completeness verdict is "malformed"

  @slice-01 @error
  Scenario: An operator gets a malformed verdict against an unreadable repository
    Given a repository with 1 features sharing the slice tag
    When the operator checks completeness against an unreadable repository
    Then the completeness verdict is "malformed"
