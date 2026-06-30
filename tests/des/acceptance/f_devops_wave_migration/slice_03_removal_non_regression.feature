@feature-f-devops-wave-migration @slice-03 @infrastructure @real-io @driving_port
Feature: The legacy free-form DEVOPS decision-question prose is removed and instrumentation is preserved
  # Slice-03 (feature-delta DESIGN Slice Plan FINAL: slice-03 @infrastructure,
  # removal-only, carries AT-8 as absence + non-regression). Removal/consolidation
  # slice (C7/G-1): the legacy free-form `/nw-devops` decision-question prose
  # (deployment-target / orchestrator / CI-platform / observability-stack asked by
  # judgement, devops.md:18-90) is removed/reconciled so the codebase carries no
  # stale non-KPI-traced DEVOPS assertion.
  #
  # Two witnesses, one real gate port (Layer-3 subprocess, Mandate-13):
  #   • ABSENCE (ac-8-absence): registers the LEGACY free-form decision-question
  #     marker; the gate FAILs when the marker is absent. Absence is the goal → the
  #     AT asserts FAIL. PRESENT today → the gate PASSes → the AT (expecting FAIL)
  #     is ACTIVE-RED. DELIVER removes the devops.md:18-90 block → FAIL → green.
  #   • NON-REGRESSION (ac-8-non-regression): asserts the KPI-traced observability
  #     wording is PRESENT (DEVOPS on an instrumenting feature still reaches a
  #     KPI-traced gate-OUT). The floor reuses the slice-01 KPI→telemetry marker
  #     (single SSOT phrase); ABSENT today → gate FAIL → expects PASS → ACTIVE-RED,
  #     green when the same migration lands. It pins the removal does not strip the
  #     instrumentation behaviour (C7 non-regression).
  #
  # Empty positive-@slice AT set is correct for a removal-only consolidation slice:
  # the deliverable is the ABSENCE of stale prose + the NON-REGRESSION witness. The
  # commit carries a Slice-Id trailer; verify-integrity reconciles via the trailer.
  #
  # Mandate 9 v2: @real-io → example-based; no PBT machinery (Mandate 11).

  @contract-shape:bounded-change @ac-8-absence @slice-03
  Scenario: The legacy free-form DEVOPS decision-question prose is gone after migration
    Given the real shipped DEVOPS command that the legacy decision-question prose is removed from exists
    And a clause registering the legacy free-form decision-question marker
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is FAIL with exit code 1 because the legacy marker is absent
    And the verdict names the legacy free-form decision-question clause

  @contract-shape:bounded-change @ac-8-non-regression @slice-03
  Scenario: DEVOPS still instruments outcome KPIs after the legacy prose is removed
    Given the real shipped DEVOPS agent that the KPI-traced observability floor lives in exists
    And a clause asserting the KPI-traced observability wording is preserved
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0 because the KPI-traced observability is preserved
