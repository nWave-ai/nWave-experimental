@feature-fix-scorecard-freshness-audit-cli @slice-01
Feature: The freshness audit CLI reads a scorecard and reports which cells cite recent evidence

  The PRR scorecard (and the sister SF Distribution Gate, and the Tsunami
  detector tracker) emit assertions about system state with no built-in
  freshness probe. Empirical anchor 2026-05-24: F-01 (HMAC bootstrap
  "missing") was cited as a publish-blocker in the PRR scorecard but the
  producer (ReviewerSigningPlugin) had been shipped 2026-05-20 -- a stale
  cell silently re-blocked work that was already done.

  This CLI is the freshness probe. For every cell that cites an F-id, it
  asks the backing git history "is there a recent commit naming this F-id?"
  -- if yes, the cell is FRESH; otherwise STALE. Top-level verdict is PASS
  iff every cell is FRESH; otherwise FAIL. The CLI is read-only -- invoking
  it never mutates the scorecard.

  # Driving port: python -m scripts.cli.check_scorecard_freshness.
  # Layer 3 (subprocess / FS acceptance) -- example-based (Mandate 11).
  # The walking-skeleton ATs cover three of the seven Phase-2.5 completeness
  # categories: C1 happy-path, C6 error-path (stale detection), C7
  # preservation invariant (read-only contract verified via state-delta).
  # Slices 02+ cover the remaining categories (MISSING-cell shape,
  # MALFORMED_INPUT exit-2 shape, cron wiring, badge integration).

  Background:
    Given a project root with a backing git repository

  @slice-01 @driving_port @walking_skeleton @wiring_e2e @contract-shape:pure-function
  Scenario: The freshness audit accepts a scorecard whose every cell cites recent evidence
    Given the producer wave has recently landed commits for every cited F-id
    And the acceptance designer has authored a scorecard whose every cell cites a recently-landed F-id
    When the reviewer runs the freshness audit on the scorecard
    Then the freshness audit reports the scorecard as freshly verified

  @slice-01 @driving_port @error @contract-shape:pure-function
  Scenario: The freshness audit refuses a scorecard whose cell cites an F-id with no recent commit
    Given the producer wave has recently landed commits for one cited F-id but not another
    And the acceptance designer has authored a scorecard with one fresh cell and one stale cell
    When the reviewer runs the freshness audit on the scorecard
    Then the freshness audit reports the scorecard as failing freshness
    And the freshness audit names the stale cell so the reviewer can re-baseline it

  @slice-01 @driving_port @contract-shape:unbounded-preservation
  Scenario: The freshness audit invocation is read-only and leaves the scorecard file unchanged
    Given the producer wave has recently landed commits for every cited F-id
    And the acceptance designer has authored a scorecard whose every cell cites a recently-landed F-id
    When the reviewer runs the freshness audit on the scorecard
    Then the scorecard file content is unchanged after the audit runs
