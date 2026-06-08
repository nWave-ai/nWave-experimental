@feature-gate-trailer-read-git-port-extract @slice-02
Feature: The deliver-integrity verdict is computed through a git-FREE gate core
  As an nWave operator running des verify-integrity on ANY target machine
  I want the deliver-integrity verdict to be derived purely from a
    CommitTrailerReadPort -- with no git coupling baked into the gate core --
  So that a target machine whose commit-trailer source is NOT git (a non-git
    SCM, a synthesized trailer stream, a future adapter) still reconciles
    exactly the same way, and git is genuinely just one swappable adapter

  # slice-02 of gate-trailer-read-git-port-extract (DISCUSS Slice Plan slice-02
  # + DESIGN Per-Slice Companion slice-02). The GENUINE distinct value left after
  # slice-01: slice-01 proved git-ABSENCE degrades LOUD via the REAL
  # GitCommitTrailerReadAdapter through the CLI; its non-vacuity control read a
  # REAL git work-tree. NEITHER slice-01 scenario proves the gate CORE is
  # genuinely git-FREE -- that a NON-git CommitTrailerReadPort can feed the
  # verdict and reconcile WITHOUT any git involvement at all. That is the actual
  # genericita / target-machine-agnosticism claim (AD-21/24): git is one
  # swappable adapter, the core depends only on the port abstraction.
  #
  # DRIVING SURFACE (Mandate-13, tolerable contract-AT variant -- the R3
  # slice-03 shape, justified): the value "the CORE is git-free, the port is
  # genuinely swappable" CANNOT be proven through the slice-01 CLI subprocess
  # black box, because `main()` HARDCODES `trailer_port=GitCommitTrailerReadAdapter()`
  # (verify_deliver_integrity.py:645) -- there is NO env/flag that selects a
  # non-git trailer source (option (a) is unavailable). The honest shape is
  # therefore option (b): the gate core's PUBLIC DESIGN-INTENDED INJECTION SEAM
  # (`_verify_atdd_pure(project_dir, roadmap_path, feature_id, trailer_port=...)`
  # -- the driving-side-consumed driven-port boundary the DESIGN composition-root
  # wiring exists for) IS the seam under test. A FAKE `CommitTrailerReadPort`
  # honoring the same interface is substituted (Architecture-of-Reference: an
  # in-memory double for a driven port -- the textbook treatment). This is NOT a
  # forbidden direct-domain import: the substrate is exercised THROUGH the port
  # boundary the architecture designed for substitution, never by reaching into
  # the trailer-scan internals. The fake is the ONLY driven adapter in the
  # composition, so per Mandate 9 v2 OR-reduction this slice is @in-memory and
  # example-based + assert_state_delta is the correct treatment.
  #
  # GIT-FREEDOM PROOF (the load-bearing genericita assertion): every scenario
  # runs on a `tmp_path` that is NOT a git work-tree (no `.git`). If the gate
  # core had ANY residual git coupling it would itself raise on the non-work-tree
  # -- but the verdict is derived entirely from what the fake port returns, with
  # zero git calls. The core reconciling / refusing on a non-git tree, fed only
  # by the fake port, IS the proof that the core is git-free.
  #
  # NON-VACUITY (perturbation-bound, KPI #2 guardrail): "reconciles via a non-git
  # port" is paired with a CONTROL -- a fake returning a `Slice-Id` trailer for a
  # slice NOT in the verified ledger set yields FeatureUnreconciled (exit 1). The
  # reconciliation is therefore genuinely bound to what the port returns, not
  # vacuously always-pass. A third scenario perturbs the port to Indeterminate
  # and asserts the LOUD exit-4 refusal -- proving the degrade-LOUD path is a
  # PORT-CONTRACT property (any source that cannot read refuses LOUD), not a
  # git-specific behavior.
  #
  # SUT verdict model: on a deliver project that demands trailer reconciliation,
  # fed by a non-git CommitTrailerReadPort, the gate core resolves to one of
  # {reconciled (the port supplied a matching trailer -> exit 0 FeatureReconciled),
  # unreconciled (the port supplied a NON-matching trailer -> exit 1
  # FeatureUnreconciled), cannot-evaluate (the port returned Indeterminate ->
  # exit 4 FeatureIndeterminate)}. Materially-distinct decision-table rows, all
  # reached WITHOUT git.
  #
  # Mandate 14 (contract-shape): all 3 scenarios @contract-shape:unbounded-preservation
  # -- the gate core reads the (fake) trailer stream and reconciles/refuses WITHOUT
  # mutating the deliver project (pinned by the pure-read universe guard, Mandate 8).

  @slice-02 @driving_port @in-memory @contract-shape:unbounded-preservation
  Scenario: A delivery whose trailers come from a non-git source reconciles cleanly
    Given a deliver project that demands slice reconciliation in a non-git tree
    And the commit-trailer history is supplied by a non-git source recording the shipped slice
    When the operator verifies the delivery through the git-free gate core
    Then the gate core reconciles the delivery cleanly without consulting git
    And the gate core does not mutate the deliver project

  @slice-02 @driving_port @in-memory @contract-shape:unbounded-preservation
  Scenario: A non-git trailer source missing the shipped slice leaves the delivery unreconciled
    Given a deliver project that demands slice reconciliation in a non-git tree
    And the commit-trailer history is supplied by a non-git source missing the shipped slice
    When the operator verifies the delivery through the git-free gate core
    Then the gate core leaves the delivery unreconciled
    And the unreconciled verdict is distinct from a cannot-evaluate refusal

  @slice-02 @driving_port @in-memory @contract-shape:unbounded-preservation
  Scenario: A non-git trailer source that cannot read refuses with a loud cannot-evaluate verdict
    Given a deliver project that demands slice reconciliation in a non-git tree
    And the commit-trailer history cannot be read by the non-git source
    When the operator verifies the delivery through the git-free gate core
    Then the gate core refuses with a loud cannot-evaluate verdict
