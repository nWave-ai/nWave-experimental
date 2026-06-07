@feature-simplify-atdd-pure-carpaccio-spine
Feature: The contract gate is scoped to one feature and refuses a vacuous pass

  The contract gate used to re-run the whole test tree, so a red anywhere -- a
  sibling slice's by-design scaffold, an unrelated feature, a pre-existing
  master red -- failed a slice's commit (walls W2, W4, W6). This slice scopes
  the gate to one feature's own tests.

  Scoping is dangerous if done naively: narrowing the collection until it is
  empty would make the gate pass vacuously. So the scoped gate carries a
  non-vacuity floor -- it must genuinely COLLECT at least one runnable test
  node-id, and the collected set must intersect the entering slice's tag. A
  zero-collected or empty-intersection run is malformed, never a pass.

  This is the carpaccio base case (no predecessor): it gives the orchestrator a
  contract gate that judges only one feature, and refuses to be fooled by an
  empty scope. It is the walking skeleton -- the thinnest end-to-end vertical
  proving feature-scoped gating wires together.

  # Driving port: the run_contract_gate CLI with --feature-id (python -m).
  # Layer 3 (subprocess / FS acceptance) -- example-only sad paths (Mandate 11).
  # The non-vacuity floor (M-1/M-8) is realised as an enumerated Scenario
  # Outline at layer 3, not a Hypothesis @given (Mandate 9).

  Background:
    Given a feature project with a multi-slice plan

  # @red_scaffold_distill: this block is author-ahead RED until DELIVER routes
  # _mode_feature_scoped through real node-id collection. The conftest holds it
  # xfail so the DISTILL commit lands green; DELIVER drops the tag at re-GREEN.
  @slice-01 @walking_skeleton @wiring_e2e @driving_port @red_scaffold_distill @contract-shape:unbounded-preservation
  Scenario Outline: The contract gate passes when the feature genuinely collects tagged tests
    Given the feature has <files> .feature file(s) carrying a runnable scenario tagged for the entering slice
    When the orchestrator runs the feature-scoped contract gate
    Then the feature-scoped contract gate passes
    And the gate reports it collected at least one node-id for the entering slice

    Examples:
      | files |
      | one   |
      | two   |

  # @red_scaffold_distill: held xfail(non-strict) for the DISTILL commit. These
  # malformed rows pass in isolation, but are intermittently flaky under the
  # full-suite parallel pre-commit run while the happy-path block above is RED.
  # DELIVER drops this tag (with the happy-path block's) at re-A_GREEN.
  @slice-01 @error @driving_port @red_scaffold_distill @contract-shape:bounded-change
  Scenario Outline: The contract gate refuses a vacuous scope as malformed
    Given a feature-scoped invocation where <vacuity>
    When the orchestrator runs the feature-scoped contract gate
    Then the feature-scoped contract gate is refused as malformed

    Examples:
      | vacuity                                                       |
      | no test collects under the feature id                         |
      | the collected tests carry no entering-slice tag                |
      | the collected tests carry a malformed slice tag                |
      | the entering slice is not declared                             |
      | a tagged feature file collects zero runnable node-ids          |
      | a feature test module has a syntax error                       |
