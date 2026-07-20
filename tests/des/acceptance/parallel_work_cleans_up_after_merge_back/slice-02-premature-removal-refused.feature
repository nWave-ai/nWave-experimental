@feature-parallel-work-cleans-up-after-merge-back @slice-02
# Feature: Removing a worktree before its merge is confirmed is refused.
#          Charter: docs/product/expectations/parallel-work-cleans-up-after-merge-back/
#          removing-a-worktree-before-its-merge-is-confirmed-is-refused.md
# Slice: 02 (feature-delta Slice Plan row slice-02, Locked Decision D-3,
#         ADR-SWARM-002). depends-on slice-01: REUSES the SAME mechanism
#         slice-01 introduces (`des verify-worktree-cleanup` CLI,
#         `WorktreeCleanupService`, the `is_ancestor` state check, D-D4) --
#         "zero new plumbing" (feature-delta D-D4). This slice drives the
#         SAME CLI, scoped via `--worktree <path>` (DESIGN Open Question #3:
#         worktree identity is PATH-keyed) at a NOT-yet-merged worktree, and
#         pins the refusal D-3 already guarantees structurally: mutation is
#         reachable ONLY for a CLEANUP_DUE (confirmed-merged) entry -- never
#         for NOT_YET_MERGEABLE.
#
# -- DRIVING PORT (Mandate-13, invariant 1+2) --
# Same driving port as slice-01: the REAL `des verify-worktree-cleanup` CLI,
# driven IN-PROCESS through the SAME production `des.cli.__main__` dispatcher
# (`run_cli_in_process`). No new @walking_skeleton here -- the feature's ONE
# subprocess scenario already lives in slice-01 (AT-CLEANUP-1); every
# slice-02 scenario stays in-process.
#
# -- Fixture reuse (Test Reuse & Consolidation, feature-delta) --
# `PrematureRemovalFixture` (composition_slice_02.py) EXTENDS slice-01's
# `WorktreeCleanupFixture` -- same trunk-repo builder, same SHIPPED
# `GitWorktreeAdapter` substrate, same production driving surface. It adds
# ONLY the three observables this slice's oracle needs and slice-01 never
# needed: the SCOPED entry's own verdict string, an entry-level `reason`
# presence check (the self-explaining "message naming that the merge-back
# has not happened yet" the charter's oracle demands -- GDP-3, see below),
# and a direct, independent git-reachability read of the sealed commit (the
# charter's own oracle names `git log`/reachability explicitly, never
# solely the CLI's own payload). The Given step is REUSED VERBATIM from
# slice-01's step module (`given_worktree_with_branch_state`,
# `PHRASE_BY_TEXT` -- Pillar 2 chained narrative + step-reuse). Then/When
# steps are authored fresh here: reusing slice-01's own Then bodies verbatim
# would inherit an existing assert_state_delta universe-scoping gap in that
# file (an over-wide universe paired with an under-declared expected set --
# flagged to the team, not this agent's file to fix mid-flight) -- this
# file's own state-delta checks scope `universe` to exactly the key(s) each
# check declares, avoiding that trap by construction.
#
# -- GENUINE RED, not a characterization pin (empirically verified) --
# D-D4's structural guarantee (mutation unreachable for a NOT_YET_MERGEABLE
# entry) is ALREADY satisfied by slice-01's shipped code -- confirmed
# empirically: `target_verdict`/`worktree_removed`/`still_registered`/
# `commit_reachable` assertions alone were GREEN on the FIRST run, with zero
# new production code (`des verify-red-green` correctly REFUSED to record
# that as RED -- "every test PASSES pre-implementation... witnesses
# nothing"). The charter's own oracle demands more than the bare
# machine-readable verdict enum, though: "refused, WITH A MESSAGE naming
# that the merge-back has not happened yet" -- the shipped payload's
# `"verdict": "NOT_YET_MERGEABLE"` is a terse enum code, not a human-readable
# message, and no such message exists anywhere (JSON or stdout) for a
# `--worktree`-scoped attempt today. This slice pins that gap concretely: an
# ADDITIVE, entry-level `"reason": <str>` key (GDP-3 self-explaining,
# presence-checked, mirrors slice-01's own `has_what_why_how` pattern),
# present ONLY when a `--worktree`-scoped entry's verdict is
# NOT_YET_MERGEABLE. This IS new, small, CLI-layer-only plumbing (no
# domain/application/port change) -- distinct from D-D4's STRUCTURAL "zero
# new plumbing" claim about the removal-gating mechanism itself, which stays
# untouched. `outcome.has_reason` is genuinely RED today (verified: `des
# verify-red-green --record-red` succeeds once this Then-step is added).
#
# -- Mechanical assertion (Mandate-13 invariant 5) --
# Python + git + filesystem only, cross-OS. `commit_reachable` is re-derived
# from a REAL `git cat-file -e <sha>^{commit}` read in the trunk repo,
# independent of the CLI's own payload -- the charter's own oracle
# ("observe repository state directly with git worktree list and git log").
#
# Universe (Mandate 8): {outcome.target_verdict, outcome.has_reason,
# outcome.worktree_removed, outcome.still_registered,
# outcome.commit_reachable}. Internal fields (Popen handle, raw stdout
# bytes, adapter internals) NEVER appear.
#
# Layer 3 (real git repo + real trunk-repo fixture, @real-io): example-only
# (Mandate 9 v2). No PBT machinery imported -- sad paths enumerated
# explicitly (Mandate 11). All 3 scenarios ARE the sad path (D-3's refusal
# guarantee IS the value this slice ships) -- 100% error/edge coverage.
#
# Carpaccio: 3 counted scenarios, a 1:1 induction from the dispatch's own
# three named assertions ("--check-only reports NOT-DONE / ACT refuses
# removal / the commit is preserved") -- no over-authoring beyond slice-02's
# own charter oracle.

