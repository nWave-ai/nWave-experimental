@feature-r3-gate-non-vacuity-build-tier
Feature: A vacuous architecture tier is refused at feature-end, never charged to a passing slice

  As the U2 SubagentStop / G_COMMIT exit gate that certifies a carpaccio slice
    GREEN before it earns a SliceCommitVerified record
  I want the whole-tree architecture run to refuse LOUD when a target's
    architecture tier EXISTS but collects no invariant -- a malformed arch tier
    -- while still CLEARING a target that legitimately carries no architecture
    tier at all, and while never charging either verdict to a concurrent lane's
    slice
  So that nobody can earn a verified record by "covering an empty arch set" when
    an arch tier is present-but-broken, an external target (TS, Go, minimal
    Python) with no nWave architecture tier is never over-refused, and a slice
    whose own scope is green is never blocked by the state of a tier it does not
    own

  # RE-ALLOCATION (fix-e2-whole-tree-scope-blocks-unrelated-slices, 2026-07-30).
  # slice-02's protections are UNCHANGED and UNWEAKENED; they move to the
  # surface that now owns the whole-tree architecture tier. The original
  # allocation charged the present-but-vacuous refusal to the PER-SLICE gate,
  # which meant a malformed tier owned by ANOTHER concurrent lane refused every
  # lane's slice tree-wide. Restores nw-throughput move 3 (C1).
  #
  #   * Hole A -- arch tier ABSENT: `_arch_invariant_paths(repo)` returns `[]`
  #     when the repo has NO `tests/build/` dir. CORRECT BEHAVIOUR (no arch tier
  #     => no arch invariant to enforce). The ABSENT *clear control* is a
  #     genericità over-refusal guard and is UNCHANGED by the re-allocation: the
  #     per-slice gate must still clear it.
  #   * Hole B -- arch tier present-but-vacuous: a `tests/build/` that collects
  #     ZERO runnable node-ids under the contract marker filter is genuinely
  #     malformed -- a tier the gate would fingerprint vacuously. It must still
  #     be REFUSED LOUD (`arch-scope-zero-collected`), but at the WHOLE-TREE run
  #     (feature-end), not on every concurrent lane's entering slice.
  #
  # Target contract after the re-allocation:
  #   * per-slice, ANY arch-tier state -> FeatureScopeCleared exit 0 + a LOUD
  #     BuildTierWholeTreeDeferred naming feature-end (the slice is judged on its
  #     OWN scope; the tier's state is not its business);
  #   * whole-tree, arch tier ABSENT        -> CLEAR (BuildTierNotApplicable);
  #   * whole-tree, arch tier collects zero -> REFUSE (BuildTierRefused reason
  #                                            `arch-scope-zero-collected`);
  #   * whole-tree, arch tier non-vacuous + green -> CLEAR (BuildTierVerified,
  #                                            non-zero executed count).
  #
  # RED witness at HEAD: the per-slice legs are RED (production still sweeps the
  # whole tier per-slice, so a vacuous tier refuses the slice with
  # `arch-scope-zero-collected` instead of deferring). The whole-tree legs are
  # GREEN today and are pinned as invariant guards the fix must not perturb --
  # a protection that survives the move only in prose is a protection that was
  # dropped. The failures are verdict AssertionErrors (cleared-vs-refused), not
  # collection crashes / import errors. Not xfail-marked.
  #
  # Driving ports (Mandate-13), inherited from slice-01 via R3GateComposition2:
  # (a) the per-slice leg drives the real `des run-contract-gate --feature-id <f>
  # --entering-slice <s>` CLI as a Layer-3 SUBPROCESS black-box; (b) the
  # whole-tree leg drives the real `build_tier_exit_verdict` entry (Layer-3
  # composition) -- no CLI flag selects the whole-tree build-tier run.
  #
  # Two distinct planes (inherited): (a) THIS `.feature` is tagged
  # `@feature-r3-gate-non-vacuity-build-tier`; (b) the SUT targets a SYNTHETIC
  # tmp repo with its OWN feature id (`arch-probe-fixture`) whose feature scope
  # is ALWAYS clean.
  #
  # Layer 3+ (real subprocess / real worker spawn over a synthetic repo) ->
  # example-only (Mandate 9, 11); the arch-scope-vacuity property is
  # perturbation-bound (present-but-vacuous vs present-and-green vs absent),
  # never a vacuous constant.

  @slice-02 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice whose target carries no architecture tier still clears its feature scope
    Given a slice whose feature scope collects cleanly
     And the repository carries no architecture tier
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the gate does not over-refuse the absent architecture tier

  @slice-02 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The whole-tree architecture run does not over-refuse an absent architecture tier
    Given a slice whose feature scope collects cleanly
     And the repository carries no architecture tier
    When the whole-tree architecture run certifies the repository
    Then the whole-tree architecture run clears the repository
     And the whole-tree run reports the architecture tier is not applicable

  @slice-02 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A whole-tree architecture tier that exists but collects nothing is refused, not silently cleared
    Given a slice whose feature scope collects cleanly
     And the architecture tier collects no invariant
    When the whole-tree architecture run certifies the repository
    Then the whole-tree architecture run refuses the repository
     And the whole-tree run reports the architecture scope collected nothing
     And the system is unchanged

  @slice-02 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice is not charged for a vacuous architecture tier it does not own
    Given a slice whose feature scope collects cleanly
     And the architecture tier collects no invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the gate defers the whole-tree architecture tier to feature-end

  @slice-02 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice whose architecture tier is non-vacuous and holds still clears its feature scope
    Given a slice whose feature scope collects cleanly
     And the architecture tier carries a holding invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the gate defers the whole-tree architecture tier to feature-end

  @slice-02 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The whole-tree architecture run certifies a non-vacuous tier that holds
    Given a slice whose feature scope collects cleanly
     And the architecture tier carries a holding invariant
    When the whole-tree architecture run certifies the repository
    Then the whole-tree architecture run clears the repository
     And the whole-tree architecture run certifies a non-vacuous architecture-tier scope
