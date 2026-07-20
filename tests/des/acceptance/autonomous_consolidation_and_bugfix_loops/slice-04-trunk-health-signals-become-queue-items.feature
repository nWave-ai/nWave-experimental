@feature-autonomous-consolidation-and-bugfix-loops @slice-04
# Feature: Trunk-health signals become queue items that never vanish. Charter:
#          docs/product/expectations/autonomous-consolidation-and-bugfix-loops/
#          trunk-health-signals-become-queue-items-that-never-vanish.md
# Slice: 04 (feature-delta Slice Plan row slice-04, building on Locked
# Decision D-4's shared two-lane pipeline slice-03 built). The feature's
# SINGLE @walking_skeleton already lives on slice-01 (feature-delta WS
# Strategy) -- every scenario below drives the real driving port IN-PROCESS
# (Architecture of Reference default), never subprocess-e2e.
#
# ── REUSE, DON'T REBUILD (D-4/D-19 resolution, verbatim) ──
# A detected trunk-health signal (drift / un-merged work / stale branch /
# failing gate) becomes exactly one queue item by entering the SAME shared
# pipeline slice-03 built, at its FIRST cloud-lane stage (RCA) -- via a
# DIRECT call into the SAME `des.domain.bugfix_pipeline.evaluate_and_record`
# seam slice-03 already ships (GREEN today), never a bespoke per-signal-type
# runner and never a second pipeline/ledger-event-vocabulary. This slice adds
# exactly ONE net-new thing: signal-to-queue-item INTAKE (the derivation of a
# stable defect_id from `(signal_type, signal_key)` + the idempotency check
# that stops a re-detected, still-unresolved signal from duplicating its
# queue item). Full contract:
# tests/des/acceptance/autonomous_consolidation_and_bugfix_loops/steps/domain_types_slice_04.py
#
# ── DRIVING PORT (Mandate-13, invariant 1+2) ──
# The driving port is the REAL `des consolidation-signal-tick` CLI entry
# (`des.cli.consolidation_signal_tick.main`), driven IN-PROCESS via the
# shared `run_cli_in_process` helper -- NEVER a direct
# `from des.domain.consolidation_queue_intake import intake_signal`
# invocation (that seam does not exist yet -- it is DELIVER's job to build).
# AT-19 additionally drives the SIBLING slice-03 driving port
# (`des.cli.bugfix_pipeline_tick.main`) directly against the SAME queue item
# -- the mechanical proof that the item flows through the SAME shared
# pipeline, not a lookalike duplicate.
#
# ── DISTILL-INTERIM SCOPE DECISION (row 7b advisory -- DESIGN was skipped
# for this feature; see feature-delta.md's own "Design Skipped" section) ──
# The DRIVING PORT boundary for this slice is the SIGNAL-TO-QUEUE-ITEM
# INTAKE contract only: the caller supplies an ALREADY-DETECTED
# `(signal_type, signal_key)` pair. Scanning the actual git/CI state to
# DECIDE whether a branch is stale, a gate is failing, drift exists, or work
# sits unmerged is OUT OF SCOPE for this slice's ATs -- exactly the same
# carve-out the feature-delta's own Out-of-Scope table already grants
# defect-classification/triage for slice-03 ("assumed as an existing input
# ... this feature only makes the DRAINING of that queue reliable, not the
# triage that populates it"). The charter's real-repo detection walkthrough
# ("What to explore") is Vera's EXAMINE job against the real surface, not
# this AT's job (methodology principle 5: DISTILL drives IN-PROCESS/example-
# based; EXAMINE exercises every charter observable through the REAL
# surface).
#
# ── THE CONTROLLABLE CLOCK (deterministic, NO real sleep) ──
# Every tick supplies an explicit synthetic `--now` instant computed from a
# fixed base + a minute offset -- the whole multi-signal intake sequence is
# walked in test-process time, never a real wait.
#
# ── THE TERMINAL ASSERTION (the load-bearing NEW behavior, RED today) ──
# `des.cli.consolidation_signal_tick.main` exists ONLY as a RED scaffold
# today: it parses its args, then lazily imports the not-yet-built
# `des.domain.consolidation_queue_intake` seam, catches the resulting
# `ModuleNotFoundError`, emits a named `CONSOLIDATION_INTAKE_NOT_WIRED`
# line, and returns exit 2 WITHOUT ever touching the ledger. So every
# scenario below RED-fails for the right reason: the ledger is
# byte-for-byte silent no matter how many ticks fire, because nothing is
# wired yet.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + filesystem only, cross-OS. No git subprocess needed for this
# slice's ATs (the real-repo walkthrough is EXAMINE's job) -- only the
# ledger + the injected clock.
#
# Universe (Mandate 8): {outcome.queue_item_count, outcome.traceable_to_signal,
# outcome.full_chain_traceable, outcome.slice_commit_verified_present,
# outcome.intake_rejected, outcome.rejection_reason_named}. Internal fields
# (Popen handle, argv list, raw ledger path, the derived defect_id string
# itself) NEVER appear as Universe entries.
#
# Layer 3/4 (real filesystem + real ledger JSONL + real in-process CLI
# invocation against tmp_path): example-only (Mandate 9 v2 -- @real-io =>
# example-based, NOT PBT). Sad paths explicit (Mandate 11). No PBT
# machinery.
#
# Carpaccio ceiling: 6 counted scenarios (1 Scenario Outline collapses to
# ONE parsed scenario + 5 plain Scenarios), authored as a @coupled group
# bound by ONE contract -- the D-4/D-19 signal-to-shared-pipeline intake
# invariant. 3 of 6 (50%) are negative/error-path scenarios
# (AT-20/AT-21/AT-22), exceeding the 40%+ error-path target.

