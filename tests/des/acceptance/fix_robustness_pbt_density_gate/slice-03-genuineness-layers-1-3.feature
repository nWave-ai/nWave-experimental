@feature-fix-robustness-pbt-density-gate @slice-03 @walking-skeleton
Feature: The robustness density gate refuses property-based tests whose strategy is trivial or whose only assertion is a tautology, and survives adversarial AST shapes
  As an nWave framework developer authoring a feature's acceptance tests
  I want the robustness density gate CLI to reject a shallow @given (trivial
    strategy or tautology-only assertion, including via a single-hop
    module-local helper) and to survive adversarial test-file AST shapes
    such as an indirect parametrize source
  So that the density count cannot be gamed by a presence-only @given that
    tests nothing, and the gate's own AST parser cannot be crashed by an
    adversarial test file the architect already named as the gate's highest
    risk surface

  # carpaccio slice-03 (DESIGN slice plan, ## Wave: DISCUSS / [REF] Slice Plan).
  # Builds on slice-01's walking-skeleton parser and slice-02's empty-
  # declaration guard. Adds genuineness layers 1+3 (anti-shallow-PBT) and
  # the adversarial-AST robustness probe.
  #
  # CONTRACT SOURCE: this slice is authored against the feature-delta
  # `docs/feature/fix-robustness-pbt-density-gate/feature-delta.md` section 4
  # (genuineness defense layers 1+3) and section 6 (slice-03 row). Three ATs:
  #   AT1: a @given whose strategy is `st.just(...)` reached through a
  #        single-hop module-local helper (per B5 -- the cheap evasion the
  #        design closes for blocking layers) -> `RobustnessPBTShallow`
  #        exit 1.
  #   AT2: a @given whose only assertion is a tautology (`result == result`)
  #        reached through a single-hop module-local helper (per B5) ->
  #        `RobustnessPBTShallow` exit 1.
  #   AT3: an adversarial test file using `@pytest.mark.parametrize("x",
  #        _cases())` -- the canonical V4 indirect parametrize source the
  #        gate cannot classify (advisory-only on this path per R4); the
  #        gate must record the advisory verdict (RobustnessAdvisoryUnclassified)
  #        WITHOUT CRASHING. R6 dogfood: the gate's own parser is the SUT.
  #
  # Layer 5 (WS @wiring_e2e): real stack, subprocess, real YAML parsing,
  # real AST/grep over a real staged test file. Example-only per Mandate
  # 9/11 -- the AT-set itself is layer 5, NOT PBT-generated. The PBT
  # input-space declared by the architect (strategy-expression AST space +
  # assertion-body AST space + adversarial test-file AST space) is exercised
  # through the THREE NAMED example shapes below, each instantiating one
  # cell of the Slice03GenuinenessKind enum: trivial-strategy-via-helper,
  # tautology-via-helper, adversarial-indirect-parametrize. The architect's
  # PBT framing on slice-03 row is honored via the slice-04 + slice-05
  # layered design (slice-04 mutmut-delta proxy generates the mutation space
  # at layer 1-2), NOT by adding @given to layer 5. Traditional assertions
  # permitted at layer 4+ (Mandate 8). No fixture-folding: the subject is
  # the production CLI, the composition stages real on-disk artifacts, the
  # delivery form is the invocation result.
  #
  # Driving port: `check_robustness_density` CLI invoked as a `python -m`
  # subprocess (slice-01 / slice-02 precedent, project Infrastructure Policy
  # spine-gate CLI row).
  #
  # DEPENDENCY: slice-01 + slice-02 shipped (walking-skeleton parser +
  # empty-declaration guard). Slice-03 requires the genuineness layer 1+3
  # branch in the production CLI: an AST walker over the staged AT-scope
  # @given strategies + test bodies, with single-hop module-local
  # indirection resolution per B5. Multi-hop / cross-module is NAMED
  # RESIDUE (owner: slice-03 crafter, recorded in the slice plan).

  @slice-03 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A property-based test whose strategy is trivial reached through a single-hop module-local helper is refused as shallow
    Given a declared unbounded input domain "tree-vs-commit-file-divergence" covered by a property-based test whose strategy is reached through a single-hop module-local helper returning a constant
    When the developer runs the robustness density gate against the declared scope
    Then the gate exit status indicates a shallow property-based test

  @slice-03 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A property-based test whose only assertion is a tautology reached through a single-hop module-local helper is refused as shallow
    Given a declared unbounded input domain "tree-vs-commit-file-divergence" covered by a property-based test whose only assertion is reached through a single-hop module-local helper returning a tautology
    When the developer runs the robustness density gate against the declared scope
    Then the gate exit status indicates a shallow property-based test

  @slice-03 @walking-skeleton @wiring_e2e @driving_port @real-io @property @contract-shape:pure-function
  Scenario: An adversarial test file whose parametrize value list is reached through a module-local helper is survived by the gate parser as an advisory verdict
    Given a declared unbounded input domain "tree-vs-commit-file-divergence" alongside an adversarial test file whose parametrize value list is reached through a module-local helper the gate parser cannot classify
    When the developer runs the robustness density gate against the declared scope
    Then the gate completes the adversarial parser probe without crashing and records an advisory verdict for the unclassifiable indirect parametrize source
