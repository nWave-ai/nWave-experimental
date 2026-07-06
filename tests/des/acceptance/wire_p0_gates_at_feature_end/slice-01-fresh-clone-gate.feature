@feature-wire-p0-gates-at-feature-end @slice-01
Feature: The feature-end cycle refuses to sign a feature whose committed tree fails a fresh-clone build

  As the nWave maintainer running the feature-end cycle
  I want a feature whose committed tree only builds in my warm working tree
    to be refused at feature-end
  So that a fresh-clone-broken build never ships as a signed "done" feature

  # wire-p0-gates-at-feature-end slice-01 (walking skeleton -- establishes the
  # new-leg wiring pattern slice-02/03 replicate). Backlog: evolution-plan
  # P0.1 row ("Wiring into the feature-end stack = P2.2"). Ground truth:
  # `des verify-fresh-clone` (src/des/cli/verify_fresh_clone.py) is DONE,
  # unit-tested 3/3, catalogued -- but `run_feature_end_cycle`
  # (src/des/application/feature_end_cycle_service.py) never invokes it. This
  # scenario is the acceptance-level witness of the already-authored unit
  # oracle at tests/des/unit/application/test_feature_end_cycle_fresh_clone_
  # gate.py::test_fresh_clone_broken_build_refuses_feature_end -- same fixture
  # shape (an untracked helper.py the committed main.py imports), reused here
  # as the oracle rather than re-derived.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition): the real use-case entry
  #   point `run_feature_end_cycle(repo_root=..., feature_id=..., feature_dir=
  #   ..., reviewer_agent_id=..., verdict=...)` -- the SAME function both
  #   `des feature-end run` and the SubagentStop hook shim invoke (DDD-7).
  #   Sibling legs (walking-skeleton, env-e2e, coverage-map, full-suite) are
  #   stubbed to PASS/NOT_APPLICABLE so this scenario isolates the NEW
  #   fresh-clone leg; the fresh-clone gate itself is NEVER stubbed -- it runs
  #   as a real `des verify-fresh-clone` subprocess against a real git
  #   repository planted with a genuine untracked-dependency defect.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD `run_feature_end_cycle` does
  #   not yet call `verify-fresh-clone` at all, so this scenario reaches a
  #   signed success regardless of the planted defect -- a genuine semantic
  #   AssertionError (expected refusal, got success), not a collection error.
  #   GREEN once DELIVER adds the fresh-clone leg mirroring the existing four
  #   legs' dispatch -> verdict-parse -> CycleRefusal-or-heartbeat shape (L-2).

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A fresh-clone-broken build blocks the feature-end signing
    Given a feature whose committed tree fails a fresh-clone build
    When the nWave maintainer runs the feature-end cycle
    Then the feature-end cycle refuses to sign the feature as done
    And the refusal names the fresh-clone gate
    And no feature-end verdict is recorded
