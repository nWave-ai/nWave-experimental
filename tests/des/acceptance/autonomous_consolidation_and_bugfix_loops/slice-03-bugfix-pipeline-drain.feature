@feature-autonomous-consolidation-and-bugfix-loops @slice-03
# Feature: The bugfix loop drains the defect queue as a pipeline. Charter:
#          docs/product/expectations/autonomous-consolidation-and-bugfix-loops/
#          the-bugfix-loop-drains-the-queue-as-a-pipeline.md
# Slice: 03 (feature-delta Slice Plan row slice-03, Locked Decision D-4).
# The feature's SINGLE @walking_skeleton already lives on slice-01
# (feature-delta WS Strategy) -- every scenario below drives the real
# driving port IN-PROCESS (Architecture of Reference default), never
# subprocess-e2e.
#
# ── THE TWO-LANE PIPELINE (D-4, verbatim) ──
# Cloud-lane stages (RCA, charter authoring, AT authoring) fan out
# concurrently at near-zero box cost -- no ceiling. Box-lane stages (RED
# seal, crafter's GREEN pass, Vera's examine, commit-slice) stay strictly
# serialized to exactly ONE in-flight item -- a LOCAL invariant the
# pipeline itself ENFORCES (a concurrent second entry is DEFERRED, never
# silently admitted, never silently dropped), no cross-instance
# coordination required. Full contract:
# tests/des/acceptance/autonomous_consolidation_and_bugfix_loops/steps/domain_types_slice_03.py
#
# ── DRIVING PORT (Mandate-13, invariant 1+2) ──
# The driving port is the REAL `des bugfix-pipeline-tick` CLI entry
# (`des.cli.bugfix_pipeline_tick.main`), driven IN-PROCESS via the shared
# `run_cli_in_process` helper -- NEVER a direct
# `from des.domain.bugfix_pipeline import evaluate_and_record` invocation
# (that seam does not exist yet -- it is DELIVER's job to build).
#
# ── THE CONTROLLABLE CLOCK (deterministic, NO real sleep) ──
# Every tick supplies an explicit synthetic `--now` instant computed from a
# fixed base + a minute offset -- the whole multi-defect drain is walked in
# test-process time, never a real wait.
#
# ── THE TERMINAL ASSERTION (the load-bearing NEW behavior, RED today) ──
# `des.cli.bugfix_pipeline_tick.main` exists ONLY as a RED scaffold today:
# it parses its args, then lazily imports the not-yet-built
# `des.domain.bugfix_pipeline` seam, catches the resulting
# `ModuleNotFoundError`, emits a named `PIPELINE_NOT_WIRED` line, and
# returns exit 2 WITHOUT ever touching the ledger. So every scenario below
# RED-fails for the right reason: the ledger is byte-for-byte silent no
# matter how many ticks fire, because nothing is wired yet. Every positive
# assertion below requires POSITIVE ledger evidence -- AT-15 additionally
# carries an explicit discriminator (box-lane activity genuinely observed)
# guarding its "never exceeds 1" negative check against a vacuous pass
# against this silent scaffold.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + filesystem only, cross-OS. No git subprocess needed for this
# slice -- only the ledger + the injected clock.
#
# Universe (Mandate 8): {outcome.cloud_lane_concurrent_count,
# outcome.box_lane_concurrent_count, outcome.box_lane_activity_observed,
# outcome.box_lane_entry_deferred, outcome.deferred_reason_named,
# outcome.full_chain_traceable, outcome.slice_commit_verified_present,
# outcome.drain_claim_rejected, outcome.rejection_reason_named,
# outcome.mid_pipeline_failure_recorded, outcome.box_lane_freed_after_failure,
# outcome.new_record_count}. Internal fields (Popen handle, argv list, raw
# ledger path) NEVER appear.
#
# Layer 3/4 (real filesystem + real ledger JSONL + real in-process CLI
# invocation against tmp_path): example-only (Mandate 9 v2 -- @real-io =>
# example-based, NOT PBT). Sad paths explicit (Mandate 11). No PBT
# machinery.
#
# Carpaccio ceiling: 6 counted scenarios (1 Scenario Outline collapses to
# ONE parsed scenario + 5 plain Scenarios), authored as a @coupled group
# bound by ONE contract -- the D-4 two-lane pipeline invariant. 4 of 6
# (67%) are negative/error-path scenarios (AT-12/AT-14/AT-15/AT-16),
# exceeding the 40%+ error-path target.

