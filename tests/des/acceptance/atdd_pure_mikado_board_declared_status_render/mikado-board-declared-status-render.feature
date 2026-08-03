@feature-unified-slice-progress-visualization
Feature: The Mikado board renders a slice's status exactly as the Slice Plan declares it

  Ale runs several delivery lanes in parallel across worktrees. Today three
  independent readers reason about "what state is this slice in": the
  feature-delta Slice Plan (DISTILL-authoritative), nw-throughput's own
  scheduling reasoning, and the Mikado board's own ad hoc free-text parser --
  three sources that can silently drift out of agreement (F12, JOB-028). This
  slice retires the board's ad hoc parser for ONE feature's view and replaces
  it with a direct, read-only projection of the Slice Plan: the thinnest
  walking skeleton that proves a shared model CAN represent what the board
  needs, before any scheduling or parallel-view investment is built on top
  (Locked Decision D5).

  # slice-01 of `unified-slice-progress-visualization` (JOB-028, D4/D5,
  # DES-1/DES-2/DES-7). Driving port: `des mikado-board render --feature
  # <feature-id>` (src/des/cli/mikado_board.py, CREATE_NEW) composing
  # `slice_progress_projection.project_slice_progress`
  # (src/des/domain/slice_progress_projection.py, CREATE_NEW), which reads
  # ONLY the Slice Plan's declared Status column at this slice -- no
  # scheduling state, no declared lanes yet (DESIGN Handoff: those land in
  # slice-02).
  #
  # Layer 2 in-process by default: every non-walking-skeleton scenario below
  # drives the real `des.cli.__main__.main` in-process (P1-P4 active-RED
  # pattern, nw-distill-red-scaffolding) -- it NEVER imports
  # `des.cli.mikado_board` at module top, since that module does not exist
  # until DELIVER creates it; the absence surfaces as a runtime dispatch
  # failure inside the in-process call, not a collection error. The ONE
  # `@walking_skeleton` scenario below is this FEATURE's single subprocess-e2e,
  # proving the installed `des` entry point is wired end-to-end.
  #
  # Contract pinned here (CT-5 narrowed to declared_status only, per the
  # DESIGN handoff's slice-01 scope; DES-1 "composed fresh on every read,
  # never a 4th persisted copy"; DES-7 retirement of `read_slice_progress`):
  #   * declared-status-verbatim -- the rendered status for a slice equals
  #     the Slice Plan row's Status column, byte-for-byte, in document order.
  #   * never-stale -- because the projection is composed fresh on every
  #     read (never cached), a Slice Plan edit is reflected on the very next
  #     render, with no restart and no re-registration needed.
  #   * missing-source refuses LOUD -- an absent feature-delta or an
  #     absent/malformed Slice Plan section is refused with WHAT/WHY/HOW,
  #     never silently rendered as an empty board.
  #
  # A companion Hypothesis property test
  # (steps/test_declared_status_render_property.py) pins the layer-1/2
  # PBT-full invariant (Mandate 9) over an unbounded number of generated
  # Slice Plan rows through this SAME driving surface -- never a direct
  # domain-function call (Mandate 13).

  Background:
    Given a repository with a feature directory

  @wiring_e2e @walking_skeleton @slice-01 @driving_port @contract-shape:pure-function @covers-R1
  Scenario: Ale opens the board and sees a slice's status rendered exactly as the Slice Plan declares it
    Given the Slice Plan for feature "board-render-demo" declares slice-01 as "pending" and slice-02 as "shipped"
    When Ale opens the real Mikado board for that feature
    Then the board shows slice-01 as "pending" and slice-02 as "shipped"
    And the shown statuses are read from the Slice Plan itself, not re-derived

  @slice-01 @driving_port @contract-shape:pure-function @covers-R1
  Scenario: A Slice Plan with a single slice still renders that one slice
    Given the Slice Plan for feature "board-render-demo" declares only slice-01 as "pending"
    When Ale opens the Mikado board for that feature
    Then the board shows exactly one slice, slice-01, as "pending"
    And the render leaves the feature-delta unchanged

  @slice-01 @driving_port @contract-shape:pure-function @covers-R1
  Scenario: A Slice Plan with many slices renders every one of them in document order
    Given the Slice Plan for feature "board-render-demo" declares 12 slices in document order
    When Ale opens the Mikado board for that feature
    Then the board shows all 12 slices in the same order as the Slice Plan

  @slice-01 @driving_port @negative @contract-shape:pure-function @covers-R1
  Scenario: The board never keeps showing a slice's previous status after the Slice Plan changes
    Given the Slice Plan for feature "board-render-demo" declares slice-01 as "pending"
    And Ale has already opened the Mikado board for that feature
    When the Slice Plan is edited to declare slice-01 as "shipped"
    And Ale opens the Mikado board for that feature again
    Then the board shows slice-01 as "shipped"

  @slice-01 @driving_port @error @contract-shape:pure-function @covers-R1
  Scenario: The board refuses a Slice Plan that declares zero slices
    Given the feature-delta for "board-render-demo" carries a slice plan with a header but zero slice rows
    When Ale opens the Mikado board for that feature
    Then the board refuses, naming a malformed slice plan as the cause

  @slice-01 @driving_port @error @contract-shape:pure-function @covers-R1
  Scenario: The board refuses to render a feature with no feature-delta on disk
    Given feature "board-render-demo" has no feature-delta on disk
    When Ale opens the Mikado board for that feature
    Then the board refuses, naming the missing feature-delta as the cause
    And the refusal names how to fix it

  @slice-01 @driving_port @error @contract-shape:pure-function @covers-R1
  Scenario Outline: The board refuses to render a feature whose Slice Plan is missing or malformed
    Given the feature-delta for "board-render-demo" carries <slice plan>
    When Ale opens the Mikado board for that feature
    Then the board refuses, naming <cause> as the cause

    Examples: structurally unsound slice plans
      | slice plan                           | cause                   |
      | no slice-plan section at all          | a missing slice plan    |
      | a slice plan with only four columns   | a malformed slice plan  |
