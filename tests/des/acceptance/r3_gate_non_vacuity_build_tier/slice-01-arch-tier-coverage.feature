@feature-r3-gate-non-vacuity-build-tier
Feature: The per-slice exit gate covers the architecture tier, not just the feature scope

  As the U2 SubagentStop / G_COMMIT exit gate that certifies a carpaccio slice
    GREEN before it earns a SliceCommitVerified record
  I want my feature-scoped verdict to cover the SAME architecture-boundary
    invariants the whole-tree pre-push gate enforces (the tests/build/** tier)
  So that a slice that breaks an architecture-boundary invariant can never earn
    a verified record by passing a narrower-than-contract feature-scoped run --
    the gate's verdict stops being narrower than the contract it claims to
    enforce

  # slice-01 (walking skeleton) -- THE keystone non-vacuity hole closed
  # end-to-end for the smallest case.
  #
  # Verified-from-source at HEAD 479adf700 (corrected per feature-delta §6
  # ADDENDUM -- Form A): `_mode_feature_scoped` (run_contract_gate.py:852)
  # narrows collection to the feature's `.feature` PARENT dirs (`scope_dirs`,
  # :894) and COLLECTS them via `_collect_node_ids` (a HARD `--collect-only`
  # worker, :896 -> _collect_scope_worker.py:135). It does NOT RUN the tests.
  # `tests/build/` is structurally EXCLUDED. The whole-tree pre-push gate covers
  # it ONLY because the pre-push path RUNS the suite (conftest auto-marks
  # `tests/build/` -> unit). The per-slice feature-scoped run neither runs NOR
  # collects it. Narrower-than-contract green by construction.
  #
  # THE KEYSTONE THREAT IS A RUN-TIME ARCH INVARIANT. The real F-D-09 arch gate
  # `tests/build/test_des_no_dev_root_imports.py` is a self-contained AST
  # scanner: it reads each `src/des/**/*.py` as TEXT and `ast.parse`s it (:42),
  # it NEVER imports the scanned subject. A forbidden `from scripts...` import
  # surfaces ONLY when its `assert not all_violations` (:78) EXECUTES at
  # run-time. A collect-only gate is structurally blind to it. The fix (DDD-1
  # §6.2) collect-AND-RUNs the arch-invariant set via a `--run` worker branch;
  # a RED arch run -> `FeatureScopeMalformed` reason `arch-invariant-failed`
  # exit 2 (REFUSED). Today the arch tier is neither run nor collected, so the
  # verdict is `FeatureScopeCleared` exit 0 -- the RED witness this AT pins.
  #
  # The synthetic broken-arch tier is therefore Form A: a real `src/des/badmod`
  # violation that NO in-scope test imports (so collection PASSES), plus a
  # `tests/build/`-class AST scanner test that reads it as text and FAILS only
  # when it RUNS. (The earlier collection-crash seed proved an ADJACENT
  # sub-class -- a forbidden import some test directly imports -- NOT the
  # scans-not-imports run-time threat; superseded by Form A.)
  #
  # OQ-1 ratified for slice-01: arch-set membership = the `tests/build/**` GLOB
  # for the walking skeleton; a `@pytest.mark.arch` marker convention is deferred
  # to slice-02.
  #
  # Driving port (Mandate-13): the real `des run-contract-gate --feature-id <f>
  # --entering-slice <s>` CLI, driven as a Layer-3 SUBPROCESS black-box (via
  # python_for(None), genericità). The AT never imports `_mode_feature_scoped` /
  # `_collect_node_ids` / `_arch_invariant_paths` / `_run_arch_invariant_set`;
  # it observes ONLY the CLI's exit code + stdout JSON verdict event.
  #
  # Two distinct planes: (a) THIS `.feature` is tagged
  # `@feature-r3-gate-non-vacuity-build-tier` so the R3 feature's OWN future exit
  # gate resolves it; (b) the SUT is pointed at a SYNTHETIC tmp repo whose feature
  # id is `arch-probe-fixture` (a `.feature` tagged `@feature-arch-probe-fixture`),
  # so the SUT never resolves the AT's own file.
  #
  # Layer 3+ (real subprocess collect-AND-run over a synthetic repo) ->
  # example-only (Mandate 9, 11); the arch-coverage property is
  # perturbation-bound (the arch tier broken vs clean), not a vacuous constant.

  @slice-01 @coupled @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice that fails a run-time architecture invariant is refused though its feature scope is clean
    Given a slice whose feature scope collects cleanly
     And the architecture tier fails a run-time forbidden dev-root import invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate refuses the slice
     And the gate reports the architecture invariant failed

  @slice-01 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice whose architecture invariants all hold still clears its feature scope
    Given a slice whose feature scope collects cleanly
     And the architecture tier holds every invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the gate certifies a non-vacuous architecture-tier scope

  @slice-01 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario Outline: The gate refuses any shape of run-time architecture-invariant failure
    Given a slice whose feature scope collects cleanly
     And the architecture tier fails a run-time <violation> invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate refuses the slice

    Examples:
      | violation                 |
      | forbidden dev-root import |
      | inline interpreter spawn  |
      | seeded runtime assertion  |
