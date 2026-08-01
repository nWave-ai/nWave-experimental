@feature-r3-gate-non-vacuity-build-tier
Feature: An architecture-boundary break blocks a feature's close, never a concurrent lane's slice

  As the U2 SubagentStop / G_COMMIT exit gate that certifies a carpaccio slice
    GREEN before it earns a SliceCommitVerified record
  I want a slice to be judged on ITS OWN scope, while the architecture-boundary
    invariants (the tests/build/** tier) are enforced on the whole tree at
    feature-end
  So that a slice can never earn a verified record while breaking an
    architecture boundary -- and equally can never be held hostage by a
    DIFFERENT concurrent lane's legitimate, in-flight architecture RED that it
    never touched

  # RE-ALLOCATION (fix-e2-whole-tree-scope-blocks-unrelated-slices, 2026-07-30).
  # This feature's keystone concern is UNCHANGED and UNWEAKENED: a slice must
  # not earn a verified record while breaking an architecture boundary. What
  # changed is WHERE that protection is enforced.
  #
  # The original allocation ran the WHOLE tests/build/** tier inside the
  # per-slice feature-scoped gate (`_mode_feature_scoped`). Measured twice on
  # 2026-07-30 (lanes c1-matcher and D80), that allocation refused slices whose
  # OWN scope was fully green, because an active-RED scaffold belonging to a
  # DIFFERENT feature owned by a DIFFERENT concurrent lane was failing elsewhere
  # under tests/build/**. Those REDs were the atdd_pure JIT method working
  # correctly, not defects. The blocked maintainer's refusal named files they
  # had never opened, with no action available inside their own scope.
  #
  # The standard being RESTORED (nw-throughput SKILL.md, move 3, C1): "the
  # per-slice seal digests only the ENTERING slice's regression test + light
  # always-on invariants; the whole-tree tier defers to feature-end. Running the
  # whole tree per-slice is the JIT poison that forbids pipelining."
  #
  # So the allocation is now:
  #   * PER-SLICE  -> judge the entering slice's own scope; DEFER the whole-tree
  #                   architecture tier to feature-end, announcing the deferral
  #                   LOUD (`BuildTierWholeTreeDeferred` naming feature-end) so
  #                   the narrowing can never be mistaken for a coverage drop.
  #   * FEATURE-END -> the whole-tree architecture run still REFUSES every shape
  #                   of run-time architecture-invariant failure, and still
  #                   NAMES the failing invariant.
  # Every protection slice-01 originally encoded is asserted below, at whichever
  # surface now owns it. Nothing was deleted to make a test pass.
  #
  # THE KEYSTONE THREAT IS STILL A RUN-TIME ARCH INVARIANT. The real F-D-09 arch
  # gate `tests/build/test_des_no_dev_root_imports.py` is a self-contained AST
  # scanner: it reads each `src/des/**/*.py` as TEXT and `ast.parse`s it, it
  # NEVER imports the scanned subject. A forbidden `from scripts...` import
  # surfaces ONLY when its `assert not all_violations` EXECUTES at run-time. A
  # collect-only gate is structurally blind to it -- which is why the whole-tree
  # run collect-AND-RUNs the tier, and why the synthetic broken-arch tier below
  # is Form A: it PASSES collection and FAILS at run-time.
  #
  # Driving ports (Mandate-13), TWO surfaces because the protection now lives on
  # two: (a) the per-slice leg drives the real `des run-contract-gate
  # --feature-id <f> --entering-slice <s>` CLI as a Layer-3 SUBPROCESS black-box;
  # (b) the whole-tree leg drives the real `build_tier_exit_verdict` entry
  # (Layer-3 composition, in-process) -- no CLI flag selects the whole-tree
  # build-tier run, so no subprocess black-box exists for that surface. See
  # `composition_slice_01.run_whole_tree_arch_gate` for the full statement.
  #
  # Two distinct planes: (a) THIS `.feature` is tagged
  # `@feature-r3-gate-non-vacuity-build-tier` so the R3 feature's OWN exit gate
  # resolves it; (b) the SUT is pointed at a SYNTHETIC tmp repo whose feature id
  # is `arch-probe-fixture`, so the SUT never resolves the AT's own file.
  #
  # Layer 3+ (real subprocess / real worker spawn over a synthetic repo) ->
  # example-only (Mandate 9, 11); the properties are perturbation-bound (the
  # arch tier broken vs clean), never vacuous constants.

  @slice-01 @coupled @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice whose own scope is green is not blocked by an architecture failure it never touched
    Given a slice whose feature scope collects cleanly
     And the architecture tier fails a run-time forbidden dev-root import invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the gate defers the whole-tree architecture tier to feature-end
     And the refusal never names a file outside the entering slice's own scope

  @slice-01 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The whole-tree architecture run still refuses a run-time architecture-invariant failure
    Given a slice whose feature scope collects cleanly
     And the architecture tier fails a run-time forbidden dev-root import invariant
    When the whole-tree architecture run certifies the repository
    Then the whole-tree architecture run refuses the repository
     And the whole-tree run reports the architecture invariant failed
     And the whole-tree run names the failing architecture invariant

  @slice-01 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A slice whose architecture invariants all hold still clears its feature scope
    Given a slice whose feature scope collects cleanly
     And the architecture tier holds every invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the gate defers the whole-tree architecture tier to feature-end

  @slice-01 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The whole-tree architecture run certifies a non-vacuous tier whose invariants hold
    Given a slice whose feature scope collects cleanly
     And the architecture tier holds every invariant
    When the whole-tree architecture run certifies the repository
    Then the whole-tree architecture run clears the repository
     And the whole-tree architecture run certifies a non-vacuous architecture-tier scope

  @slice-01 @coupled @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario Outline: The whole-tree architecture run refuses any shape of run-time architecture-invariant failure
    Given a slice whose feature scope collects cleanly
     And the architecture tier fails a run-time <violation> invariant
    When the whole-tree architecture run certifies the repository
    Then the whole-tree architecture run refuses the repository

    Examples:
      | violation                 |
      | forbidden dev-root import |
      | inline interpreter spawn  |
      | seeded runtime assertion  |

  @slice-01 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario Outline: No shape of unrelated architecture failure blocks a slice whose own scope is green
    Given a slice whose feature scope collects cleanly
     And the architecture tier fails a run-time <violation> invariant
    When the exit gate certifies the slice over its feature scope
    Then the gate clears the slice's feature scope
     And the refusal never names a file outside the entering slice's own scope

    Examples:
      | violation                 |
      | forbidden dev-root import |
      | inline interpreter spawn  |
      | seeded runtime assertion  |
