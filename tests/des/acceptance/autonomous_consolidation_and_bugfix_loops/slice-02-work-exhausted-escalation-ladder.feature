@feature-autonomous-consolidation-and-bugfix-loops @slice-02
# Feature: An exhausted loop stops instead of idle-holding. Charter:
#          docs/product/expectations/autonomous-consolidation-and-bugfix-loops/
#          an-exhausted-loop-stops-instead-of-idle-holding.md
# Slice: 02 (feature-delta Slice Plan row slice-02, Locked Decision D-2).
# The feature's SINGLE @walking_skeleton already lives on slice-01
# (feature-delta WS Strategy) -- every scenario below drives the real
# driving port IN-PROCESS (Architecture of Reference default), never
# subprocess-e2e.
#
# ── DISTILL-INTERIM QUEUE MODEL (feature-delta Open Question 2 -- no DESIGN
# wave ran for this feature; resolved here as the concrete, testable "safe-
# work tier" DELIVER must implement) ──
# A loop tick observes exactly ONE of 4 queue states: "is empty" / "is fully
# gated" / "has a freshly unblocked item" / "is ambiguous to parse". The
# first three are EXHAUSTED (a malformed/ambiguous read is deliberately
# treated as exhausted -- SAFE, never an indeterminate hang). Only "has a
# freshly unblocked item" is a non-exhausted, fresh-triggering condition --
# the ONLY state that can resolve an open window or resume a loop past its
# own STOP/ESCALATE. Full contract:
# tests/des/acceptance/autonomous_consolidation_and_bugfix_loops/steps/domain_types_slice_02.py
#
# ── DRIVING PORT (Mandate-13, invariant 1+2) ──
# The driving port is the REAL `des work-exhausted-tick` CLI entry
# (`des.cli.work_exhausted_tick.main`), driven IN-PROCESS via the shared
# `run_cli_in_process` helper -- NEVER a direct
# `from des.domain.work_exhausted_ladder import evaluate_and_record`
# invocation (that seam does not exist yet -- it is DELIVER's job to build).
#
# ── THE CONTROLLABLE CLOCK (deterministic, NO real sleep) ──
# Every tick supplies an explicit synthetic `--now` instant computed from a
# fixed base + a minute offset -- the entire ladder is walked in test-process
# time, never a real 45-minute wait.
#
# ── THE TERMINAL ASSERTION (the load-bearing NEW behavior, RED today) ──
# `des.cli.work_exhausted_tick.main` exists ONLY as a RED scaffold today: it
# parses its args, then lazily imports the not-yet-built
# `des.domain.work_exhausted_ladder` seam, catches the resulting
# `ModuleNotFoundError`, emits a named `LADDER_NOT_WIRED` line, and returns
# exit 2 WITHOUT ever touching the ledger. So every scenario below RED-fails
# for the right reason: the ledger is byte-for-byte silent no matter how many
# ticks fire, because nothing is wired yet.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + filesystem only, cross-OS. No git subprocess needed for this
# slice -- only the ledger + the injected clock.
#
# Universe (Mandate 8): {outcome.first_warning_fired,
# outcome.first_warning_within_ceiling, outcome.second_warning_fired,
# outcome.second_warning_within_ceiling, outcome.stop_escalate_fired,
# outcome.stop_escalate_within_ceiling, outcome.reason_named,
# outcome.window_resolved, outcome.ledger_proves_ladder_from_timestamps_alone,
# outcome.new_record_count}. Internal fields (Popen handle, argv list, raw
# ledger path) NEVER appear.
#
# Layer 3/4 (real filesystem + real ledger JSONL + real in-process CLI
# invocation against tmp_path): example-only (Mandate 9 v2 -- @real-io =>
# example-based, NOT PBT). Sad paths explicit (Mandate 11). No PBT machinery.
# Parametrize density via Scenario Outline over the time-ladder + tick-
# cadence space, per the max-PBT-density mandate applied at its
# layer-appropriate mechanism.
#
# Carpaccio ceiling: 6 counted scenarios (2 Scenario Outlines each collapse
# to ONE parsed scenario + 4 plain Scenarios), authored as a @coupled group
# bound by ONE contract -- the ratified 20/30/45-minute wall-clock ladder.
# 50% (3 of 6) are negative/error-path scenarios (AT-07/AT-09/AT-10),
# exceeding the 40%+ error-path target.

