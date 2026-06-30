@feature-f-deliver-wave-migration @slice-01 @walking_skeleton @real-io @driving_port
Feature: A maintainer running DELIVER implements MATCHING the design with private freedom preserved
  # Slice-01 walking skeleton (feature-delta DESIGN Slice Plan FINAL, line 882:
  # slice-01 carries AT-1..AT-3). The thinnest end-to-end vertical proving the
  # JOB-027 "implement-matching-the-design, public-surface-only" job: the DELIVER
  # prose normatively declares that the crafter CONSUMES the bundle (the AT set +
  # the DESIGN [REF] Code-Design contract + the architecture) and implements TO the
  # declared structure (AT-1), that crafter-matches-design compares the
  # implementation PUBLIC surface against the design's declared public contract
  # (AT-2), and that a private symbol / Extract-Method refactor below the public
  # boundary is NEVER flagged (AT-3, the load-bearing C4 private-refactor-freedom
  # invariant) — instead of a crafter free to invent whatever structure passes the
  # ATs.
  #
  # PROSE migration (DESIGN feature-delta:721 — zero new src/des module; the
  # mechanical ConformanceDiff is DESIGNED-NOT-BUILT, owned by feature 6 per OB-1 →
  # option b/c). These ATs do NOT build or test a conformance engine; they witness
  # that the shipped DELIVER prose DECLARES the matches-design discipline.
  #
  # Driving surface (Mandate-13, Layer-3 subprocess): the real `des
  # skill-normative-gate` dispatcher reads the REAL shipped
  # nWave/agents/nw-software-crafter.md, nWave/tasks/nw/deliver.md, and
  # nWave/skills/nw-tdd-methodology/SKILL.md and emits PASS/FAIL/INDETERMINATE. The
  # AT asserts the SHIPPED exit code — never a fabricated oracle (protocol-driver
  # contract: the oracle is the gate's real exit code over the real file).
  #
  # Active-RED (atdd_pure / ADR-025, NOT @skip): each f-deliver matches-design
  # marker is ABSENT from the shipped prose at HEAD → the real gate returns FAIL
  # (exit 1) → these scenarios expect PASS → AssertionError. DELIVER migrates the
  # bundle-consume + matches-design prose into the crafter surfaces → the gate
  # returns PASS → green.
  #
  # Mandate 9 v2: @real-io (real subprocess + real filesystem) → example-based;
  # no PBT machinery (Mandate 11).

  @contract-shape:unbounded-preservation @ac-1 @slice-01
  Scenario: The crafter prose declares the crafter consumes the bundle and implements matching the design
    Given the real shipped crafter agent that the bundle-consume rule lives in exists
    And a clause asserting the crafter consumes the bundle and implements matching the declared structure
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing conformance clauses

  @contract-shape:unbounded-preservation @ac-2 @slice-01
  Scenario: The DELIVER prose declares crafter-matches-design compares the public surface against the declared contract
    Given the real shipped DELIVER command that the matches-design public-surface rule lives in exists
    And a clause asserting the matches-design gate compares the public surface against the declared contract
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing conformance clauses

  @contract-shape:unbounded-preservation @ac-3 @slice-01
  Scenario: The crafter skill declares a private symbol or Extract-Method below the public boundary is never flagged
    Given the real shipped crafter skill that the private-refactor-freedom rule lives in exists
    And a clause asserting a new private symbol or Extract-Method below the public boundary is never flagged
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing conformance clauses
