@feature-algebra-projections-enforced
Feature: A DISTILL feature-delta is enforced against the distill wave's own output contract

  Maya, an nWave maintainer, runs the registry-section check on a DISTILL
  feature-delta. Today `nWave/waves/distill.yaml` carries a `gate_stack` but NO
  `output_contract` block (verified grep-0): the registry reader finds zero
  declared `ref_sections` for the distill wave, so the check has NO contract to
  enforce — every DISTILL `[REF]` section is treated as undeclared. This slice
  gives distill a real `output_contract.ref_sections` block, so a DISTILL
  feature-delta carrying exactly the sections the distill wave declares is
  ACCEPTED, while a DISTILL feature-delta carrying a section the distill wave
  never declared is REJECTED, named in the verdict. The check reads the LIVE
  distill registry — the contract is finally a constraint instead of a silent
  pass-everything hole.

  # DISCUSS slice-03 ("the maintainer sees distill.yaml carry an output_contract
  # block ... so a DISTILL feature-delta is enforced against a real contract
  # instead of silently passing with no contract at all"). DESIGN Point 4 (the 8
  # induced ref_sections) + Reuse Analysis row `distill.yaml`. Driving port: the
  # validate-feature-delta CLI invoked with --require-registry-sections distill
  # --format=json (DESIGN Driving Ports). Layer 3 (subprocess/FS acceptance) —
  # example-only, no PBT (Mandate 9/11): the section⊗distill-registry cross-check
  # is a closed-world finite classification at this layer; sad paths are
  # enumerated explicitly (Mandate 11), never PBT-generated.
  #
  # active-RED at HEAD: distill.yaml has NO output_contract block, so
  # read_wave_output_contract("distill") yields an EMPTY contract. An all-declared
  # DISTILL delta therefore gets `undeclared-section` (RED), and a bogus-section
  # delta names the FIRST DISTILL section rather than the bogus one (RED). DELIVER
  # A_GREEN adds the output_contract.ref_sections block (8 entries) to distill.yaml
  # to turn these GREEN. No production code change — a registry data block.

  @slice-03 @walking_skeleton @driving_port @real-io @contract-shape:pure-function
  Scenario: A DISTILL feature-delta whose every section is declared by the distill wave is accepted
    Given a DISTILL feature-delta whose [REF] sections are exactly the distill wave's declared sections
    When the maintainer runs the registry-section check for the distill wave
    Then the registry-section check accepts the feature-delta
    And the check leaves the feature-delta unchanged

  @slice-03 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A DISTILL feature-delta carrying a section the distill wave never declared is rejected, naming it
    Given a DISTILL feature-delta carrying a [REF] section the distill wave does not declare
    When the maintainer runs the registry-section check for the distill wave
    Then the registry-section check rejects the feature-delta for an undeclared section
    And the rejection names the undeclared distill section
    And the check leaves the feature-delta unchanged

  @slice-03 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A DISTILL feature-delta with no declared contract to enforce is not silently passed
    Given a DISTILL feature-delta carrying only a single distill-declared section
    When the maintainer runs the registry-section check for the distill wave
    Then the registry-section check accepts the feature-delta
    And the check leaves the feature-delta unchanged
