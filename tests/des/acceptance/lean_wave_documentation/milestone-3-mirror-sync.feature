Feature: Marco reads in-flight feature scopes from a single master worktree mirror
  As Marco running parallel feature worktrees
  I want one explicit command that mirrors in-flight feature-deltas under the master worktree
  So that I can review every active feature scope from one open VSCode window without chasing worktree paths

  Background:
    Given Marco's master worktree is a fresh temporary repository

  @US-4 @driving_port
  Scenario: Sync populates the in-flight mirror with feature-deltas from active worktrees
    Given Marco has two feature worktrees registered with feature-delta files for "feat-alpha" and "feat-beta"
    When Marco runs the sync command from the master worktree
    Then the master worktree's in-flight mirror contains a copy of "feat-alpha"'s feature-delta
    And the master worktree's in-flight mirror contains a copy of "feat-beta"'s feature-delta
    And the in-flight mirror directory is gitignored

  @US-4 @driving_port
  Scenario: Sync is idempotent when source feature-deltas are unchanged
    Given Marco has previously synced the in-flight mirror for feature "feat-alpha"
    And "feat-alpha"'s feature-delta has not changed in its source worktree
    When Marco runs the sync command a second time
    Then the in-flight mirror entry for "feat-alpha" still matches the source worktree's feature-delta

  @US-4 @driving_port @error
  Scenario: Sync removes mirror entries for features that have been merged or whose worktrees no longer exist
    Given Marco's master worktree has an in-flight mirror entry for feature "feat-merged"
    And "feat-merged"'s feature-delta now lives at the merged location on the master worktree
    When Marco runs the sync command
    Then the in-flight mirror entry for "feat-merged" is removed
    And Marco sees an informational line announcing the mirror cleanup

  @US-4 @driving_port @error
  Scenario: Concurrent waves on parallel worktrees auto-merge cleanly through wave-owned sections
    Given Marco has two worktrees of the same feature checked out in parallel
    And worktree A has appended only to its DESIGN wave section
    And worktree B has appended only to its DISTILL wave section
    When both worktrees commit and Marco merges them
    Then the merge succeeds with no conflict markers
    And the merged feature-delta.md contains both new wave sections under their owned headings
