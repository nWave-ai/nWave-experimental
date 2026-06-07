@feature-simplify-atdd-pure-carpaccio-spine
Feature: A real slice ships through the simplified spine end to end

  The Definition of Done claims a multi-slice atdd_pure feature delivers with
  zero manual file parking and zero reverify invocations, every PROCEED backed
  by mechanical evidence. Slices 01-03 were built on the OLD spine -- they
  cannot prove that claim. This slice is the honest proof: a thin real slice run
  ON the simplified spine itself.

  It delivers a slice the new way -- the feature-scoped gates clear, the exit
  gate records the slice -- and it demonstrates the involuntary backstop by
  exercising the flow with the exit gate deliberately skipped and showing the
  commit refused FROM WITHIN the flow. The backstop is not poked standalone:
  the slice-04 proof is the whole four-phase flow, end to end, and the M-2
  refusal is observed as a step of that flow.

  Read in sequence after slice-03: slice-03 restored involuntariness; this slice
  exercises the whole simplified spine on a real slice and confirms the
  park/reverify dance is gone and that an unverified slice cannot ship -- whether
  the slice's ATs never went GREEN or the exit gate was skipped.

  # Driving port: the simplified spine itself (the 4-phase hand-orchestrated
  # flow over the slice-01..03 CLIs + the M-2 hook). Layer 4 (walking-skeleton
  # / E2E) -- example-only, traditional assertions (Mandate 9 / Mandate 11).
  #
  # SUT decision table -- the new-spine delivery flow has exactly these
  # flow-owned outcomes:
  #   * happy        -- slice ATs GREEN, every phase clears, exit gate run:
  #                     the slice ships with one SliceCommitVerified record,
  #                     zero park, zero reverify (scenario 1).
  #   * unverified   -- the slice cannot ship: either its ATs never reached
  #                     GREEN at A_GREEN, or the exit gate was skipped before
  #                     D_REFACTOR_COMMIT. Both end the same way -- the flow
  #                     produces no SliceCommitVerified record and the M-2
  #                     backstop refuses the slice commit (the error Outline).
  # The predecessor-not-verified outcome is owned by the carpaccio_slice_gate
  # entry CLI and is witnessed by the slice-01 / slice-03 entry-gate ATs; the
  # new-spine flow delegates to that CLI, so it is not re-witnessed here (it is
  # not a flow-owned row, and carpaccio caps slice-04 at <= 3 scenario blocks).

  Background:
    Given a feature project on the simplified atdd_pure spine

  @slice-04 @walking_skeleton @wiring_e2e @driving_port @contract-shape:bounded-change
  Scenario: A slice delivered on the new spine ships with zero manual recovery
    Given a thin real slice ready to deliver on the simplified spine
    When the slice is delivered through the simplified four-phase flow
    Then the slice ships with a SliceCommitVerified record
    And no file was manually parked and no reverify was invoked

  @slice-04 @error @driving_port @contract-shape:bounded-change
  Scenario Outline: The simplified flow refuses to ship an unverified slice
    Given a thin real slice ready to deliver on the simplified spine
    And the flow is run with <flaw>
    When the slice is delivered through the simplified four-phase flow
    Then the involuntary backstop refuses the slice commit during the flow
    And the slice ships with no SliceCommitVerified record

    Examples:
      | flaw                                       |
      | the slice acceptance tests left RED        |
      | the slice-commit exit gate skipped         |