Feature: Trunk-health signals become queue items that never vanish
  As the operator of the consolidation loop
  I want every detected trunk-health signal to become exactly one queue item flowing through the same reliable pipeline the bugfix loop drains
  So that I never wonder whether a problem the loop noticed actually got queued, and no signal type needs its own bespoke handler

  # ─────────────────────────────────────────────────────────────────────────
  # AT-17 -- EACH SIGNAL TYPE, TRIGGERED INDIVIDUALLY, BECOMES EXACTLY ONE
  # TRACEABLE QUEUE ITEM (RED today). Charter Positive-1, verbatim: "each of
  # the four signal types ... triggered individually, produces exactly one
  # queue item traceable back to the specific signal." Scenario Outline
  # collapses to ONE counted scenario; 4 Examples sweep every signal type.
  # contract-shape:bounded-change -- the declared mutation is the single
  # PipelineStageStarted(rca) record this signal's intake appends.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @consolidation-intake @contract-shape:bounded-change @covers-R17
  Scenario Outline: Each trunk-health signal type becomes exactly one queue item traceable back to it
    Given a fresh consolidation intake
    When a "<signal_type>" signal for "<signal_key>" is detected at minute 0
    Then sampled at minute 1, that signal produced exactly one queue item traceable back to it

    Examples:
      | signal_type   | signal_key            |
      | drift         | trunk                 |
      | unmerged-work | feature/old-branch    |
      | stale-branch  | feature/stale-branch  |
      | failing-gate  | lint                  |

  # ─────────────────────────────────────────────────────────────────────────
  # AT-18 -- MULTIPLE SIGNAL TYPES PRESENT AT ONCE PRODUCE ONE QUEUE ITEM PER
  # SIGNAL, NONE MERGED OR DROPPED (RED today). Charter Positive-2, verbatim.
  # contract-shape:bounded-change -- the declared mutation is the set of 4
  # distinct PipelineStageStarted(rca) records this batch appends.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @consolidation-intake @contract-shape:bounded-change @covers-R18
  Scenario: A repository state with multiple signal types at once produces one queue item per signal
    Given a fresh consolidation intake
    When a "drift" signal for "trunk" is detected at minute 0
    And a "unmerged-work" signal for "feature/old-branch" is detected at minute 1
    And a "stale-branch" signal for "feature/stale-branch" is detected at minute 2
    And a "failing-gate" signal for "lint" is detected at minute 3
    Then sampled at minute 4, exactly 4 distinct queue items are observed, one per signal

  # ─────────────────────────────────────────────────────────────────────────
  # AT-19 -- A QUEUED SIGNAL FLOWS THROUGH THE SAME PIPELINE STAGES A BUGFIX
  # DEFECT DOES (RED today). D-19 resolution, mechanically proven: the item
  # this slice's intake queued at RCA is walked through the REST of the
  # chain using the SIBLING slice-03 driving port directly
  # (`des bugfix-pipeline-tick`) -- the mechanical reuse proof, not merely an
  # assertion.
  # contract-shape:bounded-change -- the declared mutation is the full
  # ordered 7-stage completion chain for the queued signal's item.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @consolidation-intake @contract-shape:bounded-change @covers-R19
  Scenario: A queued trunk-health signal flows through the same pipeline stages a bugfix defect does
    Given a fresh consolidation intake
    When a "stale-branch" signal for "feature/long-forgotten" is detected at minute 0
    And its queue item walks the rest of the shared pipeline to commit-slice starting at minute 1
    Then the queue item's ledger chain traces RCA, charter authoring, AT authoring, RED seal, crafter's GREEN pass, Vera's examine and commit-slice in order, backed by a commit-slice-verified record

  # ─────────────────────────────────────────────────────────────────────────
  # AT-20 -- RE-DETECTING THE SAME UNRESOLVED SIGNAL DOES NOT DUPLICATE ITS
  # QUEUE ITEM (CRITICAL negative, RED today). Charter Negative-2, verbatim:
  # "re-running a consolidation tick against an unresolved signal does not
  # silently duplicate the queue item."
  # contract-shape:unbounded-preservation -- the invariant preserved across
  # an unbounded number of re-detections is "still exactly one item."
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @consolidation-intake @negative @contract-shape:unbounded-preservation @covers-R20
  Scenario: Re-detecting the same unresolved signal does not duplicate its queue item
    Given a fresh consolidation intake
    When a "failing-gate" signal for "mypy" is detected at minute 0
    And the same "failing-gate" signal for "mypy" is detected again at minute 5
    Then sampled at minute 5, that signal still has exactly one queue item, not two

  # ─────────────────────────────────────────────────────────────────────────
  # AT-21 -- AN UNSUPPORTED SIGNAL TYPE IS REJECTED LOUDLY, NEVER SILENTLY
  # ABSENT FROM THE QUEUE (CRITICAL negative, D-8, RED today). Charter
  # Negative-1, verbatim: "no detected trunk-health signal is ever silently
  # absent from the queue."
  # contract-shape:bounded-change -- the declared mutation is the
  # ConsolidationSignalIntakeRejected record itself, proven as a positive
  # enforcement, not an absence check.
  #
  # EXTENDED (Vera EXAMINE FAIL, real-CLI-surface defect): the ledger record
  # alone was not enough -- `des consolidation-signal-tick --signal-type
  # INVALID_TYPE` exited 0 silently, even though the ledger correctly
  # carried the rejection. The crafter's fix (already landed) makes
  # `intake_signal` return a discriminated `IntakeResult` the CLI branches
  # on; this second Then line pins that fix as a regression guard, asserting
  # the CLI-FACING surface itself (exit code + emitted line), not merely the
  # ledger a caller might never read.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @consolidation-intake @negative @contract-shape:bounded-change @covers-R21
  Scenario: An unsupported signal type is rejected loudly, never silently absent
    Given a fresh consolidation intake
    When an unsupported "flaky-test" signal for "test_foo" is detected at minute 0
    Then sampled at minute 0, the intake was rejected with a named reason and no queue item was silently created
    And the CLI surface itself refuses loudly: nonzero exit code, output naming the unsupported type and the supported set

  # ─────────────────────────────────────────────────────────────────────────
  # AT-22 -- TWO DISTINCT INSTANCES OF THE SAME SIGNAL TYPE PRODUCE TWO
  # DISTINCT QUEUE ITEMS, NEVER COLLAPSED INTO ONE (CRITICAL negative, RED
  # today). Discriminator against a defect_id-derivation bug that ignores
  # `signal_key` and collides two unrelated stale branches into one item --
  # exactly the "collapse/interfere with each other" failure mode the
  # charter's "What to explore" names.
  # contract-shape:bounded-change -- the declared mutation is the set of 2
  # distinct PipelineStageStarted(rca) records this pair appends.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @consolidation-intake @negative @contract-shape:bounded-change @covers-R18
  Scenario: Two distinct stale branches produce two distinct queue items, never collapsed into one
    Given a fresh consolidation intake
    When a "stale-branch" signal for "feature/alpha-stale" is detected at minute 0
    And a "stale-branch" signal for "feature/beta-stale" is detected at minute 1
    Then sampled at minute 2, exactly 2 distinct queue items are observed, one per branch
