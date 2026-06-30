@feature-skill-normative-content-gate @slice-01 @walking_skeleton @real-io @driving_port
Feature: The maintainer sees the named broken clause through the real gate
  # Slice-01 walking skeleton (feature-delta WS Strategy; DESIGN §9).
  # Connects manifest-load -> asset-resolve -> clause-assert -> closed-verdict
  # end-to-end on the REAL Mandate-13 surface, driven through the REAL `des`
  # dispatcher (M-1 dormant-seam guard: `des skill-normative-gate`, not
  # `python -m des.cli.skill_normative_gate`).
  #
  # Real-Surface Binding (AC-08): both scenarios read the real shipped
  # manifest / real `nWave/skills/nw-test-design-mandates/SKILL.md`; the FAIL
  # scenario asserts against a real-text copy with the marker removed — never a
  # fabricated oracle.
  #
  # Mandate 9 v2: @real-io (real subprocess + real filesystem) -> example-based;
  # no PBT. Mandate 11: the sad path (AC-01) is one explicit named example.

  @contract-shape:bounded-change @ac-01 @slice-01
  Scenario: A deleted protocol-driver clause yields FAIL naming the skill and clause
    Given the real shipped skill carrying clause "protocol-driver:assert-shipped-artifact" exists
    And a manifest that points at a skill copy with that clause's marker removed
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is FAIL with exit code 1
    And the verdict names skill "nw-test-design-mandates" and clause "protocol-driver:assert-shipped-artifact"

  @contract-shape:bounded-change @ac-02 @slice-01
  Scenario: The protocol-driver clause intact on the real surface yields PASS
    Given the real shipped manifest and the real Mandate-13 skill are present
    And a manifest registering clause "protocol-driver:assert-shipped-artifact" against the real shipped skill
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing clauses
