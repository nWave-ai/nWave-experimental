@feature-fix-des-single-entry-point-consolidation @slice-02
Feature: slice-02 — every subcommand reachable through the dispatcher

  Architect's slice-02 ATs (AT-04, AT-05, AT-06) per feature-delta.md.
  Unparked 2026-05-24 (N2 night autonomous PRR push).

  Background:
    Given the nwave runtime is installed

  @contract-shape:pure-function @driving_port @real-io @parametrize-collapse
  Scenario Outline: Operator can ask any subcommand for its own help
    When the operator asks the "<subcommand>" subcommand for its help
    Then the subcommand exits successfully
    And the help output names the "<subcommand>" prog name

    Examples:
      | subcommand                   |
      | log-phase                    |
      | init-log                     |
      | verify-integrity             |
      | roadmap                      |
      | health-check                 |
      | verify-commit-trailers       |
      | verify-slice-commit          |
      | walking-skeleton-gate        |
      | walking-skeleton-done-gate   |
      | carpaccio-slice-gate         |
      | classify-features            |
      | convert-to-atdd-pure         |
      | reverify-slice-commit        |
      | verify-environmental-e2e    |
      | run-contract-gate            |
      | check-slice-at-completeness |

  @contract-shape:pure-function @driving_port @real-io @parametrize-collapse
  Scenario Outline: Every subcommand passes through argparse exit codes unchanged
    When the operator runs the "<subcommand>" subcommand with an unknown flag
    Then the subcommand exits with the underlying argparse exit code 2

    Examples:
      | subcommand                   |
      | log-phase                    |
      | init-log                     |
      | verify-integrity             |
      | roadmap                      |
      | health-check                 |
      | verify-commit-trailers       |
      | verify-slice-commit          |
      | walking-skeleton-gate        |
      | walking-skeleton-done-gate   |
      | carpaccio-slice-gate         |
      | classify-features            |
      | convert-to-atdd-pure         |
      | reverify-slice-commit        |
      | verify-environmental-e2e    |
      | run-contract-gate            |
      | check-slice-at-completeness |

  @contract-shape:unbounded-preservation @adapter-integration @real-io
  Scenario: The des dispatcher introduces no third-party import at runtime
    When the bundle scan inspects the shipped des package
    Then the bundle scan reports no forbidden import was added by the dispatcher
    And the existing forbidden-import set remains the contract surface
