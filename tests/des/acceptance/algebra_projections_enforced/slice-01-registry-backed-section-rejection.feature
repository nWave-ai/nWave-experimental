@feature-algebra-projections-enforced
Feature: The maintainer is stopped from shipping a feature-delta section the wave's registry never declared

  Maya, an nWave maintainer, authors a `## Wave: <W> / [REF] <S>` section in a
  feature-delta. Today nothing checks her new section against the wave-contract
  registry (`nWave/waves/<wave>.yaml`'s `output_contract.ref_sections`): she can
  ship a section the registry never declared and every gate stays green, so the
  drift surfaces weeks later. This slice closes the first half of that gap — the
  maintainer runs the registry-section check and a section absent from the wave's
  declared contract is REJECTED, named in the verdict, while a feature-delta whose
  sections are all declared is ACCEPTED. The check reads the LIVE registry, not a
  hard-coded section list, so the registry is finally a constraint rather than
  documentation.

  # DISCUSS WD-1 (the walking skeleton is the SECOND consumer of the projection —
  # the feature-delta section validator reading the registry) + WD-3 direction (a)
  # (feature-delta section not in registry ref_sections -> REJECT). DESIGN DA-1/DA-2/
  # DA-6, DD-A1/DD-A2. Driving port: the validate-feature-delta CLI invoked with
  # --require-registry-sections <wave> --format=json (DESIGN Driving Ports).
  # Layer 3 (subprocess/FS acceptance) — example-only, no PBT (Mandate 9/11): the
  # section⊗registry cross-check is a closed-world finite classification at this
  # layer; sad paths are enumerated explicitly (Mandate 11), never PBT-generated.

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:pure-function
  Scenario: A feature-delta whose every section is declared by the wave clears the registry-section check
    Given a feature-delta whose [REF] sections are all declared by the discuss registry
    When the maintainer runs the registry-section check for the discuss wave
    Then the registry-section check accepts the feature-delta
    And the check leaves the feature-delta unchanged

  @slice-01 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A feature-delta carrying a section the wave never declared is rejected, naming the section
    Given a feature-delta carrying a [REF] section the discuss registry does not declare
    When the maintainer runs the registry-section check for the discuss wave
    Then the registry-section check rejects the feature-delta for an undeclared section
    And the rejection names the undeclared section
    And the check leaves the feature-delta unchanged

  @slice-01 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A section that the old hard-coded list allowed but the live registry omits is rejected
    Given a feature-delta carrying a section honoured by the legacy hard-coded list but absent from the discuss registry
    When the maintainer runs the registry-section check for the discuss wave
    Then the registry-section check rejects the feature-delta for an undeclared section
    And the rejection names the undeclared section
    And the check leaves the feature-delta unchanged

  @slice-01 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A section the live registry declares but the legacy hard-coded list omits is accepted
    Given a feature-delta carrying only a section the discuss registry declares but the legacy hard-coded list omits
    When the maintainer runs the registry-section check for the discuss wave
    Then the registry-section check accepts the feature-delta
    And the check leaves the feature-delta unchanged
