@feature-many-features-close-for-one-full-suite @slice-01
# Feature: A maintainer closes several ready features off one shared suite run.
#          Charter: docs/product/expectations/many-features-close-for-one-full-suite/
#          a-maintainer-closes-several-ready-features-off-one-shared-suite-run.md
# Slice: 01 (the WALKING SKELETON, feature-delta Slice Plan row slice-01,
#         Locked Decisions D-1/D-3, ADR-FEATURE-END-BATCH-001). D-D2 REUSE:
#         `run_feature_end_cycle` (SHIPPED) becomes a batch-of-one delegating
#         to the shared use-case this slice introduces -- never rebuilt.
#
# -- DISTILL-interim wire contract (feature-delta [REF] Driving Ports, pinned
# concretely here since nothing exists yet to reverse-engineer) --
# `des feature-end run-batch <manifest.json> --repo PATH` reads a JSON array
# of {feature_id, feature_dir, reviewer_agent_id, verdict} entries. A
# structurally malformed manifest emits ONE `FeatureEndBatchManifestRefused`
# line and exits 2 with ZERO gates dispatched (GDP-1). A valid manifest runs
# the whole-tree full-suite leg EXACTLY ONCE (D-3); on RED it emits ONE
# `FeatureEndBatchRefused` line (the EXISTING `failing_tests`/`failing_count`/
# `junit_artifact` enrichment, batch-scoped) and exits 2 with ZERO per-member
# cycles run (D-4). On PASS/NOT_APPLICABLE it runs each member's cycle in
# manifest order, printing the EXISTING `FeatureEndCycleComplete` /
# `FeatureEndCycleRefused` / `FeatureEndCycleIndeterminate` shapes (verb
# "run-batch"), followed by ONE trailing `FeatureEndBatchComplete` summary
# line. Full contract:
# tests/des/acceptance/many_features_close_for_one_full_suite/steps/domain_types_slice_01.py
#
# -- DRIVING PORT (Mandate-13, invariant 1+2) --
# The driving port is the REAL `des feature-end run-batch` / `des feature-end
# run` CLI -- driven in-process through the SAME production
# `des.cli.__main__` dispatcher every other `des <subcommand>` invocation
# uses, EXCEPT the feature's single `@walking_skeleton` scenario, which forks
# the REAL installed `des` console-script (mirrors the
# `parallel-work-cleans-up-after-merge-back` slice-01 precedent). NEVER a
# direct import of the not-yet-existing batch service module.
#
# -- RED reason (P1-P4 in-process active-RED) --
# `run-batch` is not yet a registered `feature-end` verb. Every scenario
# observes the REAL current sub-dispatcher's own argparse failure ("argument
# verb: invalid choice: 'run-batch'", exit 2) and fails with a semantic
# AssertionError comparing that to the contract this slice specifies -- never
# a naked traceback.
#
# -- Mechanical assertion (Mandate-13 invariant 5) --
# Python + filesystem + one real (hermetic, tmp_path-scoped) pytest suite
# only, cross-OS. Every observable is re-derived from REAL filesystem state
# (the persisted JUnit artifact COUNT under `.nwave/telemetry/feature-end/`)
# and the REAL AT-completion ledger JSONL, independent of whether the CLI's
# own payload parses.
#
# Universe (Mandate 8): {outcome.exit_code, outcome.batch_event,
# outcome.member_count, outcome.member_success_count,
# outcome.member_refused_count, outcome.junit_artifact_count,
# outcome.total_feature_end_records}. Internal fields (raw stdout, Popen
# handles) NEVER appear.
#
# Layer 3 (a hermetic tmp_path git-free pytest repo + one real subprocess
# fork for the walking skeleton, @real-io): example-only (Mandate 9 v2 --
# the driven set includes a real pytest/git subprocess seam => example-based,
# NOT PBT). Sad paths explicit (Mandate 11). No PBT machinery.
#
# Carpaccio: 5 counted scenarios, a 1:1 induction from the DESIGN wave's own
# `[REF] Architecture & Contract Tests` table (AT-BATCH-1..5) -- no
# over-authoring beyond what DESIGN already named as slice-01's scope.