Feature: The bugfix loop drains the defect queue as a pipeline
  As an operator draining a queue of several defects
  I want cloud-lane work to fan out while the box lane stays serialized to one
  So that N defects drain in roughly the time one box lane takes, never N times that, and I never take "done" on faith

  # ─────────────────────────────────────────────────────────────────────────
  # AT-11 -- CLOUD LANES FAN OUT WHILE THE BOX LANE HOLDS AT MOST ONE
  # (RED today). Mirrors feature-delta Domain Example 3 verbatim: two
  # defects in RCA, one mid-AT-authoring (cloud lane, 3 concurrent), one in
  # the crafter's GREEN pass (box lane, the only item there).
  # contract-shape:bounded-change -- the declared mutation is the set of
  # PipelineStageStarted records this tick's fan-out appends.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @bugfix-pipeline @contract-shape:bounded-change @covers-R11 @covers-R12
  Scenario: Cloud lanes fan out while the box lane holds at most one item
    Given a fresh bugfix pipeline
    When "defect-1" starts RCA at minute 0
    And "defect-2" starts RCA at minute 1
    And "defect-3" starts AT authoring at minute 2
    And "defect-4" starts crafter's GREEN pass at minute 3
    Then sampled at minute 5, the cloud lane holds at least 2 items in flight while the box lane holds at most 1

  # ─────────────────────────────────────────────────────────────────────────
  # AT-12 -- A CONCURRENT SECOND BOX-LANE ENTRY IS DEFERRED, NEVER SILENTLY
  # ADMITTED OR DROPPED (CRITICAL negative, RED today). D-4's own
  # enforcement mechanism: while defect-5 holds an open box-lane stage,
  # defect-6's attempt to enter a DIFFERENT box-lane stage must be turned
  # away with a named reason.
  # contract-shape:bounded-change -- the declared mutation is the
  # BoxLaneEntryDeferred record itself, in place of a silent second
  # admission.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @bugfix-pipeline @negative @contract-shape:bounded-change @covers-R12 @covers-R13
  Scenario: A concurrent second box-lane entry is deferred, never silently admitted
    Given a fresh bugfix pipeline
    When "defect-5" starts RED seal at minute 0
    And "defect-6" starts crafter's GREEN pass at minute 1
    Then sampled at minute 1, the box lane still holds exactly 1 item and "defect-6"'s entry was deferred with a named reason

  # ─────────────────────────────────────────────────────────────────────────
  # AT-13 -- A FULLY-DRAINED DEFECT HAS A TRACEABLE LEDGER CHAIN (RED
  # today). Charter Positive-2: "an operator can point at the exact record
  # proving each stage happened."
  # contract-shape:bounded-change -- the declared mutation is the full
  # ordered 7-stage completion chain for one defect.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @bugfix-pipeline @contract-shape:bounded-change @covers-R14 @covers-R15
  Scenario: A fully-drained defect has a traceable ledger chain from RCA to commit-slice
    Given a fresh bugfix pipeline
    When "defect-7" walks the full pipeline from RCA to commit-slice starting at minute 0
    Then "defect-7"'s ledger chain traces RCA, charter authoring, AT authoring, RED seal, crafter's GREEN pass, Vera's examine and commit-slice in order, backed by a commit-slice-verified record

  # ─────────────────────────────────────────────────────────────────────────
  # AT-14 -- NO "DRAINED" CLAIM WITHOUT A COMMIT-SLICE-VERIFIED RECORD
  # (CRITICAL negative, D-8, RED today). Charter Negative-1, verbatim: "no
  # defect is ever marked 'done'/'drained' without a `SliceCommitVerified`-
  # class ledger record backing it."
  # contract-shape:bounded-change -- the declared mutation is the
  # DrainClaimRejectedNoAttestation record itself, proven as a positive
  # enforcement, not an absence check.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @bugfix-pipeline @negative @contract-shape:bounded-change @covers-R15
  Scenario: A "drained" claim with no commit-slice attestation is rejected, never silently accepted
    Given a fresh bugfix pipeline
    When someone claims "defect-8" is drained at minute 0
    Then "defect-8"'s drain claim was rejected for lacking a commit-slice-verified record, with a named reason

  # ─────────────────────────────────────────────────────────────────────────
  # AT-15 -- THE BOX LANE NEVER EXCEEDS ONE AT ANY SAMPLED MOMENT ACROSS A
  # FULL DRAIN (CRITICAL negative, RED today). D-8/D-4 negative-oracle,
  # verbatim: "the box lane never shows 2+ items genuinely in flight at the
  # same sampled moment." Sampled repeatedly across a longer, serialized
  # multi-defect drain -- not a single hand-picked instant. Scenario
  # Outline collapses to ONE counted scenario; 3 Examples sweep the
  # sample-instant axis.
  # contract-shape:bounded-change -- the declared mutation is the ongoing
  # serialized sequence of box-lane start/complete records this invariant
  # is checked against.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @bugfix-pipeline @negative @contract-shape:bounded-change @covers-R12
  Scenario Outline: The box lane never exceeds one item at any sampled moment across a drain
    Given a fresh bugfix pipeline
    When "defect-9", "defect-10" and "defect-11" walk crafter's GREEN pass one after another starting at minute 0 with a 4-minute gap
    Then sampled at minute <sample_minute>, the box lane holds at most 1 item and box-lane activity was genuinely observed

    Examples:
      | sample_minute |
      | 1             |
      | 5             |
      | 9             |

  # ─────────────────────────────────────────────────────────────────────────
  # AT-16 -- A MID-PIPELINE FAILURE IS ROUTED OUT LOUDLY AND FREES THE BOX
  # LANE (RED today). Charter "What to explore": "does the pipeline
  # correctly route it out (fail loud) instead of silently marking it
  # done, and does that failure free up the box lane for the next item?"
  # contract-shape:bounded-change -- the declared mutations are the
  # PipelineStageFailed record and the subsequent ADMITTED (not deferred)
  # box-lane entry for the next defect.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @bugfix-pipeline @negative @contract-shape:bounded-change @covers-R16 @covers-R13
  Scenario: A defect that fails its crafter's GREEN pass is routed out loudly and frees the box lane
    Given a fresh bugfix pipeline
    When "defect-12" starts crafter's GREEN pass at minute 0
    And "defect-12"'s crafter's GREEN pass fails at minute 2 because "2 tests still red after the fix"
    And "defect-13" starts RED seal at minute 3
    Then sampled at minute 3, "defect-12"'s failure was recorded loudly with a named reason and "defect-13"'s box-lane entry was admitted, not deferred
