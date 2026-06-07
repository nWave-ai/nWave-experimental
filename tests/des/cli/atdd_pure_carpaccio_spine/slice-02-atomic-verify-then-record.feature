@feature-simplify-atdd-pure-carpaccio-spine
Feature: A slice commit is verified and recorded atomically, or not at all

  The U2 sequencer hook used to write the SliceCommitVerified ledger record, but
  hand-orchestration carries no sequencer dispatch marker, so the hook silently
  no-opped and the record the next slice's gate needs was never written (wall
  W3). This slice folds verification and recording into one CLI.

  The CLI runs two checks -- completeness (E1) then the feature-scoped contract
  gate (E2) -- and appends the SliceCommitVerified record IF AND ONLY IF both
  exit zero, in the same process. On any non-zero half the CLI exits non-zero
  and appends nothing: an unverified slice never leaves a record behind.

  The record is the carpaccio chain's evidence: slice-03's predecessor check
  and the M-2 commit backstop read SliceCommitVerified through the AT-completion
  ledger and fail-closed on any record missing its integrity fields. So this
  slice's contract is not merely "a record exists" but "a verified record lands
  on the substrate the chain reads, carrying the integrity fields, and a re-run
  does not corrupt the slice-ordering the chain depends on".

  Read in sequence after slice-01: slice-01 gave the orchestrator a trustworthy
  feature-scoped contract gate; this slice makes that gate one half of an atomic
  verify-then-record exit gate.

  # Driving port: the verify_slice_commit CLI with --feature-id (python -m).
  # Layer 3 (subprocess / FS acceptance) -- example-only sad paths (Mandate 11).
  # The negative case (E1/E2 fails -> no record) is the M-3 non-vacuity contract.
  # The ledger seam is the carpaccio chain's AT-completion ledger -- the AT
  # observes verified_slices(), not a path-agnostic substring scan.

  Background:
    Given a feature project with a multi-slice plan
    And a slice commit exists for the entering slice

  @slice-02 @driving_port @contract-shape:bounded-change @slice02_seam_scaffold
  Scenario: A verified slice is recorded on the substrate the carpaccio chain reads
    Given the slice commit passes both the completeness and contract checks
    When the orchestrator runs the slice-commit exit gate
    Then the slice-commit exit gate clears the slice
    And the entering slice is reported as verified to the carpaccio chain

  @slice-02 @error @driving_port @contract-shape:bounded-change @slice02_seam_scaffold
  Scenario Outline: A slice that fails either half of the exit gate records nothing
    Given the slice commit where <failure>
    When the orchestrator runs the slice-commit exit gate
    Then the slice-commit exit gate is refused
    And the carpaccio chain reports no verified slice

    Examples:
      | failure                     |
      | the contract gate fails     |
      | the completeness check fails |

  @slice-02 @driving_port @contract-shape:bounded-change @slice02_seam_scaffold
  Scenario: Re-running the exit gate on an already-verified commit keeps the slice verified exactly once
    Given the slice commit passes both the completeness and contract checks
    And the orchestrator has already run the slice-commit exit gate for the slice
    When the orchestrator runs the slice-commit exit gate again on the same commit
    Then the slice-commit exit gate clears the slice
    And the carpaccio chain still reports the slice as verified exactly once
