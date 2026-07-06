@feature-wire-p0-gates-at-feature-end @slice-03
Feature: The feature-end cycle refuses to sign a feature whose docs overstate absent code

  As the nWave maintainer running the feature-end cycle
  I want a feature whose shipped docs claim a script, file, or module that
    does not exist in the tree to be refused at feature-end
  So that docs overstating the code never ship alongside a signed "done" feature

  # wire-p0-gates-at-feature-end slice-03 (reuses slice-01's wiring pattern
  # against a third gate). Backlog: evolution-plan P0.5 row. Ground truth:
  # `des verify-doc-coherence` (src/des/cli/verify_doc_coherence.py) is DONE,
  # unit-tested 3/3, catalogued -- but `run_feature_end_cycle` never invokes
  # it. This scenario is the acceptance-level witness of the already-authored
  # unit oracle at tests/des/unit/application/
  # test_feature_end_cycle_doc_coherence_gate.py::
  # test_doc_overstating_absent_code_refuses_feature_end -- same fixture
  # shape (a README claiming an absent npm script AND an absent file path),
  # reused here as the oracle rather than re-derived.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition): the real use-case entry
  #   point `run_feature_end_cycle(...)` -- the SAME function both `des
  #   feature-end run` and the SubagentStop hook shim invoke (DDD-7). Sibling
  #   legs (walking-skeleton, env-e2e, coverage-map, full-suite) are stubbed
  #   to PASS/NOT_APPLICABLE so this scenario isolates the NEW doc-coherence
  #   leg; the doc-coherence gate itself is NEVER stubbed -- it runs as a
  #   real `des verify-doc-coherence` subprocess against a real README
  #   planted with a genuine false claim (an npm script absent from
  #   package.json and a file path absent from the tree).
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD `run_feature_end_cycle` does
  #   not yet call `verify-doc-coherence` at all, so this scenario reaches a
  #   signed success regardless of the planted defect -- a genuine semantic
  #   AssertionError (expected refusal, got success), not a collection error.
  #   GREEN once DELIVER adds the doc-coherence leg mirroring the existing
  #   legs' dispatch -> verdict-parse -> CycleRefusal-or-heartbeat shape (L-2).

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Docs overstating absent code block the feature-end signing
    Given a feature whose shipped docs claim a script and a file that do not exist
    When the nWave maintainer runs the feature-end cycle
    Then the feature-end cycle refuses to sign the feature as done
    And the refusal names the doc-coherence gate
    And no feature-end verdict is recorded
