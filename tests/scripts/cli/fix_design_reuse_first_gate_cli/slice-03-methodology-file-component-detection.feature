@feature-fix-design-reuse-first-gate-cli @slice-03
Feature: The reuse-first CLI detects NEW methodology file-components from the commit range

  slice-02 detects NEW components by grepping added src/** files for class
  declarations. A methodology artifact -- a data SSOT under nWave/data, a skill
  under nWave/skills, a gate under scripts/cli -- is a NEW component too, but it
  is a FILE, not a Python class: the class-grep unit never sees it. A new
  nWave/data/dor-items.yaml therefore ships unchallenged -- a vacuous PASS where
  a parallel methodology SSOT slips past the reuse-first check.

  slice-03 adds a second detection unit dispatched by path kind: an added file
  under a methodology-path kind is itself a NEW component, keyed by its path and
  stem, requiring a Reuse Analysis row -- exactly as a src/** class does. The
  two units compose: the NEW component count is the union across class-components
  and methodology file-components. The artifact the architect's commits genuinely
  added, but never reasoned about in the Reuse Analysis, is caught from the
  commits themselves whether it is a class or a methodology file.

  # DDD-8 / DDD-9 / DDD-10 / DDD-11. Driving port:
  # scripts/cli/check_reuse_first_design.py invoked via main(argv). Driven ports
  # (real I/O): a real feature repository under tmp_path (real commits adding a
  # class file and/or a methodology file) plus the feature-delta on the real
  # filesystem. The detector reads the feature's real commit-range name-status
  # (added paths) -- file-component mode keys methodology paths WITHOUT reading
  # their bytes (DDD-11), composing with the class-component grep of slice-02.
  # Layer 3 (FS + subprocess acceptance) with a real driven adapter -> @real-io,
  # example-based, assert_state_delta (Mandate 9 v2 OR-reduction: at least one
  # real driven adapter -> example-based, no PBT). Finite verdict set
  # (PASS / FAIL / preservation) -> example scenarios, no @given.

  Background:
    Given a feature with methodology paths whose source tree is tracked in a repository

  @slice-03 @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: A feature whose committed class and methodology file are both named in the Reuse Analysis clears the reuse-first check
    Given the feature's commits add a NEW class to the source tree
    And the feature's commits add a NEW methodology file under "nWave/data"
    And the feature names both the NEW class and the NEW methodology file in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature's commit range with methodology detection
    Then the methodology-aware commit range passes the reuse-first check
    And the methodology-aware reuse-first check reports two NEW components
    And the reuse-first check with methodology detection leaves the feature repository unchanged

  @slice-03 @error @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: A feature whose committed methodology file is absent from the Reuse Analysis is rejected
    Given the feature's commits add a NEW methodology file under "<methodology_path>"
    And the feature does not name that NEW methodology file in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature's commit range with methodology detection
    Then the methodology-aware commit range is rejected by the reuse-first check
    And the methodology-aware reuse-first check reports one NEW component
    And the reuse-first check with methodology detection leaves the feature repository unchanged

    Examples:
      | methodology_path |
      | nWave/data       |
      | nWave/skills     |
      | scripts/cli      |

  @slice-03 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: Running the reuse-first check with methodology detection mutates no observable
    Given the feature's commits add a NEW methodology file named in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature's commit range with methodology detection
    Then the reuse-first check with methodology detection produced a structured verdict for the commit range
    And the reuse-first check with methodology detection leaves the feature repository unchanged
