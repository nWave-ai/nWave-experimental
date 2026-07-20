@feature-parallel-work-cleans-up-after-merge-back @slice-03
# Feature: A bugfix's cleanup never waits on a feature-end it doesn't owe.
#          Charter: docs/product/expectations/parallel-work-cleans-up-after-merge-back/
#          a-bugfixs-cleanup-never-waits-on-a-feature-end-it-doesnt-owe.md
# Slice: 03 (feature-delta Slice Plan row slice-03, Locked Decisions D-4/D-5,
#         ADR-SWARM-002). depends-on slice-01: REUSES the SAME mechanism
#         slice-01 introduces (`des verify-worktree-cleanup` CLI,
#         `WorktreeCleanupService`, D-D6: "this service never imports or
#         touches AtCompletionLedgerPort... protected BY CONSTRUCTION").
#
# -- WHAT'S GENUINELY NEW HERE (not a re-run of AT-CLEANUP-5) --
# Slice-01's own AT-CLEANUP-5 already pins the WRITE-side half of D-D6 in
# EVERY one of its 5 scenarios ("new_feature_end_pending_count == 0" is a
# universal invariant asserted on every sweep outcome, per that file's own
# harness-bugfix note). The facet slice-01 never exercised is the
# READ/WAIT-side half the charter's own oracle names explicitly: a
# feature-end-pending record ALREADY sitting in the ledger (for an unrelated
# unit of work) must neither block, delay, nor alter THIS unit of work's own
# cleanup outcome -- for EITHER a bugfix-flavored or a feature-slice-flavored
# worktree (D-5 uniformity, no persona special-casing). Every scenario here
# chains from a NEW precondition slice-01 never seeded: an EXISTING
# `FeatureEndPending` ledger record for an unrelated feature, present BEFORE
# the sweep under specification even runs.
#
# -- DRIVING PORT (Mandate-13, invariant 1+2) --
# Same driving port as slice-01/02: the REAL `des verify-worktree-cleanup`
# CLI, driven IN-PROCESS through the SAME production `des.cli.__main__`
# dispatcher (`run_cli_in_process`). No new @walking_skeleton here -- the
# feature's ONE subprocess scenario already lives in slice-01
# (AT-CLEANUP-1).
#
# -- Fixture reuse (Test Reuse & Consolidation, feature-delta) --
# `PendingFeatureEndFixture` (composition_slice_03.py) EXTENDS slice-01's
# `WorktreeCleanupFixture` with exactly ONE new capability --
# `seed_existing_feature_end_pending()` -- and reuses every other fixture
# method verbatim. The When/Then vocabulary is REUSED VERBATIM from
# slice-01's own step module (`steps_slice_01_worktree_cleanup` --
# `when_maintainer_runs_sweep_in_process`, `when_maintainer_runs_sweep_check_
# only`, `then_worktree_is_gone`, `then_sweep_reports_clean_exit_code`,
# `then_sweep_reports_refusal_exit_code`, `then_refusal_names_what_why_how`,
# `then_worktree_remains_registered_check_only`) -- Pillar 2 chained
# narrative + step-reuse: those Then bodies already assert
# `new_feature_end_pending_count == 0` as part of their combined
# `assert_state_delta` call, which is EXACTLY the read/wait-side proof this
# slice needs (the DELTA stays 0 whether the pre-seed count was 0 or 1).
# Only the 2 new Given steps below (`steps_slice_03_feature_end_decoupling
# .py`) are authored fresh.
#
# -- Mechanical assertion (Mandate-13 invariant 5) --
# Python + git + filesystem only, cross-OS. The pre-existing ledger record is
# a REAL `AtCompletionLedger.append_gate_event` write under `tmp_path`,
# re-read via the SAME real ledger the sweep itself would read.
#
# Universe (Mandate 8): {outcome.exit_code, outcome.worktree_removed,
# outcome.still_registered, outcome.entry_count, outcome.has_what_why_how,
# outcome.new_feature_end_pending_count} -- IDENTICAL to slice-01's own
# SWEEP_UNIVERSE (verbatim reuse, no new universe declared).
#
# Layer 3 (real git repo + real ledger JSONL, @real-io): example-only
# (Mandate 9 v2). No PBT machinery imported -- sad paths enumerated
# explicitly (Mandate 11). Scenario 3 is the sad path (a done-check refusal
# that must STILL prove zero feature-end coupling).
#
# Carpaccio: 3 counted scenarios, a 1:1-ish induction from the charter's own
# 4 oracle bullets (bullets 1+3, both bugfix-persona, combine into scenario
# 1; bullet 2 is scenario 2; bullet 4 is scenario 3) -- no over-authoring
# beyond the charter's own oracle.

Feature: A bugfix's cleanup never waits on a feature-end it doesn't owe
  As a maintainer closing a bugfix (or a feature slice) through its ephemeral worktree
  I want that unit of work's cleanup to complete on its own, uninfluenced by any feature-end state
  So that I am never held open waiting on an obligation my unit of work never owed

  # ---------------------------------------------------------------------
  # Realizes: charter bullets 1 + 3 (bugfix, positive + negative). A
  # feature-end-pending record already exists for SOMEONE ELSE'S work --
  # this bugfix's own cleanup must be totally unaffected by it.
  # ---------------------------------------------------------------------
  @slice-03 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R9
  Scenario: A bugfix's cleanup succeeds and stays fully done even while a feature-end record is already pending for other work
    Given a worktree named for a bugfix, whose branch is confirmed merged into the target branch and still registered
    And a feature-end-pending record already exists for an unrelated unit of work
    When the maintainer runs the cleanup sweep in-process
    Then the worktree is gone from the repository's registered worktrees
    And the sweep reports a clean exit code of 0

  # ---------------------------------------------------------------------
  # Realizes: charter bullet 2 (D-5 uniformity) -- the IDENTICAL mechanism,
  # no pre-seeded ledger record needed, applied to a feature-slice-flavored
  # worktree -- proving no persona special-casing exists either way.
  # ---------------------------------------------------------------------
  @slice-03 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R10
  Scenario: A feature slice's cleanup completes the identical way, independent of feature-end
    Given a worktree named for a feature slice, whose branch is confirmed merged into the target branch and still registered
    When the maintainer runs the cleanup sweep in-process
    Then the worktree is gone from the repository's registered worktrees
    And the sweep reports a clean exit code of 0

  # ---------------------------------------------------------------------
  # Realizes: charter bullet 4 (negative) -- cleanup must never trigger,
  # start, or require a feature-end run as a side effect, EVEN on the
  # refusal path (a lingering worktree the done-check correctly refuses).
  # ---------------------------------------------------------------------
  @slice-03 @driving_port @real-io @negative @contract-shape:unbounded-preservation @covers-R11
  Scenario: A cleanup sweep never triggers a feature-end run, even when the done-check refuses a lingering worktree
    Given a worktree named for a bugfix, whose branch is confirmed merged into the target branch and still registered
    And a feature-end-pending record already exists for an unrelated unit of work
    When the maintainer runs the cleanup sweep in-process as a done-check only
    Then the sweep reports a refusal exit code of 1
    And the refusal names what, why, and how to fix it
    And the worktree remains registered because a done-check never mutates
