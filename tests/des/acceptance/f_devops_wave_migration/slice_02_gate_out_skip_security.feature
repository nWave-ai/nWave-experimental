@feature-f-devops-wave-migration @slice-02 @real-io @driving_port
Feature: A maintainer gets an explicit DEVOPS skip, an un-instrumentable KPI caught, and a language-agnostic security seam
  # Slice-02 (feature-delta DESIGN Slice Plan FINAL: slice-02 carries AT-4..AT-7,
  # 4 ATs ≤ ceiling 5, re-confirmed after OB-1 → option (a)). One cohesive
  # gate-OUT / skip / security behaviour:
  #   • AT-4 — explicit N/A skip-witness (machine-distinguishable) + Tier-B advisory notifies
  #   • AT-5 — KPI-in-gate completeness: an un-instrumentable KPI → FAIL → redo-in-wave
  #   • AT-6 — language-agnostic security-gate SEAM; unrecognized toolchain → INDETERMINATE degrade-LOUD
  #   • AT-7 — Tier-B DEVOPS advisory LITERAL wording (NAME skip + risk + /nw-devops, proceeds, no confirm)
  #
  # Driving surface (Mandate-13, Layer-3 subprocess): the real `des
  # skill-normative-gate` dispatcher over the REAL shipped
  # nw-platform-architect.md + nw-infrastructure-and-observability/SKILL.md.
  #
  # AT-6 INDETERMINATE guardrail (the KPI-4 degrade-LOUD): the security-seam clause
  # is registered against an UNREADABLE asset, so the gate returns INDETERMINATE
  # (exit 4) by construction TODAY — the AT asserts INDETERMINATE, witnessing the
  # "mechanism could not run ⇒ degrade-LOUD, never a silent pass" §17 row. It is
  # ALSO active-RED in the prose-presence sense: the seam-PRESENCE leg (a separate
  # scenario) registers the seam marker ABSENT from the prose → FAIL → expects PASS.
  #
  # Active-RED (atdd_pure / ADR-025, NOT @skip): every PRESENCE marker (AT-4/5/6
  # seam-leg/7) is ABSENT from the shipped prose at HEAD → the gate returns FAIL →
  # these scenarios expect PASS → AssertionError. DELIVER migrates the prose → PASS
  # → green. The AT-6 INDETERMINATE-guardrail scenario expects INDETERMINATE (exit
  # 4) and stays green as a guardrail (degrade-LOUD is the permanent behaviour).
  #
  # Mandate 9 v2: @real-io → example-based; no PBT machinery (Mandate 11). Sad
  # paths (un-instrumentable, unrecognized toolchain) are named examples.

  @contract-shape:bounded-change @ac-4 @slice-02
  Scenario: The DEVOPS prose declares a no-delta feature records an explicit N/A skip with a notice
    Given the real shipped DEVOPS agent that the explicit N/A skip rule lives in exists
    And a clause asserting a no-delta feature records an explicit N/A skip the advisory notifies without blocking
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing instrumentation clauses

  @contract-shape:bounded-change @ac-5 @slice-02
  Scenario: The DEVOPS prose declares an un-instrumentable KPI is caught at gate-out and routed to redo
    Given the real shipped DEVOPS agent that the un-instrumentable KPI rule lives in exists
    And a clause asserting an un-instrumentable KPI fails the gate and is routed to redo in-wave
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing instrumentation clauses

  @contract-shape:bounded-change @ac-6-seam @slice-02
  Scenario: The observability prose declares the security gate is a language-agnostic seam that degrades loud
    Given the real shipped observability skill that the security-gate seam rule lives in exists
    And a clause asserting the security gate resolves the toolchain behind a per-language port and degrades loud
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing instrumentation clauses

  @contract-shape:bounded-change @ac-6-guardrail @slice-02
  Scenario: The security seam degrades LOUD as INDETERMINATE when the mechanism cannot read its surface
    Given the real shipped observability skill that the security-gate seam rule lives in exists
    And a clause asserting the security-gate seam against a surface the mechanism cannot read
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is INDETERMINATE with exit code 4 because the mechanism could not run
    And the verdict refuses to certify what it cannot read

  @contract-shape:unbounded-preservation @ac-7 @slice-02
  Scenario: The DEVOPS prose carries the Tier-B advisory literal notice for a DEVOPS skip
    Given the real shipped DEVOPS agent that the Tier-B advisory wording lives in exists
    And a clause asserting the Tier-B advisory literal notice names the skip and proposes nw-devops and proceeds
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing instrumentation clauses