Feature: Removing a worktree before its merge is confirmed is refused
  As a maintainer (or an interrupted/retried automation)
  I want an early removal attempt refused while its commit's merge-back is unconfirmed
  So that I never orphan a commit that only exists in that worktree

  # ---------------------------------------------------------------------
  # Realizes: "--check-only reports NOT-DONE" (dispatch). The done-check is
  # a PURE read; a not-yet-merged worktree is reported, never mutated.
  # ---------------------------------------------------------------------
  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R6
  Scenario: A done-check on a not-yet-merged worktree reports it is not ready for cleanup
    Given a worktree whose branch is not yet merged into the target branch
    When the maintainer checks whether that worktree is ready for cleanup
    Then the worktree is reported as not yet mergeable
    And the done-check leaves the worktree registered without mutating it
    And the refusal names the reason the worktree was not removed

  # ---------------------------------------------------------------------
  # Realizes: "ACT refuses removal" (dispatch) -- THE core D-3 value: an
  # explicit removal attempt, not merely a passive sweep, is refused.
  # ---------------------------------------------------------------------
  @slice-02 @driving_port @real-io @negative @contract-shape:unbounded-preservation @covers-R6 @covers-R7
  Scenario: An attempt to remove a worktree before its merge-back is confirmed is refused
    Given a worktree whose branch is not yet merged into the target branch
    When the maintainer attempts to remove that worktree before its merge-back is confirmed
    Then the worktree is reported as not yet mergeable
    And the removal attempt is refused and the worktree remains registered
    And the refusal names the reason the worktree was not removed

  # ---------------------------------------------------------------------
  # Realizes: "+ the commit is preserved" (dispatch) -- the charter's own
  # git-log-observed oracle: a refused attempt must not orphan the commit.
  # ---------------------------------------------------------------------
  @slice-02 @driving_port @real-io @negative @contract-shape:unbounded-preservation @covers-R8
  Scenario: The commit sealed inside a not-yet-merged worktree stays reachable after a refused removal attempt
    Given a worktree whose branch is not yet merged into the target branch
    When the maintainer attempts to remove that worktree before its merge-back is confirmed
    Then the worktree's sealed commit is still reachable in the repository
