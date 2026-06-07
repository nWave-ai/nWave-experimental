@feature-fix-robustness-pbt-density-gate @slice-04 @walking-skeleton @driving_port @real-io
Feature: The robustness density gate consults a fixture mutmut report to refuse a property-based test that kills no mutants while distinguishing an untrustworthy mutmut run from a falsifiable one
  As an nWave framework developer authoring a feature's acceptance tests
  I want the robustness density gate CLI to read a fixture mutmut report
    keyed by the declared unbounded-input-domain's sut symbol and to
    distinguish three Layer-2 states -- the property-based test kills at
    least one mutant (pass), the property-based test kills zero mutants
    while the positive control was killed (fail closed for shallow
    non-trivial coverage), and the mutmut report is untrustworthy
    (unavailable, neither pass nor fail) -- so that a shallow-but-non-trivial
    property-based test cannot survive Layer 1 and Layer 3 AST checks while
    silently leaving the SUT undefended, and so that a mutmut absent or
    misconfigured environment cannot brick the gate or vacuously pass it
  So that the v1 blocking set is complete (Layer 1 plus Layer 2 plus Layer
    3 ship together), kill-rate zero terminates in a refusal, and the
    feature is held out of ready when mutmut cannot answer truthfully

  # carpaccio slice-04 (DESIGN slice plan, ## Wave: DISCUSS / [REF] Slice Plan).
  # Builds on slice-01 walking-skeleton parser, slice-02 empty-declaration
  # guard, and slice-03 genuineness layers 1 + 3. Adds Genuineness Layer 2
  # (mutmut-delta proxy, three-state per R5) as the v1 blocking set's final
  # piece. Slice-05 (wiring) ships last so it demos against the COMPLETE
  # blocking gate, not a partial one.
  #
  # CONTRACT SOURCE: this slice is authored against the feature-delta
  # `docs/feature/fix-robustness-pbt-density-gate/feature-delta.md` section 4
  # (Genuineness Layer 2 specification including positive control and the
  # three-state R5) and section 6 (slice-04 row). Three ATs:
  #   AT1: a property-based test whose declared sut symbol has kill-rate 0
  #        in the fixture mutmut report while the positive control was
  #        killed -> RobustnessPBTNotFalsifiable exit 1 (the gate's "real
  #        teeth" defense against shallow-but-non-trivial PBTs).
  #   AT2: a property-based test whose declared sut symbol has kill-rate
  #        greater than zero in the fixture mutmut report (positive control
  #        killed) -> exit 0 (Layer 2 satisfied; the PBT genuinely
  #        discriminates a broken SUT from a correct one).
  #   AT3: an untrustworthy fixture mutmut report (malformed JSON OR empty
  #        report OR partial report missing the sut entry OR positive
  #        control absent OR positive control NOT killed) -> exit 3
  #        RobustnessLayer2Unavailable (V5 / R5 three-state -- neither pass
  #        nor fail, holds the feature out of ready). R6 dogfood: the
  #        gate's own mutmut-report parser is the SUT here.
  #
  # M2 FIXTURE-ONLY MANDATE (architect, gated not disciplinary per C1):
  # slice-04 ATs MUST exercise the kill-rate parser against COMMITTED
  # FIXTURE mutmut reports staged under
  # `tests/des/acceptance/fix_robustness_pbt_density_gate/fixtures/mutmut/`.
  # They MUST NEVER import `mutmut` or subprocess-invoke the `mutmut`
  # binary -- else slice-04 inherits the very environment coupling (M2) the
  # gate exists to bound. The mandate is enforced by an in-module
  # mechanical self-check test (`test_c1_no_live_mutmut_invocation_in_slice_04`)
  # that statically asserts the slice-04 binding module contains no
  # `mutmut` token in any import or subprocess argv -- per the
  # gate-or-residue policy (feedback_gate_or_residue_policy STANDING),
  # converting the M2 prose mandate into an executing check.
  #
  # Layer 5 (WS @wiring_e2e): real stack, subprocess, real YAML parsing,
  # real JSON report parsing over committed fixture artifacts. Example-only
  # per Mandate 9/11 -- the AT-set itself is layer 5, NOT PBT-generated.
  # The PBT input-space declared by the architect (mutant-survival space +
  # malformed-mutmut-report space) is exercised through the THREE NAMED
  # example shapes below, each instantiating one cell of the
  # Slice04Layer2State enum: kill-rate-positive, kill-rate-zero with
  # positive-control-killed, and the unavailable-report cell. Traditional
  # assertions permitted at layer 4+ (Mandate 8). No fixture-folding: the
  # subject is the production CLI, the composition stages real on-disk
  # fixture mutmut reports, the delivery form is the invocation result.
  #
  # MUTMUT CACHE JSON SCHEMA: the fixture reports follow a minimal
  # gate-specific shape documented inline in `composition.py` (constant
  # `_MUTMUT_FIXTURE_SCHEMA_DOC`). The shape is a JSON object with a
  # top-level `mutmut_ran: bool`, a `positive_control: {seeded: bool,
  # killed: bool}` block (the probe per R5), and a `mutants: {<sut_symbol>:
  # {killed: int, survived: int}}` map keyed by the manifest `sut:` field.
  # This shape is gate-internal -- the production CLI reads only what the
  # gate's three-state R5 logic requires; the gate is NOT a general mutmut
  # report consumer. Future v2 (paired-falsifier fixture, backlog) may
  # converge on the upstream `.mutmut-cache` schema; v1 declares its own
  # minimal contract so slice-04 can ship without coupling to mutmut's
  # internal cache format (which differs across mutmut 2.x point releases).
  #
  # Driving port: `check_robustness_density` CLI invoked as a `python -m`
  # subprocess (slice-01 / slice-02 / slice-03 precedent, project
  # Infrastructure Policy spine-gate CLI row). Slice-04 extends the
  # invocation surface with a new `--mutmut-report <path>` flag pointing at
  # the staged fixture JSON.
  #
  # DEPENDENCY: slice-01 + slice-02 + slice-03 shipped (walking-skeleton
  # parser + empty-declaration guard + genuineness layers 1+3). Slice-04
  # requires the production CLI to grow a layer-2 branch that reads the
  # `--mutmut-report` path, looks up the declared sut symbol, applies the
  # three-state R5 (positive control gating, kill-rate-zero refusal,
  # unavailable detection), and emits one of three diagnostic tokens.

  @slice-04 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A property-based test whose declared sut symbol kills no mutants while the positive control was killed is refused as not falsifiable
    Given a declared unbounded input domain "tree-vs-commit-file-divergence" covered by a property-based test whose declared sut symbol has kill-rate zero in the fixture mutmut report while the positive control was killed
    When the developer runs the robustness density gate against the declared scope including the fixture mutmut report
    Then the gate exit status indicates a property-based test that is not falsifiable

  @slice-04 @walking-skeleton @wiring_e2e @driving_port @real-io @contract-shape:pure-function
  Scenario: A property-based test whose declared sut symbol kills at least one mutant satisfies the falsifiability layer
    Given a declared unbounded input domain "tree-vs-commit-file-divergence" covered by a property-based test whose declared sut symbol has positive kill-rate in the fixture mutmut report while the positive control was killed
    When the developer runs the robustness density gate against the declared scope including the fixture mutmut report
    Then the gate exit status indicates the falsifiability layer was satisfied

  @slice-04 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: An untrustworthy fixture mutmut report holds the feature out of ready without bricking the gate
    Given a declared unbounded input domain "tree-vs-commit-file-divergence" covered by a property-based test whose fixture mutmut report is untrustworthy
    When the developer runs the robustness density gate against the declared scope including the fixture mutmut report
    Then the gate exit status indicates the falsifiability layer is unavailable and the feature is held out of ready
