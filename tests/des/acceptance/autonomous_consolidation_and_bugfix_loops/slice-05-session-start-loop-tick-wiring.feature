@feature-autonomous-consolidation-and-bugfix-loops @slice-05
# Feature: A session starting fires every pending autonomous-loop tick,
#          fail-open. Resolves feature-delta `## Wave: DESIGN / [REF] Open
#          Questions` OQ-3 (DA-13): slices 02-04 shipped three correct,
#          ledger-safe driving ports (`des work-exhausted-tick` /
#          `des bugfix-pipeline-tick` / `des consolidation-signal-tick`) with
#          ZERO production callers -- "the loop" in this feature's own name
#          did not yet exist as autonomous code. Ale ratified closing this
#          gap by wiring them into `handle_session_start()` -- mirrors
#          slice-01's already-shipped SubagentStop pattern
#          (`_maybe_emit_stale_agent_closed`): extend an EXISTING lifecycle
#          hook trigger, never a new in-process daemon (`background-loops-
#          hybrid-c`'s already-ratified `iv-3` no-daemon invariant, shared by
#          sitting on the same lifecycle surface).
#
# ── DISTILL-INTERIM WIRING CONTRACT (row 7b advisory again -- no DESIGN
# decision fixes the per-tick parameter-sourcing question) ──
# Real state-detection (which queue-state, which defect transition, which
# trunk-health signal) is OUT OF SCOPE for this driving port -- the SAME
# carve-out slice-04 already established. SessionStart instead reads an
# EXPLICIT, ALREADY-DETECTED tick request per domain from an optional,
# minimal `.nwave/loop-tick-{domain}.json` file; absence is a safe no-op,
# presence dispatches DIRECTLY into the domain seam. Each of the three ticks
# is wrapped in its OWN fail-open try/except -- the EXACT contract every
# existing SessionStart trigger already follows -- so one tick's exception
# never blocks the other two or any pre-existing trigger, and the hook always
# returns 0. Full contract:
# tests/des/acceptance/autonomous_consolidation_and_bugfix_loops/steps/domain_types_slice_05.py
#
# ── D-8 EXTENDED: a failed tick ATTEMPT is still observable, never swallowed ──
# A request naming a KNOWN feature_id but missing a required field is
# LEDGER-ATTESTED (`*TickAttemptFailed`, reusing the already-generic
# append_work_exhausted_event / append_bugfix_pipeline_event write surfaces --
# D-8/DA-6 reuse, no new port method). A request with NO derivable feature_id
# fails open via a labeled `[nwave] ... error (fail-open)` stderr diagnostic
# ONLY (the SAME idiom `_adopt_prior_use_if_warranted` already uses) -- there
# is no feature ledger to target.
#
# ── DRIVING PORT (Mandate-13, invariant 1+2) ──
# The driving port is the REAL `handle_session_start` SessionStart hook,
# invoked over its JSON stdin protocol via the SAME faithful in-process
# driving-port pattern slice-01 uses for SubagentStop (`run_hook_in_process`).
# NEVER a direct `des.domain.*` / `des.cli.*` invocation in test bodies.
#
# ── THE TERMINAL ASSERTION (the load-bearing NEW behavior, RED today) ──
# `handle_session_start()` today reads NONE of the three
# `.nwave/loop-tick-*.json` files -- every scenario below therefore RED-fails
# for the right reason (the expected tick/failure/diagnostic never appears)
# until DELIVER grafts the three `_maybe_tick_*` wrapper calls.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + filesystem only (no git needed by this slice's SUT), cross-OS. The
# hook returns 0 unconditionally -- unchanged from every existing
# SessionStart trigger's fail-open contract.
#
# Universe (Mandate 8): {outcome.exit_code, outcome.ticked[domain],
# outcome.attempt_failed[domain], outcome.stderr_mentions_domain[domain]}.
# Internal fields (stdin/stdout/stderr capture buffers, the raw JSON request
# bytes, the raw ledger file path) NEVER appear.
#
# Layer 3/4 (real filesystem + real ledger JSONL + real hook invocation
# against tmp_path): example-only (Mandate 9 v2 -- @real-io => example-based,
# NOT PBT). Sad paths explicit (Mandate 11). No PBT machinery.
#
# Carpaccio ceiling: 5 counted scenarios (1 Scenario Outline collapses to
# ONE + 4 plain Scenarios), authored as a @coupled group bound by ONE
# contract -- the fail-open, independently-checked wiring of the three
# pending-tick requests.

