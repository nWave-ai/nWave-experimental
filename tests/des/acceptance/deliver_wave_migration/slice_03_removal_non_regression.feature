@feature-f-deliver-wave-migration @slice-03 @infrastructure @real-io @driving_port
Feature: The legacy AT-satisfaction-only crafter prose is reconciled and matches-design is preserved
  # Slice-03 (feature-delta DESIGN Slice Plan FINAL, line 884: slice-03
  # @infrastructure, removal-only, carries AT-8 as absence + non-regression).
  # Removal/consolidation slice (C9/G-1): the legacy crafter prose that frames
  # implementation purely as AT-satisfaction ("Implement the minimum production
  # code that turns all ATs from RED to GREEN", nw-software-crafter.md:104) with NO
  # bundle-consume / matches-design conformance step is reconciled so the codebase
  # carries no stale free-to-invent DELIVER assertion.
  #
  # Two witnesses, one real gate port (Layer-3 subprocess, Mandate-13):
  #   • ABSENCE (ac-8-absence): registers the LEGACY AT-satisfaction-only marker;
  #     the gate FAILs when the marker is absent. Absence is the goal → the AT
  #     asserts FAIL. PRESENT today → the gate PASSes → the AT (expecting FAIL) is
  #     ACTIVE-RED. DELIVER reconciles the nw-software-crafter.md:104 A_GREEN_ATS
  #     step to add the matches-design conformance step → FAIL → green.
  #   • NON-REGRESSION (ac-8-non-regression): asserts the matches-design leg is
  #     PRESENT (DELIVER on a conforming feature still reaches a matches-design
  #     gate-OUT PASS — the leg is present, not re-broken). The floor reuses the
  #     slice-01 matches-design-public-surface marker (single SSOT phrase); ABSENT
  #     today → gate FAIL → expects PASS → ACTIVE-RED, green when the same migration
  #     lands. It pins that the removal does not strip the conformance behaviour (C9
  #     non-regression).
  #
  # PROSE migration (DESIGN feature-delta:721 — zero new src/des module). Empty
  # positive-@slice AT set is correct for a removal-only consolidation slice: the
  # deliverable is the ABSENCE of stale prose + the NON-REGRESSION witness. The
  # commit carries a Slice-Id trailer; verify-integrity reconciles via the trailer.
  #
  # Mandate 9 v2: @real-io → example-based; no PBT machinery (Mandate 11).

  @contract-shape:bounded-change @ac-8-absence @slice-03
  Scenario: The legacy AT-satisfaction-only crafter prose is gone after migration
    Given the real shipped crafter agent that the legacy AT-satisfaction-only prose is reconciled in exists
    And a clause registering the legacy AT-satisfaction-only marker
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is FAIL with exit code 1 because the legacy marker is absent
    And the verdict names the legacy AT-satisfaction-only clause

  @contract-shape:bounded-change @ac-8-non-regression @slice-03
  Scenario: DELIVER still conforms to the design contract after the legacy prose is reconciled
    Given the real shipped DELIVER command that the matches-design leg floor lives in exists
    And a clause asserting the matches-design leg is preserved
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0 because the matches-design leg is preserved
