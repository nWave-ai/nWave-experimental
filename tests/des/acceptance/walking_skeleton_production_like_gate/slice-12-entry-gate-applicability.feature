@feature-walking-skeleton-production-like-gate
Feature: An installer-shipped feature must declare a walking-skeleton test up front
  As an nWave framework developer starting a feature
  I want the entry gate to require a walking-skeleton test when the feature
    ships an installer artifact
  So that the missing-test gap is caught at the first slice, not at feature-end

  # carpaccio slice-12 (DESIGN slice-06, part 1 of 2). Carpaccio entry-gate
  # extension: when a feature ships a CLI/hook/installer artifact the entry gate
  # asserts a `@walking-skeleton` scenario exists. Layer 3 (subprocess / FS
  # acceptance): real composition root, example-only, no PBT (Mandate 9/11).
  # The applicability decision over the feature-shape axis is a finite
  # Cartesian -> parametrize-collapse.
  #
  # Driving port: the carpaccio entry-gate (`des.cli.carpaccio_slice_gate`).

  # The installer-shipped predicate -- one behavioural shape, one row per
  # feature artifact shape. The four shipping shapes require a walking
  # skeleton; the docs-only shape does not.
  @slice-12 @driving_port @contract-shape:bounded-change
  Scenario Outline: The entry gate's applicability verdict over each feature shape
    Given a feature that <feature_shape>
    And the feature carries a walking-skeleton acceptance test
    When the carpaccio entry gate evaluates the feature at slice-one entry
    Then the entry gate records the feature applicability as <applicability>

    Examples: a feature shipping any installer artifact is in scope
      | feature_shape                 | applicability  |
      | ships a packaged CLI module   | applicable     |
      | ships a hook                  | applicable     |
      | ships a script-mode CLI       | applicable     |
      | ships an installer change     | applicable     |
      | ships only documentation      | not applicable |

  @slice-12 @driving_port @error @contract-shape:bounded-change
  Scenario: An installer-shipped feature without a walking-skeleton test is blocked at entry
    Given a feature that ships a packaged CLI module
    And the feature carries no walking-skeleton acceptance test
    When the carpaccio entry gate evaluates the feature at slice-one entry
    Then the entry gate fails naming the missing walking-skeleton test
    And the feature cannot enter slice-one

  @slice-12 @driving_port @contract-shape:bounded-change
  Scenario: A documentation-only feature without a walking-skeleton test enters slice-one
    Given a feature that ships only documentation
    And the feature carries no walking-skeleton acceptance test
    When the carpaccio entry gate evaluates the feature at slice-one entry
    Then the entry gate records the feature applicability as not applicable
    And the feature may enter slice-one