Feature: A maintainer closes several ready features off one shared suite run
  As a maintainer closing several ready features around the same time
  I want the whole-tree full-suite check to run exactly once for the whole batch
  So that I stop paying its cost once per feature while every feature still gets its own closing record

  # ─────────────────────────────────────────────────────────────────────────
  # AT-BATCH-1 -- THE WALKING SKELETON (feature-delta WS Strategy, the
  # feature's SINGLE @walking_skeleton scenario). Litmus: a maintainer
  # closing 2 ready features sees ONE suite check run and TWO closing
  # records land.
  # contract-shape:bounded-change -- one declared mutation family: the ONE
  # shared full-suite artifact, plus each feature's own closing record.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @real-io @walking_skeleton @contract-shape:bounded-change @covers-R1
  Scenario: Closing two ready features in one batch pays the whole-tree check once
    Given two ready features sharing one repository whose whole-tree suite is green
    And a manifest naming both features for one batch run
    When the maintainer runs the batch close against the real installed des console-script
    Then the whole-tree check produced exactly one shared suite artifact
    And each of the two features has its own closing record

  # ─────────────────────────────────────────────────────────────────────────
  # AT-BATCH-4 -- BACKWARD-COMPAT + BATCH-OF-ONE EQUIVALENCE (D-1). RED
  # today -- `run-batch` does not exist, so the batch-of-one member line is
  # empty and can never match the classic close.
  # contract-shape:bounded-change -- one declared mutation: the one
  # feature's own closing record, produced identically by either entry
  # point.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @contract-shape:bounded-change @covers-R2
  Scenario: A batch of exactly one feature is indistinguishable from the classic close
    Given a single ready feature the maintainer already knows how to close alone
    When the maintainer closes it the classic way, and again through the batch entry point as a batch of one
    Then the batch entry point's own record for that feature matches the classic close exactly

  # ─────────────────────────────────────────────────────────────────────────
  # AT-BATCH-2 -- RED SHARED SUITE REFUSES THE WHOLE BATCH (D-3/D-4). RED
  # today.
  # contract-shape:unbounded-preservation -- no feature's closing state is
  # ever touched while the shared suite is red; the refusal is total.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @negative @contract-shape:unbounded-preservation @covers-R3
  Scenario: A red shared suite refuses the whole batch and closes nothing
    Given two ready features sharing one repository whose whole-tree suite is genuinely red
    And a manifest naming both features for one batch run
    When the maintainer runs the batch close in-process
    Then the batch refuses with a failing exit code
    And the refusal names the failing tests
    And neither feature has a closing record

  # ─────────────────────────────────────────────────────────────────────────
  # AT-BATCH-3 -- MALFORMED MANIFEST REFUSES BEFORE ANY CHECK RUNS (GDP-1,
  # D-D7/D-D8). RED today.
  # contract-shape:unbounded-preservation -- nothing is ever touched; the
  # refusal happens before any gate is dispatched.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @negative @contract-shape:unbounded-preservation @covers-R4
  Scenario: A structurally malformed manifest refuses before the expensive check ever runs
    Given two ready features sharing one repository whose whole-tree suite is green
    And a manifest where one entry is missing a required field
    When the maintainer runs the batch close in-process
    Then the batch refuses with a failing exit code
    And the whole-tree check never ran
    And the refusal names the malformed entry

  # ─────────────────────────────────────────────────────────────────────────
  # AT-BATCH-5 -- PER-MEMBER INDEPENDENCE ON A NON-SHARED REFUSAL (D-D6).
  # RECONCILED (R5 vs R6 conflict, feature-delta [REF] Design Discovery
  # slice-02): the OLD trigger (an undelivered Slice-Plan slice) is an
  # ELIGIBILITY failure -- slice-02's D-5 precheck now (correctly)
  # intercepts it BEFORE the per-member cycle, refusing the WHOLE batch
  # instead of demonstrating per-member independence. The trigger is now an
  # ELIGIBLE member (passes all 3 D-5 checks) whose OWN non-eligibility
  # per-member leg genuinely refuses -- the precheck lets the batch through;
  # D-D6 independence then applies exactly as before. RED today.
  # contract-shape:bounded-change -- one declared mutation: the ready
  # feature's own closing record; the leg-failing feature's own refusal
  # never merges into or suppresses it.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-01 @driving_port @covers-R5
  Scenario: One feature's own refusal never suppresses a batch-mate's successful close
    Given a batch of one ready feature and one eligible feature whose own leg refuses
    When the maintainer runs the batch close in-process
    Then the ready feature still has its own closing record
    And the not-ready feature has no closing record of its own
    And the whole-tree check still produced exactly one shared suite artifact
