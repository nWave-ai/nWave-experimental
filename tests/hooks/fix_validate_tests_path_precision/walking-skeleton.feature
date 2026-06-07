@feature-fix-validate-tests-path-precision @slice-01 @walking_skeleton @driving_port
Feature: Pre-commit test scoping isolates a staged test file to its own feature directory
  As an nWave developer staging an unrelated commit while a sibling feature
    has a RED scaffold in flight
  I want the pre-commit test-scope resolver to scope staged test files to the
    deepest meaningful feature directory (capped at four path segments) instead
    of the top-level test-layer directory
  So that a sibling feature's RED scaffold cannot block my orthogonal commit
    and the daily backup-move workaround disappears

  # Carpaccio slice-01 (single slice — small-fix shape per nw-bugfix Phase 3).
  # RCA in docs/backlog.md friction #15: scripts/hooks/validate_tests.py line 113-118
  # uses parts[1] (2-level path = top-level test dir), so staging a file under
  # tests/des/cli/foo/test_x.py expands scope to tests/des/ and runs the entire
  # tests/des/ tree (3000+ tests). When any sibling RED scaffold exists under a
  # different feature dir, the commit is blocked even though the staged file is
  # in a completely unrelated feature. The fix caps depth at 4 path segments
  # (tests/{layer}/{tier}/{feature}/) and trims to the deepest existing prefix.
  #
  # CONTRACT SOURCE: this slice is authored against
  # docs/feature/fix-validate-tests-path-precision/feature-delta.md
  # ## Wave: DISTILL / [REF] Scenario list.
  #
  # Driving port: scripts/hooks/validate_tests.py::get_targeted_test_dirs
  # (the function the pre-commit hook invokes; not the subprocess that pytest
  # itself runs — the unit-under-test is the scope-resolver helper).
  #
  # Per Mandate-13: ATs MUST drive via this function entry point loaded via
  # importlib (already the existing tests/hooks/test_validate_tests.py pattern).
  # Subprocess (git diff --cached) is monkeypatched per scenario; the real
  # filesystem under tmp_path is used so Path(d).is_dir() checks are honest.

  Background:
    Given the pre-commit test-scope resolver is loaded as the driving port

  @error @us-isolate-sibling-red-scaffold @real-io @contract-shape:pure-function @slice-01
  Scenario: A staged file under a feature directory does not pull in a sibling feature's tree
    Given the staged file list is exactly "tests/des/acceptance/fix_robustness_pbt_density_gate/walking-skeleton.feature"
    And the directories "tests/des/acceptance/fix_robustness_pbt_density_gate" and "tests/des/cli/fix_contract_gate_digest_undercount" both exist on disk
    When the resolver computes the targeted test directories
    Then the resulting scope contains "tests/des/acceptance/fix_robustness_pbt_density_gate/"
    And the resulting scope does not contain "tests/des/cli/fix_contract_gate_digest_undercount/"
    And the resulting scope does not contain "tests/des/"

  @us-cap-depth-at-four @real-io @contract-shape:pure-function @slice-01
  Scenario: Deeply nested staged file scopes to the four-level feature directory only
    Given the staged file list is exactly "tests/des/cli/fix_contract_gate_digest_undercount/regressions/edge_cases/test_deep.py"
    And the directory "tests/des/cli/fix_contract_gate_digest_undercount" exists on disk
    When the resolver computes the targeted test directories
    Then the resulting scope contains exactly "tests/des/cli/fix_contract_gate_digest_undercount/"

  @us-preserve-shallow-paths @real-io @contract-shape:pure-function @slice-01
  Scenario: A two-segment conftest path keeps top-level scope so existing shallow behaviour is unchanged
    Given the staged file list is exactly "tests/des/conftest.py"
    And the directory "tests/des" exists on disk
    When the resolver computes the targeted test directories
    Then the resulting scope contains exactly "tests/des/"
