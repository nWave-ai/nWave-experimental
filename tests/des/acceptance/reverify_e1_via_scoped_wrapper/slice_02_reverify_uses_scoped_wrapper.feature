@feature-fix-reverify-e1-via-scoped-wrapper @driving_port @real-io
@contract-shape:bounded-change
Feature: Reverify clears E1 against a slice tag shared across features
  As an operator re-verifying a buried slice in a multi-feature repository
  I want reverify's E1 gate to scope to my feature
  So that another feature's identically-tagged @slice-NN file cannot block
  recovery of my orphaned slice.

  # Decision-table rows witnessed by this slice:
  #   R4 (>=2 features sharing @slice-NN, feature-scoped) ... AT-(a) -- THE
  #     row the existing reverify ATs miss; the closing AT for this defect.
  #   R3 (single-feature, feature-scoped) ............... AT-(b) regression
  #     guard for the 10 existing reverify ATs (DESIGN open question:
  #     reviewer may collapse with the existing acceptance AT via parametrize).
  #
  # Contract shape is bounded-change: reverify's success path appends the
  # ledger pair (SliceCommitVerified + SliceReverified). Universe entries are
  # the typed reverify outcome enum (port-exposed via the JSON event field) +
  # the ledger's verified_slices set; assertions are typed-enum equality on
  # the outcome (sufficient for the layer-3 acceptance contract per Mandate 11).
  #
  # Driving port (Pillar 3): the real des.cli.reverify_slice_commit.main(argv)
  # in-process, against a real temp-git repo. Slice-01 ships the wrapper +
  # SSOT this slice's E1 invocation swap consumes.

  @slice-02
  Scenario: An operator recovers a slice when another feature shares the slice tag
    Given a repository with 2 features sharing the slice tag
    When the operator re-verifies the slice
    Then the reverify outcome is success

  @slice-02
  Scenario: An operator recovers a single-feature slice (regression-guard)
    Given a repository with 1 features sharing the slice tag
    When the operator re-verifies the slice
    Then the reverify outcome is success
