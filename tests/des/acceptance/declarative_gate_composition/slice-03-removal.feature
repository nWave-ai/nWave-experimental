@feature-f-declarative-gate-composition @slice-03 @infrastructure @real-io @contract-shape:bounded-change @JOB-026
Feature: The superseded imperative DISCUSS gate-stack branches are removed without dropping enforcement

  The imperative DISCUSS per-wave gate-stack branches (the `if markers.wave == "discuss"`
  gate-IN hinge plus the `_discuss_gate_out` / `_discuss_review_veto` gate-OUT branch)
  that the declarative wave_gate_stacks.discuss composition supersedes are removed and
  reconciled, so the codebase carries no stale imperative DISCUSS-gate-stack wiring
  duplicating the declared composition -- and the DISCUSS enforcement still vetoes.

  Removal-only consolidation slice (C10). Verified by ABSENCE (the shipped source no
  longer carries the superseded branch signatures) plus NON-REGRESSION (the DISCUSS
  gate-OUT still vetoes via the declared composition through the REAL service).

  # AT-8: absence of the stale imperative wiring + non-regression of the veto.
  @AT-8 @slice-03
  Scenario: The imperative DISCUSS branches are gone and the gate-out still vetoes
    Given the DISCUSS wave is migrated to the declarative composition
    When the codebase is inspected and the gate-out runs
    Then no imperative discuss gate-stack branch survives
    And the discuss gate-out still vetoes the infra-only slice plan
