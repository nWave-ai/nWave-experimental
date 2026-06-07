@feature-fix-distribution-boundary-dev-mode
Feature: Editable distribution boundary auto-detects dev checkout via .git adjacency

  As an nWave operator working on the framework itself (or any per-language adapter)
  I want the hook subprocess to load `des` from repo `src/` when invoked from a
  git checkout
  So that src/ edits propagate immediately without reinstall ceremony
  And customer installs (no .git/ ancestor) preserve fail-closed installed-copy behavior byte-identical
  And the resolver is filesystem-level, language-neutral (TS/Go/Rust adapters
  use the same walk shape)

  Background:
    Given the distribution boundary resolver `find_git_root` is loaded

  @walking_skeleton @driving_port @in-process @real-io @slice-01 @dev-checkout @contract-shape:pure-function
  Scenario: Dev checkout with .git/ at start path returns that path as repo root
    Given a tmp directory containing a `.git/` subdirectory
    When the resolver walks parents from inside that tmp directory
    Then the resolver returns the tmp directory absolute path

  @driving_port @in-process @real-io @slice-01 @dev-checkout @contract-shape:pure-function
  Scenario: Dev checkout with .git/ in ancestor returns the ancestor path
    Given a tmp directory containing a `.git/` subdirectory and a nested subdirectory `child/grandchild/`
    When the resolver walks parents from the `child/grandchild/` subdirectory
    Then the resolver returns the tmp directory absolute path (not the grandchild)

  @driving_port @in-process @real-io @slice-01 @customer @contract-shape:unbounded-preservation
  Scenario: Customer host without .git/ in any ancestor returns None
    Given a tmp directory with NO `.git/` directory anywhere in its tree
    When the resolver walks parents from inside that tmp directory
    Then the resolver returns None
    And the customer install fail-closed behavior is preserved (resolver returns no path)
