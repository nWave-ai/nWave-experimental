@feature-oss-spine-watchdog @slice-04
# Feature: The 3 watchdog terminals emit the SAME durable terminating-INDETERMINATE
#          shape, so the bounded-block terminal leaves a durable ledger record and
#          the stale-check keys its no-double-close precondition on GENUINE
#          terminals, not the non-terminal re-fire record.
# Slice: 04 — terminal-coherence feature-end-fix. The deep feature-end review
#         (`a360758f`, 2026-06-05 — the once-per-feature cross-slice keystone)
#         REJECTED the coherent feature: the 3 prior slices each ship correctly
#         INDIVIDUALLY (own ATs green + exit-gate verified), but the DDD-5
#         terminating-INDETERMINATE wire-format (non-block + loud stderr + DURABLE
#         ledger record) was realized INCONSISTENTLY across the 3 terminals. The
#         per-slice AT-reviews validated each slice in ISOLATION and so could not
#         catch the cross-slice incoherence. Slice-04 EXTRACTs one shared
#         `_emit_terminating_indeterminate(event, reason)` (durable ledger record +
#         loud stderr + DV-2 audit KPI event) so every terminal honours DDD-5,
#         closing the two surviving cross-slice blockers.
#
# THE SLICE VALUE (DISCUSS Slice Plan slice-04): "The 3 watchdog terminals
# (collection-crash, bounded-block, stale) all emit the SAME durable terminating-
# INDETERMINATE shape via one shared helper — so the bounded-block terminal leaves a
# SliceCommitBlockedTerminal ledger record (KPI-2 measurable) and the stale-check
# keys its no-double-close precondition on GENUINE terminals, not the non-terminal
# re-fire record."
#
# ── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess ──
# The driving port is the REAL `handle_subagent_stop` SubagentStop hook, invoked
# over its JSON stdin protocol AS A SUBPROCESS, exactly as the shipped, proven
# slice-02 sibling (`composition_slice_02.py`, the G_COMMIT bounded-block terminal)
# and slice-03 sibling (`composition_slice_03.py`, the stale-agent check) drive it:
#     python -c "... from ...subagent_stop_handler import handle_subagent_stop;
#                sys.exit(handle_subagent_stop())"
# A real git repo under tmp_path; precondition records seeded through the production
# `AtCompletionLedger` writer (the S2 tolerable-variant); the durable terminal record
# observed by a RE-READ COUNT DELTA on the ledger (the slice-03 observable pattern).
# NEVER a direct `from des...subagent_stop_handler import _emit_bounded_block_terminal`
# (or `_maybe_emit_stale_agent_closed`) at the test boundary.
#
# ── WHY THE TIER MATTERS (the crux the feature-end review rejected on) ──
# The deep review rejected the feature because the per-slice ATs "validated the wrong
# thing" — slice-02's terminal AT asserted only the NON-BLOCK return (stderr-only),
# never the DURABLE RECORD; slice-03's no-double-close AT validated the precondition
# IN ISOLATION, never the CROSS-INVOCATION read where a historical block is mistaken
# for a terminal. Slice-04's ATs drive the REAL hook and assert the OBSERVABLE the
# DESIGN promises (the durable record IS written; the stuck agent IS closed / the
# done agent is NOT) — the right tier for the BLOCKER root.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + git + filesystem only (the hook resolves a real repo + reads/writes a real
# ledger JSONL), cross-OS. The terminal is exit 0 with NO `{decision:block}` body
# (DESIGN OQ-5 / DEVOPS: loud via stderr + ledger record, NEVER a non-zero exit). The
# durable-record observables are re-read count deltas on the ledger — port-exposed
# observables, never internal fields.
#
# Universe (Mandate 8): AT-01 {outcome.terminal_recorded, outcome.blocked}; AT-02
# {outcome.closed, outcome.blocked}. Internal fields (Popen handle, env dict,
# transcript bytes, raw ledger path) NEVER appear.
#
# Layer 3/4 (subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io: the
# driven set includes a real filesystem adapter + a real git subprocess + a real hook
# subprocess → example-based, NOT PBT). Sad paths explicit (Mandate 11). No PBT
# machinery.
#
# Carpaccio ceiling = 3 ATs, authored as a @coupled group bound by ONE contract — the
# DDD-5 terminating-INDETERMINATE wire-format (durable ledger record + non-block) made
# coherent across the bounded-block terminal (AT-01) and the cross-invocation
# stale-check (AT-02 + its anti-vacuity pin).
#
# DV-2 (R-69-C, named residue, NOT in scope): the WATCHDOG_* audit KPI event the
# shared helper also emits is NOT asserted here — there is no audit-KPI sink wired at
# the real-hook boundary yet, so observing it would test a scaffold of this slice's
# own design (theater). DV-2 is left as the named R-69-C residue; AT-01/AT-02 pin the
# two load-bearing blockers (BLOCKER-2 durable record, BLOCKER-3 cross-invocation key).