Feature: An exhausted loop stops instead of idle-holding
  As an operator who armed a background loop and stepped away
  I want an exhausted safe-work tier to escalate on a fixed wall-clock ladder
  So that I know within 20 minutes if the loop isn't working, and it never idle-holds past 45

  # ─────────────────────────────────────────────────────────────────────────
  # AT-05 -- LADDER THRESHOLDS FIRE AT OR BEFORE THEIR RATIFIED MINUTE
  # (RED today). The loop ticks roughly as often as the ladder itself moves
  # (one tick per checkpoint), proving each rung fires precisely at or before
  # its 20/30/45-minute ceiling -- never later. Scenario Outline collapses to
  # ONE counted scenario; 6 Examples sweep the full checkpoint progression.
  # contract-shape:bounded-change -- one declared mutation per ratified
  # threshold crossed, for this window.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @work-exhausted-ladder @contract-shape:bounded-change @covers-R6 @covers-R7
  Scenario Outline: The escalation ladder fires each rung at or before its ratified wall-clock threshold
    Given a loop whose queue is fully gated at minute 0
    When the loop ticks in turn at minutes "<tick_minutes>"
    Then the ladder has fired FIRST WARNING "<first_warning>", SECOND WARNING "<second_warning>" and STOP/ESCALATE "<stop_escalate>" by that tick

    Examples:
      | tick_minutes            | first_warning | second_warning | stop_escalate |
      | 19                      | no            | no              | no            |
      | 19,20                   | yes           | no              | no            |
      | 19,20,29                | yes           | no              | no            |
      | 19,20,29,30              | yes           | yes             | no            |
      | 19,20,29,30,44           | yes           | yes             | no            |
      | 19,20,29,30,44,45        | yes           | yes             | yes           |

  # ─────────────────────────────────────────────────────────────────────────
  # AT-06 -- WALL-CLOCK ANCHORING, NEVER TICK-COUNT ANCHORING (RED today).
  # D-2's own ratified correction: the SAME 45-minute ceiling must hold
  # whether the loop ticks every 5 minutes, every 23 minutes, or jumps
  # straight from 0 to 46 in ONE tick (the exact "2 consecutive ticks"
  # defect the ratified thresholds replace). Scenario Outline collapses to
  # ONE counted scenario; 3 Examples sweep the cadence axis.
  # contract-shape:bounded-change -- same declared mutation as AT-05, proven
  # invariant to tick cadence.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @work-exhausted-ladder @contract-shape:bounded-change @covers-R6 @covers-R8
  Scenario Outline: The escalation ladder's thresholds do not move with how often the loop ticks
    Given a loop whose queue is empty at minute 0
    When the loop ticks every <cadence_minutes> minutes until minute 46
    Then the ladder has fired FIRST WARNING, SECOND WARNING and STOP/ESCALATE by minute 46

    Examples:
      | cadence_minutes |
      | 5               |
      | 23              |
      | 46              |

  # ─────────────────────────────────────────────────────────────────────────
  # AT-07 -- THE LEDGER ALONE PROVES NO UNESCALATED OVERRUN (CRITICAL
  # negative, RED today). D-8/D-2 negative-oracle, verbatim: an observer
  # reading ONLY the ledger's own timestamps -- zero knowledge of the loop's
  # tick interval -- must be able to confirm no exhausted window ran past 45
  # minutes without a STOP/ESCALATE record.
  # contract-shape:bounded-change -- the declared mutation is the
  # STOP/ESCALATE record itself, proven timestamp-derivable.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @work-exhausted-ladder @negative @contract-shape:bounded-change @covers-R7 @covers-R9
  Scenario: An exhausted window that runs well past the ceiling always carries a timestamp-provable STOP/ESCALATE record
    Given a loop whose queue is fully gated at minute 0
    When the loop ticks in turn at minutes "20,30,50"
    Then the ledger alone proves no exhausted window ran past 45 minutes without a STOP/ESCALATE record

  # ─────────────────────────────────────────────────────────────────────────
  # AT-08 -- A WINDOW THAT RESOLVES BEFORE THE CEILING NEEDS NO
  # STOP/ESCALATE (RED today). Mirrors feature-delta Domain Example 2: gated
  # at minute 0, warnings at 20/30, a freshly-unblocked item arrives at 38 --
  # the loop correctly resumes instead of escalating past a threshold that
  # no longer applies.
  # contract-shape:bounded-change -- the declared mutation is the
  # WorkExhaustedWindowResolved record, in place of a STOP/ESCALATE.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @work-exhausted-ladder @contract-shape:bounded-change @covers-R6 @covers-R7
  Scenario: A window that resolves before the ceiling needs no STOP/ESCALATE record
    Given a loop whose queue is fully gated at minute 0
    When the loop ticks at minute 20, minute 30 and then a freshly unblocked item appears at minute 38
    Then the loop's window is resolved with no STOP/ESCALATE record ever fired

  # ─────────────────────────────────────────────────────────────────────────
  # AT-09 -- A MALFORMED QUEUE READ IS EXHAUSTED, NEVER AN INDETERMINATE
  # HANG (CRITICAL negative, RED today). Charter "What to explore": "Try
  # feeding it a queue that is ambiguous to read -- does it treat that as
  # exhausted (safe) or does it hang indeterminately, silently defeating the
  # ladder?"
  # contract-shape:bounded-change -- the same FIRST WARNING mutation as the
  # genuinely-empty case, proven across the malformed-input axis.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @work-exhausted-ladder @negative @contract-shape:bounded-change @covers-R6 @covers-R9
  Scenario: A malformed queue read is treated as exhausted, never as a silent indeterminate hang
    Given a loop whose queue is ambiguous to parse at minute 0
    When the loop ticks again at minute 21
    Then the ladder fires FIRST WARNING exactly as it would for a genuinely empty queue

  # ─────────────────────────────────────────────────────────────────────────
  # AT-10 -- NO QUIET UN-STOP (CRITICAL negative, RED today). Charter
  # negative: "a loop that has genuinely stopped/escalated does not silently
  # resume polling on its own without a fresh triggering condition ... a
  # 'stop' that quietly un-stops itself is the same failure mode in
  # disguise."
  # contract-shape:unbounded-preservation -- a stale exhausted re-tick after
  # STOP/ESCALATE leaves the ledger byte-for-byte unchanged; no new mutation
  # at all.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @work-exhausted-ladder @no-quiet-unstop @negative @contract-shape:unbounded-preservation @covers-R6 @covers-R10
  Scenario: A genuinely stopped loop never silently resumes without a fresh unblock trigger
    Given a loop whose queue is empty at minute 0
    And the loop has already escalated to STOP/ESCALATE by minute 45
    When the loop ticks again at minute 60 with the queue still empty
    Then the loop appends no new record because a stale re-poll is not a fresh trigger