Feature: A session starting fires every pending autonomous-loop tick, fail-open
  As an operator who armed a background loop and stepped away
  I want every pending loop-tick request left from a prior iteration to fire the moment my next session starts
  So that the loop actually ticks unattended instead of waiting on me to invoke each CLI by hand

  # ─────────────────────────────────────────────────────────────────────────
  # AT-23 -- ALL THREE PENDING TICKS FIRE TOGETHER (RED today, the leading
  # positive outcome). No new @walking_skeleton -- the feature's single WS
  # already lives on slice-01 (WS Strategy).
  # contract-shape:bounded-change -- three declared mutations, one per domain.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @loop-tick-wiring @contract-shape:bounded-change @covers-R22
  Scenario: Every pending loop-tick request fires exactly once when the session starts
    Given an operator has left a pending work-exhausted tick, a pending bugfix-pipeline tick, and a pending consolidation-signal tick from a prior loop iteration
    When the operator's session starts
    Then all three pending loop ticks fire exactly once
    And the session-start hook still returns success

  # ─────────────────────────────────────────────────────────────────────────
  # AT-24 -- EACH DOMAIN'S PRESENCE IS INDEPENDENT (RED today). Guards
  # against an all-or-nothing wiring bug: one domain's absence must never
  # suppress, and must never be required for, another domain's tick.
  # Scenario Outline collapses to ONE counted scenario; 3 Examples maximize
  # density over the domain axis.
  # contract-shape:bounded-change -- same declared mutation shape as AT-23,
  # proven in isolation per domain.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @loop-tick-wiring @contract-shape:bounded-change @covers-R23
  Scenario Outline: Only the one pending loop tick left behind fires, the others stay untouched
    Given an operator has left only <pending tick> from a prior loop iteration
    When the operator's session starts
    Then only <pending tick> fires
    And the session-start hook still returns success

    Examples:
      | pending tick                            |
      | the pending work-exhausted tick         |
      | the pending bugfix-pipeline tick        |
      | the pending consolidation-signal tick   |

  # ─────────────────────────────────────────────────────────────────────────
  # AT-25 -- NO PENDING TICKS, NO SPURIOUS WRITES (CRITICAL negative, RED
  # today until the wiring exists -- currently vacuously true because nothing
  # reads the request files at all, so this pins the baseline no-op safety
  # once DELIVER lands the wiring).
  # contract-shape:unbounded-preservation -- the ledger stays byte-for-byte
  # unchanged; no mutation at all.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @loop-tick-wiring @negative @contract-shape:unbounded-preservation @covers-R24
  Scenario: An operator with no pending loop ticks sees none fire
    Given an operator's prior loop iteration left no pending loop tick behind
    When the operator's session starts
    Then no loop tick fires
    And the session-start hook still returns success

  # ─────────────────────────────────────────────────────────────────────────
  # AT-26 -- A MALFORMED KNOWN-FEATURE REQUEST IS LEDGER-ATTESTED, NEVER
  # SILENT (CRITICAL negative, D-8, RED today). The other two pending ticks
  # must still fire -- the exception-isolation guarantee, proven together
  # with the honest-failure record rather than in a separate scenario.
  # contract-shape:bounded-change -- the failure record IS a declared,
  # bounded mutation.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @loop-tick-wiring @negative @contract-shape:bounded-change @covers-R25
  Scenario: A malformed pending tick honestly records its own failed attempt, without blocking the others
    Given an operator has left a pending work-exhausted tick, a pending bugfix-pipeline tick that is missing what it must do, and a pending consolidation-signal tick from a prior loop iteration
    When the operator's session starts
    Then the malformed bugfix-pipeline tick honestly records that its attempt failed, never silently
    And the other two pending loop ticks still fire
    And the session-start hook still returns success

  # ─────────────────────────────────────────────────────────────────────────
  # AT-27 -- A REQUEST WITH NO DERIVABLE FEATURE FAILS OPEN, NEVER CRASHES
  # (CRITICAL negative, D-8 boundary case, RED today). There is no feature
  # ledger to target, so the degrade is a labeled stderr diagnostic only --
  # distinguishable from AT-26's ledger-attested class.
  # contract-shape:bounded-change -- the OTHER two domains still mutate;
  # the nameless one mutates nothing (no ledger to target).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @loop-tick-wiring @negative @contract-shape:bounded-change @covers-R26
  Scenario: A pending tick with no feature named fails open to the terminal only, without blocking the others
    Given an operator has left a pending work-exhausted tick, a pending bugfix-pipeline tick, and a pending consolidation-signal tick with no feature named from a prior loop iteration
    When the operator's session starts
    Then the nameless consolidation-signal tick fails open silently to the operator's terminal only, with no attempt recorded
    And the other two pending loop ticks still fire
    And the session-start hook still returns success