Feature: The watchdog terminals emit one coherent durable terminating-INDETERMINATE shape
  As an operator running /nw-deliver on my own machine in the background
  I want every watchdog terminal to leave the same durable, loud, non-block record
  So that the bounded-block terminal is measurable (KPI-2) and a later stale check never mistakes a re-fire block for a terminal and leaves a genuinely-stuck agent to hang

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — BLOCKER-2 (R-69-A): the bounded-block terminal writes a DURABLE record
  # (RED today). After 2 prior identical exit-gate blocks for the same slice and
  # commit, the third identical block fires the bounded-block terminal — which must
  # write a durable SliceCommitBlockedTerminal ledger record (DDD-5 / DV-1; KPI-2
  # "the 3rd block paired with a terminal record"), not merely fall non-block with a
  # stderr line. RED today: `_emit_bounded_block_terminal` is stderr-ONLY
  # (`subagent_stop_handler.py:518-541`, no `_append_record`); the re-read count
  # delta on SliceCommitBlockedTerminal is 0. GREEN once the terminal routes through
  # the shared `_emit_terminating_indeterminate` that writes the durable record.
  # contract-shape:bounded-change — the terminal appends exactly one
  # SliceCommitBlockedTerminal record for this (slice, pinned_commit_sha); the
  # outcome stays non-block.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @kpi @contract-shape:bounded-change
  Scenario: The third identical exit-gate block leaves a durable bounded-block terminal record
    Given two prior identical exit-gate blocks are recorded for the slice and commit
    When the spine evaluates the third identical exit-gate block for the same slice
    Then the spine writes a durable terminal record for the bounded-block terminal

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — BLOCKER-3 (R-69-B): the cross-invocation stale check keys on GENUINE
  # terminals (RED today). A returning agent gone stale whose only prior ledger
  # record is a regular SliceCommitBlocked — the NON-terminal re-fire record a
  # bounded-block-terminated agent leaves behind — must be CLOSED (StaleAgentClosed),
  # because a re-fire block is NOT a terminal. RED today:
  # `_EXISTING_TERMINAL_EVENTS = {SliceCommitVerified, SliceCommitBlocked}`
  # (`subagent_stop_handler.py:692`) treats the historical block as a terminal → the
  # stuck agent is wrongly left alone (the silent-hang false-negative). GREEN once
  # `_EXISTING_TERMINAL_EVENTS` is re-keyed onto genuine terminals
  # {SliceCommitVerified, SliceCommitBlockedTerminal, StaleAgentClosed}.
  # contract-shape:bounded-change — closing the stuck agent appends exactly one
  # StaleAgentClosed record; the outcome stays non-block.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @kpi @contract-shape:bounded-change
  Scenario: A stale agent whose only prior record is a re-fire block is closed instead of left to hang
    Given a returning agent gone stale whose only prior record is a re-fire block, not a terminal
    When a later stale check evaluates the returning agent when the hook fires
    Then the spine closes the stuck agent because a re-fire block is not a terminal

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — the anti-vacuity pin (no-double-close PRESERVED, GREEN today). A
  # returning agent gone stale that has ALREADY reached a genuine completed terminal
  # (SliceCommitVerified) must NOT be re-closed — the no-double-close precondition is
  # preserved by the re-key, not dropped. GREEN today (SliceCommitVerified is a
  # terminal under both the current and re-keyed precondition) and MUST STAY GREEN
  # post-GREEN: a re-key that simply dropped the precondition (always-close on a stale
  # gap) would wrongly close here. Pairs with AT-02 to bracket the contract: a
  # precondition-blind closer fails AT-03; a precondition-too-wide one fails AT-02.
  # contract-shape:unbounded-preservation — an already-terminal agent leaves the
  # leave-alone behaviour unchanged (no double-close; the ledger is otherwise
  # unchanged).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-04 @no-false-positive @contract-shape:unbounded-preservation
  Scenario: A stale agent that has already reached a completed terminal is left alone instead of double-closed
    Given a returning agent gone stale that has already reached a completed terminal
    When a later stale check evaluates the returning agent when the hook fires
    Then the spine leaves the agent alone because it has already reached a terminal
