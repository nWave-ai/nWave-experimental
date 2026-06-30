@feature-f-design-devops-review-gate @walking_skeleton @driving_port @real-io
Feature: An architect's DESIGN output is mechanically gated by a review verdict

  An architect who returns a DESIGN output has that output MECHANICALLY GATED
  end-to-end: the DESIGN gate-out stack -- authored ONCE in the canonical
  flavor-independent wave-contract registry (nWave/waves/design.yaml) and resolved
  from there by the wired spine -- runs `verify-design-review`, which reads the
  latest DesignReviewVerdict ledger record, seals the feature-delta bytes, and
  REFUSES the return unless an artefact-current approved verdict exists. So "the
  architect-review was never run" blocks the DESIGN return instead of silently
  passing.

  Driving surface (Mandate-13 driving-port-only): TWO real wired seams, no
  direct-domain import for business logic.
    * Layer 3 composition -- the REAL spine `wave_gate_stack_dispatch.resolve_stack`
      reading the SHIPPED `nWave/waves/design.yaml` registry file (the entry the
      live SubagentStop gate-out caller uses, subagent_stop_service.py:311).
    * Layer 3 subprocess -- the REAL `des record-design-review` / `des
      verify-design-review` CLIs as black-box processes; the observable is the
      process exit code + the structured JSON verdict payload, nothing else.

  Synthetic substrate (precondition state, NOT the SUT): a tmp work-tree carrying
  a `docs/feature/<id>/feature-delta.md` the verdict seals against + the
  AT-completion ledger the verdict is recorded into. No fixture authors the
  expected verdict -- the verdict is recorded through the REAL producer CLI.

  # AT-1: the DESIGN gate-out fact has ONE authoring locus (the canonical registry),
  #       and the WIRED spine resolves it FROM there to the same gate-id sequence.
  #       Two independent reads (registry-FILE-declared vs spine-resolved) agree,
  #       proving the registry -> dispatcher wiring end-to-end (the walking skeleton).
  @slice-01 @feature-f-design-devops-review-gate @AT-1 @contract-shape:bounded-change
  Scenario: The wired spine resolves the DESIGN gate-out stack from the canonical registry
    Given the canonical wave-contract registry file for the DESIGN wave is shipped in the repo
    When the dispatcher resolves the DESIGN gate-out stack from the registry as the default source
    Then the resolved gate-id sequence equals the DESIGN gate-out sequence the registry file declares
    And the resolved DESIGN gate-out stack includes the verify-design-review gate

  # AT-2 (error path): a DESIGN return with NO recorded verdict -> the verify gate
  #       REFUSES it (INDETERMINATE "absent", exit 1). Absence reads as a veto,
  #       never as silent PASS.
  @slice-01 @feature-f-design-devops-review-gate @AT-2 @error @contract-shape:bounded-change
  Scenario: A DESIGN output with no recorded review verdict is refused
    Given a DESIGN feature with a feature-delta and no recorded review verdict
    When the DESIGN review-verdict gate is verified for that feature
    Then the gate refuses the DESIGN return with verdict indeterminate

  # AT-3 (happy path): after the solution-architect-reviewer's APPROVED verdict is
  #       recorded through the REAL producer CLI, the verify gate PASSES (exit 0,
  #       "no objection found") -- the record->verify loop closes end-to-end.
  @slice-01 @feature-f-design-devops-review-gate @AT-3 @contract-shape:bounded-change
  Scenario: A DESIGN output with an artefact-current approved verdict passes the gate
    Given a DESIGN feature with a feature-delta and no recorded review verdict
    When the solution-architect-reviewer records an approved review verdict for that feature
    And the DESIGN review-verdict gate is verified for that feature
    Then the gate passes the DESIGN return with verdict pass

  # AT-4 (error path): a recorded needs-revision verdict -> the verify gate VETOES
  #       the return (exit 1, vetoed) -- a reviewer veto is mechanically honored.
  @slice-01 @feature-f-design-devops-review-gate @AT-4 @error @contract-shape:bounded-change
  Scenario: A DESIGN output whose reviewer recorded needs-revision is vetoed
    Given a DESIGN feature with a feature-delta and no recorded review verdict
    When the solution-architect-reviewer records a needs-revision review verdict for that feature
    And the DESIGN review-verdict gate is verified for that feature
    Then the gate vetoes the DESIGN return with verdict vetoed
