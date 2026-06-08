@feature-gate-trailer-read-git-port-extract @slice-01
Feature: The deliver-integrity done-gate refuses LOUD when it cannot read the commit-trailer history
  As an nWave operator running des verify-integrity at feature-end on a target machine
  I want the gate to refuse with a LOUD cannot-evaluate verdict whenever git is
    absent or the directory is not a git work-tree
  So that a git-less target can never be silently mistaken for an empty,
    "nothing shipped" delivery -- the genericita / target-machine-agnosticism
    guarantee (a git-absence is a refusal, never a silent pass)

  # slice-01 of gate-trailer-read-git-port-extract -- THE WALKING SKELETON
  # (DISCUSS Slice Plan slice-01 + DESIGN Per-Slice Companion slice-01). The
  # thinnest honest end-to-end vertical: a deliver project that demands trailer
  # reconciliation but sits in a NON-git-work-tree -> the gate cannot read the
  # commit-trailer history -> it emits the LOUD
  # `health.gate.deliver-integrity.indeterminate` event and refuses with the
  # distinct cannot-evaluate exit code 4. NOT the silent `frozenset()` pass that
  # masks git-absence as "nothing shipped" (today's bug); NOT exit 1
  # `FeatureUnreconciled` (the trailer history WAS read but a slice lacks a
  # ledger record -- a different, structurally-distinct non-pass).
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
  # `des verify-integrity` CLI, invoked as a subprocess black box
  # (`python -m des.cli.verify_deliver_integrity <synthetic-dir> --feature-id <id>`).
  # `_shipped_slices` is NEVER imported-and-called at the step boundary (that
  # would be a Layer-1 unit test masquerading as an AT). The observable surface
  # is the process exit code, the single-line JSON `FeatureIndeterminate` event
  # on stdout, and the human-readable reason -- nothing else. The composition
  # root default-wires the real `GitCommitTrailerReadAdapter`, so the genuine
  # git-absence degrade is exercised end-to-end, not an in-memory fake.
  #
  # RED-for-right-reason (ADR-025 + ADR-028, pre-DELIVER fail-for-right-reason
  # gate): on master `_shipped_slices` swallows git-absence as
  # `except (CalledProcessError, FileNotFoundError): return frozenset()`
  # (verify_deliver_integrity.py:207-208), so a NON-git-work-tree with a present,
  # integrity-clean ledger falls through to the feature-end check and EXITS 0
  # ("All slices have a complete AT-completion ledger trace") -- the silent
  # fabrication. The Then-steps assert exit 4 + the LOUD INDETERMINATE event and
  # therefore fail with a semantic AssertionError (the cannot-evaluate verdict is
  # absent; the gate silently passed) -- never a collection / import / setup
  # error in the test process (the step modules import only test-local types).
  # Empirically confirmed: today the synthetic tree below yields exit 0. The ATs
  # PASS once DELIVER lands the CommitTrailerReadPort + GitCommitTrailerReadAdapter
  # + the silent->loud re-point of `_shipped_slices`.
  #
  # HARD INVARIANT (D1, ratified): INDETERMINATE = LOUD + a distinct
  # cannot-evaluate non-pass (exit 4), NEVER a silent frozenset and NEVER
  # conflated with FeatureUnreconciled (exit 1). The LOUD event ALWAYS fires on a
  # cannot-read condition. `verify_deliver_integrity` is a done-gate verifier read
  # at feature-end (NOT the non-halting per-slice hook tap), so a git-absence is a
  # genuine cannot-evaluate boundary that MUST refuse (exit != 0).
  #
  # NON-VACUITY (perturbation-bound, KPI #2 guardrail): the two cannot-evaluate
  # scenarios are paired with a CONTROL -- a REAL git work-tree carrying a
  # `Slice-Id:` commit + a matching ledger record reconciles cleanly (exit 0,
  # FeatureReconciled). The refusal is therefore bound to the readability of the
  # trailer history, not vacuously always-on. (slice-02 deepens the git-present
  # happy path; this control proves the slice-01 refusal is not always-on.)
  #
  # SUT verdict model (C2 / C6): on a deliver project that demands trailer
  # reconciliation, the gate resolves to one of {cannot-evaluate (the trailer
  # history is unreadable -> git absent / not a work-tree -> LOUD INDETERMINATE,
  # exit 4), reconciled (the history was read and every shipped slice has a
  # ledger record -> exit 0)}. The materially-distinct decision-table rows: git
  # binary absent -> exit 4; directory is not a work-tree -> exit 4; real
  # work-tree with a recorded slice -> exit 0.
  #
  # TAG SCHEME (strict-markers safe -- mirrors the sibling suite
  # oss-dormant-seam-gate): scenario @tags are converted to dynamic pytest marks
  # by pytest-bdd's tag pipeline; the project's filterwarnings (pyproject.toml)
  # suppresses PytestUnknownMarkWarning so --strict-markers does not reject them.
  # Binding goes through pytest-bdd's scenario machinery via the RELATIVE
  # `scenarios("../<feature>")` from the steps/ module (the proven-collecting
  # form). The immutable @contract-shape tag is machine-parseable per the
  # 2026-05-15 mandate: this gate is an unbounded-preservation observer -- it
  # reads the trailer history and refuses/reconciles WITHOUT mutating the
  # deliver project (the pure-read contract asserted by the When-step universe).

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A deliver project demanding reconciliation in a non-git directory is refused with a loud cannot-evaluate verdict
    Given a deliver project that demands slice reconciliation but is not a git work-tree
    When the operator runs des verify-integrity for that feature
    Then the gate refuses with a loud cannot-evaluate verdict
    And the gate names the cannot-evaluate reason in the loud verdict
    And the gate does not silently report the delivery as nothing-shipped
    And the gate does not mutate the deliver project

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A deliver project demanding reconciliation with the git binary unavailable is refused with a loud cannot-evaluate verdict
    Given a deliver project that demands slice reconciliation but the git binary is unavailable
    When the operator runs des verify-integrity for that feature
    Then the gate refuses with a loud cannot-evaluate verdict
    And the cannot-evaluate refusal is distinct from an unreconciled-slice verdict

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A real git delivery carrying a recorded slice still reconciles cleanly
    Given a deliver project in a git work-tree carrying a recorded shipped slice
    When the operator runs des verify-integrity for that feature
    Then the gate reconciles the delivery cleanly
