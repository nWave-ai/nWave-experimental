@feature-fix-design-reuse-first-gate-cli @slice-04
Feature: The reuse-first CLI accepts an overridable base branch and scoped source tree

  PARKED (D2-clean off the tests/ collection path per the atdd_pure per-slice
  JIT discipline). slice-02 ships the real git-diff core with conventional
  defaults (trunk = master, scope = src/). slice-04 makes both overridable: the
  architect may measure the feature against a non-default trunk and may scope
  which part of the tree counts as feature code. A component introduced outside
  the scoped source tree is not a feature component and does not require a
  Reuse Analysis row. These are deferred configurability polish, separable from
  the methodology-coverage fix (slice-03), so they do not gate it.

  Relocate this feature back under
  tests/scripts/cli/fix_design_reuse_first_gate_cli/ when slice-04 enters
  DELIVER. Its step bindings reuse the slice-02 composition harness
  (run_check_on_range already accepts base_branch / scoped_path overrides; the
  init_repository branch-rename path and the AddedPathKind out-of-scope builder
  already exist) -- the parked steps file lives alongside this feature.

  # DDD-7. Driving port: scripts/cli/check_reuse_first_design.py via main(argv).
  # New optional flags --base-branch (default master) + --scoped-path (default
  # src). Driven ports (real I/O): real feature repository under tmp_path.
  # Layer 3, @real-io, example-based (Mandate 9 v2 OR-reduction). The
  # base-branch x scoped-path space is a finite decision table -> Scenario
  # Outline parametrize density.

  Background:
    Given a feature whose source tree is tracked in a repository

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: The reuse-first check measures the feature against the chosen base branch
    Given the feature's commits diverge from the base branch "<base_branch>"
    And the feature's commits add a NEW component named in its Reuse Analysis section
    When the architect runs the reuse-first check against base branch "<base_branch>"
    Then the feature's commit range passes the reuse-first check
    And the reuse-first check reports one NEW component

    Examples:
      | base_branch |
      | master      |
      | trunk       |

  @slice-04 @error @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: A NEW component outside the scoped source tree is not a feature component
    Given the feature's commits add a NEW component under "<added_path>"
    And the feature does not name that NEW component in its Reuse Analysis section
    When the architect runs the reuse-first check scoped to "<scoped_path>"
    Then the feature's commit range <verdict> the reuse-first check
    And the reuse-first check reports <component_count> NEW components

    Examples: in-scope component must be justified
      | added_path | scoped_path | verdict        | component_count |
      | src        | src         | is rejected by | one             |

    Examples: out-of-scope component is ignored
      | added_path | scoped_path | verdict        | component_count |
      | tools      | src         | passes         | zero            |
