@feature-f-deliver-wave-migration @slice-02 @real-io @driving_port
Feature: A maintainer has drift caught, a design flaw bumped, the mechanism degrade-LOUD, and a language-agnostic seam
  # Slice-02 (feature-delta DESIGN Slice Plan FINAL, line 883: slice-02 carries
  # AT-4..AT-7, 4 ATs ≤ ceiling 5). One cohesive gate-OUT / bump / seam behaviour:
  #   • AT-4 — divergence: an UNDECLARED public symbol (or a MISSING declared one) →
  #     gate-OUT FAIL → redo IN-WAVE (the crafter over/under-built; the design is
  #     sound). The OB-1 option-c UNVERIFIED-on-suspected-drift posture is folded
  #     into this same matches-design rule (one marker, not a 9th AT).
  #   • AT-5 — the K5 design-flaw bump: a NAMED contract self-contradiction →
  #     recorded DESIGN-DEFECT → bump-to-DESIGN that the HUMAN disposes
  #     (controls-only-veto, OB-2), DISTINCT from a redo-in-wave, NOT patched in
  #     place.
  #   • AT-6 — the matches-design mechanism that cannot run degrades LOUD as
  #     INDETERMINATE; never a silent pass / false green (KPI-4 guardrail).
  #   • AT-7 — the public-surface inspection SEAM is language-agnostic (resolved
  #     behind a per-language AST port reusing the CodeFactPort AstAdapter family);
  #     this is the SEAM, explicitly NOT the port BUILD (feature 6, OB-1).
  #
  # PROSE migration (DESIGN feature-delta:721 — zero new src/des module). These ATs
  # witness that the shipped DELIVER prose DECLARES the divergence/bump/seam rules.
  #
  # Driving surface (Mandate-13, Layer-3 subprocess): the real `des
  # skill-normative-gate` dispatcher over the REAL shipped nw-software-crafter.md /
  # nw-functional-software-crafter.md / nw-deliver (deliver.md).
  #
  # AT-6 INDETERMINATE guardrail (the KPI-4 degrade-LOUD): the matches-design clause
  # is registered against an UNREADABLE asset, so the gate returns INDETERMINATE
  # (exit 4) by construction TODAY — the AT asserts INDETERMINATE, witnessing the
  # §17 "mechanism could not run ⇒ degrade-LOUD, never a silent pass" row. It is
  # ALSO active-RED in the prose-presence sense: the seam-PRESENCE leg (a separate
  # scenario) registers the degrade-LOUD marker ABSENT from the prose → FAIL →
  # expects PASS.
  #
  # Active-RED (atdd_pure / ADR-025, NOT @skip): every PRESENCE marker (AT-4/5/6
  # seam-leg/7) is ABSENT from the shipped prose at HEAD → the gate returns FAIL →
  # these scenarios expect PASS → AssertionError. DELIVER migrates the prose → PASS
  # → green. The AT-6 INDETERMINATE-guardrail scenario expects INDETERMINATE (exit
  # 4) and stays green as a guardrail (degrade-LOUD is the permanent behaviour).
  #
  # Mandate 9 v2: @real-io → example-based; no PBT machinery (Mandate 11). Sad
  # paths (undeclared symbol, named contradiction, unreadable surface) are named
  # examples.

  @contract-shape:bounded-change @ac-4 @slice-02
  Scenario: The DELIVER prose declares an undeclared or missing public symbol fails the gate and is routed to redo
    Given the real shipped DELIVER command that the undeclared-public-symbol rule lives in exists
    And a clause asserting an undeclared or missing public symbol fails the gate and is routed to redo in-wave
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing conformance clauses

  @contract-shape:bounded-change @ac-5 @slice-02
  Scenario: The DELIVER prose declares a named contract self-contradiction bumps to DESIGN that the human disposes
    Given the real shipped DELIVER command that the design-defect bump rule lives in exists
    And a clause asserting a named contract self-contradiction bumps to DESIGN that the human disposes
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing conformance clauses

  @contract-shape:bounded-change @ac-6-seam @slice-02
  Scenario: The DELIVER prose declares the matches-design mechanism degrades LOUD as INDETERMINATE
    Given the real shipped DELIVER command that the matches-design degrade-LOUD rule lives in exists
    And a clause asserting the matches-design mechanism that cannot run degrades LOUD as INDETERMINATE
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing conformance clauses

  @contract-shape:bounded-change @ac-6-guardrail @slice-02
  Scenario: The matches-design seam degrades LOUD as INDETERMINATE when the mechanism cannot read its surface
    Given the real shipped DELIVER command that the matches-design degrade-LOUD rule lives in exists
    And a clause asserting the matches-design seam against a surface the mechanism cannot read
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is INDETERMINATE with exit code 4 because the mechanism could not run
    And the verdict refuses to certify what it cannot read

  @contract-shape:unbounded-preservation @ac-7 @slice-02
  Scenario: The FP-crafter prose declares the public-surface inspection is a language-agnostic per-language AST seam
    Given the real shipped FP-crafter agent that the language-agnostic AST seam rule lives in exists
    And a clause asserting the public-surface inspection is resolved behind a per-language AST port
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing conformance clauses
