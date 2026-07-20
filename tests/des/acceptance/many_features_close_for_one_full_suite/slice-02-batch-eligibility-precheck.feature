@feature-many-features-close-for-one-full-suite @slice-02
# Feature: A batch with one not-ready feature refuses as a whole.
#          Charter: docs/product/expectations/many-features-close-for-one-full-suite/
#          a-batch-with-one-not-ready-feature-refuses-as-a-whole.md
# Slice: 02 (batch-eligibility precheck, feature-delta Slice Plan row
#         slice-02, Locked Decision D-5, D-D7). depends-on slice-01.
#
# -- DISTILL-interim wire contract (nothing exists yet to reverse-engineer,
# mirrors slice-01's own precedent) -- the batch-eligibility precheck emits
# exactly ONE terminal JSON line when ANY member is ineligible:
#   {"event": "FeatureEndBatchIneligible", "verb": "run-batch",
#    "feature_id": <the ineligible member>, "error": <WHAT+WHY+HOW, naming
#    the feature_id AND the failed check>}
# and exits 2, with ZERO member lines printed and ZERO gates dispatched
# (GDP-1, mirrors AT-BATCH-3's malformed-manifest zero-gates guarantee).
# Full contract:
# tests/des/acceptance/many_features_close_for_one_full_suite/steps/domain_types_slice_02.py
#
# -- DESIGN DISCOVERY (this slice) -- two of D-5's three checks are ALREADY
# per-member gates today (Slice-Plan SliceCommitVerified truncation, charter
# EXAMINE), each firing AFTER the shared full-suite leg already ran; slice-02
# HOISTS both to a whole-batch, run-start precheck. Only the deep-review-
# APPROVED check is genuinely new. See feature-delta.md
# [REF] Design Discovery (slice-02) for the full table + a flagged
# regression risk on slice-01's own AT-BATCH-5.
#
# -- DRIVING PORT (Mandate-13, invariant 1+2) --
# The REAL `des feature-end run-batch` CLI, in-process via the SAME
# production `des.cli.__main__` dispatcher every other scenario in this
# feature uses. No second @walking_skeleton -- the feature's ONE
# subprocess-e2e proof already lives in slice-01 (AT-BATCH-1); every
# slice-02 scenario drives in-process, per the feature's own WS Strategy
# ("wiring coverage is a declared triple ... never scenario multiplication").
#
# -- RED reason (P1-P4 in-process active-RED) --
# `run_feature_end_batch` (slice-01, SHIPPED) runs NO whole-batch
# eligibility precheck. Every negative scenario below observes today's REAL
# shipped outcome (either a per-member CycleRefusal + a co-member
# CycleComplete, or BOTH members CycleComplete) compared against this
# slice's contract -- a genuine semantic AssertionError, never a crash.
#
# -- Mechanical assertion (Mandate-13 invariant 5) --
# Python + filesystem + one real (hermetic, tmp_path-scoped) pytest suite
# only, cross-OS. Every observable is re-derived from REAL filesystem state
# (the persisted JUnit artifact COUNT) and the REAL AT-completion ledger
# JSONL, independent of whether the CLI's own payload parses.
#
# Universe (Mandate 8): {exit_code, lines[0].event/feature_id/error,
# junit_artifact_count, feature_end_records_for(<feature_id>)}. Internal
# fields (raw stdout, Popen handles) NEVER appear.
#
# Layer 3 (a hermetic tmp_path git-free pytest repo, no subprocess fork
# needed for this slice's scope): example-only (Mandate 9 v2). Sad paths
# explicit (Mandate 11). No PBT machinery.
#
# Carpaccio: 4 scenarios (3 negative + 1 positive no-regression pin), a
# right-sized precheck slice per D-5/D-D7, reusing `BatchFixture` (slice-01)
# per the feature-delta's own forward-looking consolidation note.

Feature: A batch with one not-ready feature refuses as a whole
  As a maintainer closing several ready features around the same time
  I want an ineligible batch member named and the whole batch refused up front
  So that no feature closes silently while another member is still unfinished

  # ─────────────────────────────────────────────────────────────────────────
  # D-5 check 1 / Domain Example 2 (Diego Ferreira). RED today.
  # contract-shape:unbounded-preservation -- nothing is ever touched; the
  # refusal happens before any gate is dispatched.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-02 @driving_port @negative @contract-shape:unbounded-preservation @covers-R6 @covers-R9
  Scenario: An undelivered Slice-Plan slice refuses the whole batch
    Given a shared repository whose whole-tree suite is green
    And a batch of one ready feature and one feature whose Slice-Plan slice was never delivered
    When the maintainer runs the batch-eligibility precheck in-process
    Then the batch refuses citing the ineligible feature and the failed check
    And the whole-tree check never ran
    And neither feature has a closing record

  # ─────────────────────────────────────────────────────────────────────────
  # D-5 check 2. RED today.
  # contract-shape:unbounded-preservation -- nothing is ever touched.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-02 @driving_port @negative @contract-shape:unbounded-preservation @covers-R7 @covers-R9
  Scenario: A non-approved deep-review verdict refuses the whole batch
    Given a shared repository whose whole-tree suite is green
    And a batch of one ready feature and one feature declaring a non-approved deep-review verdict
    When the maintainer runs the batch-eligibility precheck in-process
    Then the batch refuses citing the ineligible feature and the failed check
    And the whole-tree check never ran
    And neither feature has a closing record

  # ─────────────────────────────────────────────────────────────────────────
  # D-5 check 3. RED today.
  # contract-shape:unbounded-preservation -- nothing is ever touched.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-02 @driving_port @negative @contract-shape:unbounded-preservation @covers-R8 @covers-R9
  Scenario: A critical charter that failed EXAMINE refuses the whole batch
    Given a shared repository whose whole-tree suite is green
    And a batch of one ready feature and one feature whose critical charter failed EXAMINE
    When the maintainer runs the batch-eligibility precheck in-process
    Then the batch refuses citing the ineligible feature and the failed check
    And the whole-tree check never ran
    And neither feature has a closing record

  # ─────────────────────────────────────────────────────────────────────────
  # No-regression pin -- already GREEN today (slice-01's shipped machinery).
  # contract-shape:bounded-change -- one declared mutation: the sole
  # feature's own closing record.
  # ─────────────────────────────────────────────────────────────────────────
  @slice-02 @driving_port @contract-shape:bounded-change @covers-R10
  Scenario: A genuinely, fully-attested-eligible batch proceeds unaffected
    Given a shared repository whose whole-tree suite is green
    And a single feature that is fully attested eligible for the batch
    When the maintainer runs the batch-eligibility precheck in-process
    Then the batch completes and the feature has its own closing record
