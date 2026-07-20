@feature-parallel-work-cleans-up-after-merge-back @slice-01
# Feature: A finished parallel unit of work's worktree disappears on its own.
#          Charter: docs/product/expectations/parallel-work-cleans-up-after-merge-back/
#          a-finished-parallel-unit-of-works-worktree-disappears-on-its-own.md
# Slice: 01 (the WALKING SKELETON, feature-delta Slice Plan row slice-01,
#         Locked Decisions D-2/D-3, ADR-SWARM-002). D-1 REUSE: `GitWorktreePort`
#         / `GitWorktreeAdapter` (des-refactor-fixer-swarm, SHIPPED) are
#         EXTENDED with `list_worktrees`, never rebuilt; this slice's fixtures
#         reuse the shipped adapter as SUBSTRATE (never the SUT) to build a
#         genuinely git-state-true "confirmed merged" precondition (D-D2).
#
# -- DISTILL-interim wire contract (feature-delta Open Question resolved
# concretely HERE, since nothing exists yet to reverse-engineer) --
# `des verify-worktree-cleanup --repo <path> --target-branch <name>
# [--check-only] [--worktree <path>]` emits a single-line
# `nwave.worktree_cleanup.v1` JSON report: {event, schema, entries:
# [{path, branch, verdict, removed}], and -- ONLY on exit 1 -- what/why/how
# (GDP-3)}. Exit 0 iff no CLEANUP_DUE entry remains unresolved after the run;
# exit 1 otherwise. Full contract:
# tests/des/acceptance/parallel_work_cleans_up_after_merge_back/steps/domain_types_slice_01.py
#
# -- DRIVING PORT (Mandate-13, invariant 1+2) --
# The driving port is the REAL `des verify-worktree-cleanup` CLI, driven
# in-process through the SAME production `des.cli.__main__` dispatcher every
# other `des <subcommand>` invocation uses -- EXCEPT the feature's single
# `@walking_skeleton` scenario, which forks the REAL installed `des`
# console-script (mirrors the shipped `blast-radius-measured-tier` slice-01
# precedent). NEVER a direct `from des.cli.verify_worktree_cleanup import
# main` at module top (P1 -- the module does not exist yet).
#
# -- RED reason (P1-P4 in-process active-RED) --
# `verify-worktree-cleanup` is not yet a registered `des` subcommand. Every
# in-process scenario observes the REAL current dispatcher behaviour ("des:
# error: argument subcommand: invalid choice: 'verify-worktree-cleanup'",
# exit 2) and fails with a semantic AssertionError comparing that to the
# contract this slice specifies -- never a naked traceback. The
# walking-skeleton scenario observes the identical dispatcher failure through
# a real subprocess fork.
#
# -- Mechanical assertion (Mandate-13 invariant 5) --
# Python + git + filesystem only, cross-OS. Every observable is re-derived
# from REAL git state (`git worktree list --porcelain`) and the REAL
# AT-completion ledger JSONL, independent of whether the CLI's own payload
# parses -- the RED reason is genuine missing business behaviour, never a
# parsing artifact of an absent module.
#
# Universe (Mandate 8): {outcome.exit_code, outcome.worktree_removed,
# outcome.still_registered, outcome.entry_count, outcome.has_what_why_how,
# outcome.new_feature_end_pending_count}. Internal fields (Popen handle,
# raw stdout bytes, adapter internals) NEVER appear.
#
# Layer 3 (real git repo + one real subprocess fork for the walking skeleton,
# @real-io): example-only (Mandate 9 v2 -- the driven set includes a real
# git subprocess seam => example-based, NOT PBT). Sad paths explicit
# (Mandate 11). No PBT machinery.
#
# Carpaccio: 5 counted scenarios, a 1:1 induction from the DESIGN wave's own
# `[REF] Architecture & Contract Tests` table (AT-CLEANUP-1..5) -- no
# over-authoring beyond what DESIGN already named as slice-01's scope.

