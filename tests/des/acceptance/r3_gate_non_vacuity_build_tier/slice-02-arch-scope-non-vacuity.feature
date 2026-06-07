@feature-r3-gate-non-vacuity-build-tier
Feature: The per-slice exit gate refuses an architecture tier that collects nothing

  As the U2 SubagentStop / G_COMMIT exit gate that certifies a carpaccio slice
    GREEN before it earns a SliceCommitVerified record
  I want to refuse LOUD when a target's architecture tier EXISTS but collects no
    invariant -- a malformed arch tier -- while still CLEARING a target that
    legitimately carries no architecture tier at all
  So that a slice can never earn a verified record by "covering an empty arch
    set" when an arch tier is present-but-broken, yet an external target (TS, Go,
    minimal Python) with no nWave architecture tier is never over-refused

  # slice-02 -- PO REVISED (Ale): the `--feature-id` gate runs on the TARGET repo
  # during DELIVER. An external target legitimately has NO nWave `tests/build/`
  # arch tier -- refusing it would violate the STANDING genericità mandate and
  # break the prior `atdd_pure_carpaccio_spine` ATs (synthetic repos with no arch
  # tier). So the two holes are NOT symmetric:
  #
  # Hole A -- arch tier ABSENT (run_contract_gate.py:1041 `if arch_paths:`):
  # `_arch_invariant_paths` returns `[]` when the repo has NO `tests/build/` dir.
  # This is now CORRECT BEHAVIOUR -- a repo that carries no arch tier carries no
  # arch invariant to enforce, so the gate CLEARS on the feature scope alone
  # (exit 0 `FeatureScopeCleared`). slice-02 adds an ABSENT *clear control* as a
  # genericità regression guard: the gate must NOT over-refuse a legitimate
  # no-arch-tier target. (Current production over-refuses ABSENT with
  # `arch-scope-empty`; the upcoming production change REMOVES that branch -- this
  # control is the RED witness for that removal.)
  #
  # Hole B -- arch tier present-but-vacuous (:1053 `if arch.collected > 0 and not
  # arch.passed`): when `tests/build/` EXISTS but holds only an UNMARKED test,
  # the `--run` worker's `-m "unit or integration or acceptance"` filter
  # (_collect_scope_worker.py:54) collects ZERO arch node-ids; the branch falls
  # through and the gate SILENTLY clears. This is the GENUINELY malformed case:
  # an arch tier is present (the directory exists) but the gate would fingerprint
  # a vacuous arch run.
  #
  # Target contract (PO-revised): the present-but-vacuous arch tier degrades-LOUD
  # via the existing M-1 non-vacuity floor (`_feature_scope_malformed`) --
  #   * arch tier ABSENT        -> FeatureScopeCleared exit 0 (CLEAR, genericità);
  #   * arch tier collects zero  -> FeatureScopeMalformed reason
  #                               `arch-scope-zero-collected` exit 2 (REFUSED).
  # This mirrors the feature-scope M-1 floor (`zero-collected` /
  # `empty-intersection`, :1010-1023) but ONLY for a present-but-vacuous tier.
  #
  # RED witness at HEAD:
  #   * ABSENT control -> RED: current production REFUSES ABSENT with
  #     `arch-scope-empty` exit 2; this AT now expects `FeatureScopeCleared`
  #     exit 0. The RED is the genericità over-refusal that production must drop.
  #   * ZERO_COLLECTED -> GREEN: current production already refuses a
  #     present-but-vacuous tier with `arch-scope-zero-collected` exit 2.
  #   * PRESENT control -> GREEN: current production clears a non-vacuous green
  #     arch tier.
  # The failures are verdict AssertionErrors (cleared-vs-refused), not collection
  # crashes / import errors. They are NOT xfail-marked.
  #
  # Driving port (Mandate-13): the real `des run-contract-gate --feature-id <f>
  # --entering-slice <s>` CLI, driven as a Layer-3 SUBPROCESS black-box (inherited
  # verbatim from slice-01 via R3GateComposition2). The AT never imports
  # `_arch_invariant_paths` / `_run_arch_invariant_set` / `_mode_feature_scoped`;
  # it observes ONLY the CLI's exit code + stdout JSON verdict event.
  #
  # Two distinct planes (inherited): (a) THIS `.feature` is tagged
  # `@feature-r3-gate-non-vacuity-build-tier`; (b) the SUT is pointed at a
  # SYNTHETIC tmp repo whose feature id is `arch-probe-fixture` with an
  # ALWAYS-clean feature scope, so the SUT never resolves the AT's own file.
  #
  # Layer 3+ (real subprocess collect-AND-run over a synthetic repo) ->
  # example-only (Mandate 9, 11); the arch-scope-vacuity property is
  # perturbation-bound (the arch tier present-but-vacuous vs present-and-green),
  # not a vacuous constant -- the ABSENT + PRESENT controls prove the gate clears
  # both a no-arch-tier target and a non-vacuous green arch tier (no over-refusal).

  @slice-02 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice whose target carries no architecture tier still clears its feature scope
    Given a slice whose feature scope collects cleanly
     And the repository carries no architecture tier
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the gate does not over-refuse the absent architecture tier

  @slice-02 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A slice whose architecture tier exists but collects nothing is refused, not silently cleared
    Given a slice whose feature scope collects cleanly
     And the architecture tier collects no invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate refuses the slice
     And the gate reports the architecture scope collected nothing
     And the system is unchanged

  @slice-02 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice whose architecture tier is non-vacuous and holds still clears its feature scope
    Given a slice whose feature scope collects cleanly
     And the architecture tier carries a holding invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the gate certifies a non-vacuous architecture-tier scope
