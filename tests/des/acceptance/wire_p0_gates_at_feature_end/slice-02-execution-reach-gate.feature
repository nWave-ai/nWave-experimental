@feature-wire-p0-gates-at-feature-end @slice-02
Feature: The feature-end cycle refuses to sign a feature that ships a never-executed production file

  As the nWave maintainer running the feature-end cycle
  I want a feature that shipped a production file with zero recorded
    executions across its own verification to be refused at feature-end
  So that a never-run scaffold never ships as a signed "done" feature

  # wire-p0-gates-at-feature-end slice-02 (reuses slice-01's wiring pattern
  # against a second gate). Backlog: evolution-plan P0.4 row. Ground truth:
  # `des verify-execution-reach` (src/des/cli/verify_execution_reach.py) is
  # DONE, unit-tested 3/3, catalogued -- but `run_feature_end_cycle` never
  # invokes it. This scenario is the acceptance-level witness of the
  # already-authored unit oracle at tests/des/unit/application/
  # test_feature_end_cycle_execution_reach_gate.py::
  # test_never_executed_file_refuses_feature_end -- same fixture shape (a
  # Cobertura coverage.xml recording zero hits for a shipped production
  # file), reused here as the oracle rather than re-derived.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition): the real use-case entry
  #   point `run_feature_end_cycle(...)` -- the SAME function both `des
  #   feature-end run` and the SubagentStop hook shim invoke (DDD-7). Sibling
  #   legs (walking-skeleton, env-e2e, coverage-map, full-suite) are stubbed
  #   to PASS/NOT_APPLICABLE so this scenario isolates the NEW execution-
  #   reach leg; the execution-reach gate itself is NEVER stubbed -- it runs
  #   as a real `des verify-execution-reach` subprocess against a real
  #   Cobertura XML planted with a genuine zero-hit production file.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD `run_feature_end_cycle` does
  #   not yet call `verify-execution-reach` at all, so this scenario reaches
  #   a signed success regardless of the planted defect -- a genuine semantic
  #   AssertionError (expected refusal, got success), not a collection error.
  #   GREEN once DELIVER adds the execution-reach leg mirroring the existing
  #   legs' dispatch -> verdict-parse -> CycleRefusal-or-heartbeat shape (L-2).

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A never-executed production file blocks the feature-end signing
    Given a feature that ships a production file with zero recorded executions
    When the nWave maintainer runs the feature-end cycle
    Then the feature-end cycle refuses to sign the feature as done
    And the refusal names the execution-reach gate
    And no feature-end verdict is recorded