Feature: A finished parallel unit of work's worktree disappears on its own
  As a maintainer driving a unit of parallel work through an ephemeral worktree
  I want its removal to fire as a mechanical consequence of a confirmed successful merge-back
  So that I never leave a worktree rotting, and never lose work by removing it too early

  # ─────────────────────────────────────────────────────────────────────────
  # AT-CLEANUP-1 -- THE WALKING SKELETON (feature-delta WS Strategy, the
  # feature's SINGLE @walking_skeleton scenario). Litmus: a non-technical
  # maintainer reads "my worktree was just gone, I never had to do anything."
  # contract-shape:bounded-change -- one declared mutation: the confirmed-
  # merged worktree (and only it) is removed.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @real-io @walking_skeleton @contract-shape:bounded-change @covers-R1
  Scenario: A confirmed successful merge-back removes its worktree without a manual step
    Given a worktree whose branch is confirmed merged into the target branch and still registered
    When the maintainer runs the cleanup sweep against the real installed des console-script
    Then the worktree is gone from the repository's registered worktrees
    And the sweep reports a clean exit code of 0

  # ─────────────────────────────────────────────────────────────────────────
  # AT-CLEANUP-2 -- IN-PROGRESS WORKTREE LEFT ALONE (D-D4: mutation is
  # structurally reachable only for a confirmed-merged entry). RED today.
  # contract-shape:unbounded-preservation -- the unmerged worktree is
  # preserved byte-for-byte, never touched.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R2
  Scenario: An in-progress worktree whose branch is not yet merged is left alone
    Given a worktree whose branch is not yet merged into the target branch
    When the maintainer runs the cleanup sweep in-process
    Then the worktree remains registered
    And the sweep reports a clean exit code of 0

  # ─────────────────────────────────────────────────────────────────────────
  # AT-CLEANUP-3 -- DONE-CHECK REFUSAL (D-2 enforcing gate, D-3 hard
  # ordering invariant's mirror image). CRITICAL negative, RED today.
  # contract-shape:unbounded-preservation -- --check-only NEVER mutates; the
  # lingering worktree survives the refused check byte-for-byte.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @real-io @negative @contract-shape:unbounded-preservation @covers-R3
  Scenario: The done-check refuses to call a unit of work finished while a merged worktree lingers
    Given a worktree whose branch is confirmed merged into the target branch and still registered
    When the maintainer runs the cleanup sweep in-process as a done-check only
    Then the sweep reports a refusal exit code of 1
    And the refusal names what, why, and how to fix it
    And the worktree remains registered because a done-check never mutates

  # ─────────────────────────────────────────────────────────────────────────
  # AT-CLEANUP-4 -- MAIN WORKTREE NEVER SWEPT (the new `list_worktrees`
  # capability's hard invariant). RED today.
  # contract-shape:unbounded-preservation -- a repo with zero linked
  # worktrees yields zero entries; the main worktree itself is never listed.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R4
  Scenario: A repository's own main worktree is never among the entries the sweep evaluates
    Given a trunk repository that has no linked worktrees registered at all
    When the maintainer runs the cleanup sweep in-process
    Then the sweep evaluates zero worktree entries
    And the sweep reports a clean exit code of 0

  # ─────────────────────────────────────────────────────────────────────────
  # AT-CLEANUP-5 -- ZERO FEATURE-END COUPLING (D-D6, protects the sibling
  # slice-03 decoupling guarantee BY CONSTRUCTION starting here). CRITICAL
  # negative, RED today (chains AT-CLEANUP-1's Given, Pillar 2).
  # contract-shape:unbounded-preservation -- the feature-end ledger surface
  # is untouched by any sweep outcome, positive or negative.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @real-io @negative @contract-shape:unbounded-preservation @covers-R5
  Scenario: A cleanup sweep never appends a feature-end-pending ledger record
    Given a worktree whose branch is confirmed merged into the target branch and still registered
    When the maintainer runs the cleanup sweep in-process
    Then the worktree is gone from the repository's registered worktrees
    And no feature-end-pending record is ever appended by the sweep

  # ─────────────────────────────────────────────────────────────────────────
  # AT-CLEANUP-6 -- DETACHED-HEAD WORKTREE IS NOT SILENTLY EXCLUDED (bugfix
  # regression, feature detached-worktree-excluded-from-cleanup-sweep). RCA:
  # `list_worktrees` dropped every entry lacking a `branch` line, so every
  # `git worktree add --detach` worktree (the scan's most common real shape
  # -- every ephemeral bugfix/swarm worktree this session) was silently
  # excluded from the sweep. Fix: classify via `head_sha` ancestry (already
  # the mechanism `_sweep_one` uses), never `branch` presence.
  # contract-shape:bounded-change -- one declared mutation: the confirmed-
  # merged detached worktree (and only it) is removed; no `delete_branch`
  # call is attempted (there is no branch to delete).
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @real-io @covers-R6
  Scenario: A confirmed-merged detached-HEAD worktree is swept and removed
    Given a detached-HEAD worktree whose HEAD is confirmed merged into the target branch and still registered
    When the maintainer runs the cleanup sweep in-process
    Then the worktree is gone from the repository's registered worktrees
    And the sweep reports a clean exit code of 0

  # ─────────────────────────────────────────────────────────────────────────
  # AT-CLEANUP-7 -- DETACHED-HEAD IN-PROGRESS WORKTREE LEFT ALONE (negative
  # regression guard, no regression on the negative path introduced by the
  # detached-HEAD fix).
  # contract-shape:unbounded-preservation -- the unmerged detached worktree
  # is preserved byte-for-byte, never touched.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @real-io @covers-R7
  Scenario: An in-progress detached-HEAD worktree that is not yet merged is left alone
    Given a detached-HEAD worktree whose HEAD is not yet merged into the target branch
    When the maintainer runs the cleanup sweep in-process
    Then the worktree remains registered
    And the sweep reports a clean exit code of 0
