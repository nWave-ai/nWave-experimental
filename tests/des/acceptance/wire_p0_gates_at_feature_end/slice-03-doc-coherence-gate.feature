@feature-wire-p0-gates-at-feature-end @slice-03
Feature: The feature-end cycle warns loud on docs overstating absent code but does not block signing

  As the nWave maintainer running the feature-end cycle
  I want a feature whose shipped docs claim a script, file, or module that
    does not exist in the tree to be surfaced loudly as a warning
  So that a single stale-but-honest doc claim never hard-blocks certification,
    while the disagreement is never swallowed or read as "doc-coherence passed"

  # wire-p0-gates-at-feature-end slice-03 (reuses slice-01's wiring pattern
  # against a third gate). Backlog: evolution-plan P0.5 row. Ground truth:
  # `des verify-doc-coherence` (src/des/cli/verify_doc_coherence.py) is DONE,
  # unit-tested 3/3, catalogued.
  #
  # SUPERSEDED (2026-07-16, ratified by
  #   docs/product/expectations/fix-doc-coherence-gate-warns-not-blocks/
  #   doc-coherence-findings-warn-loud-never-block-feature-end.md): this
  #   scenario originally pinned a HARD-REFUSAL on doc-coherence violations.
  #   That behavior is intentionally superseded -- a doc-coherence violation
  #   now WARNS LOUD (a distinct `DocCoherenceWarned` ledger record naming
  #   the violation, folded into `leg_census.warned`) and the cycle PROCEEDS
  #   to a signed done -- never a doc-coherence-caused refusal. The
  #   superseded hard-block behavior remains in git history. The unit-level
  #   oracle for this contract now lives at tests/des/unit/application/
  #   test_feature_end_cycle_doc_coherence_gate.py::
  #   test_doc_overstating_absent_code_warns_but_does_not_refuse_feature_end
  #   and the regression AT tests/bugs/des/
  #   test_doc_coherence_gate_warns_not_blocks_feature_end.py -- same fixture
  #   shape (a README claiming an absent npm script AND an absent file path),
  #   reused here as the oracle rather than re-derived.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition): the real use-case entry
  #   point `run_feature_end_cycle(...)` -- the SAME function both `des
  #   feature-end run` and the SubagentStop hook shim invoke (DDD-7). Sibling
  #   legs (walking-skeleton, env-e2e, coverage-map) are stubbed to
  #   PASS/NOT_APPLICABLE, and the full-suite leg is forced to a genuine
  #   RAN outcome (so `leg_census.ran >= 1` and the cycle does not ALSO trip
  #   the unrelated zero-observed-checks charter) so this scenario isolates
  #   the doc-coherence leg's WARN contract; the doc-coherence gate itself is
  #   NEVER stubbed -- it runs as a real `des verify-doc-coherence` subprocess
  #   against a real README planted with a genuine false claim (an npm
  #   script absent from package.json and a file path absent from the tree).

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Docs overstating absent code warn loud but do not block the feature-end signing
    Given a feature whose shipped docs claim a script and a file that do not exist
    When the nWave maintainer runs the feature-end cycle
    Then the feature-end cycle signs the feature as done
    And the doc-coherence findings are recorded as a warning naming the violation
    And the warning is never recorded as doc-coherence verified clean
