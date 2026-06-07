@feature-oss-spine-watchdog @slice-06
# Feature: A gate-subprocess TIMEOUT-originated re-fire loop on the same commit
#          terminates at N=3 like any other block — instead of looping unbounded
#          because the timeout-path block was UNCOUNTABLE.
# Slice: 06 — timeout-block countability feature-end-fix. Closes residue R-69-F of
#         the feature-end deep review (`a01511d9`): the G_COMMIT exit-gate handler's
#         `except subprocess.TimeoutExpired` path (`subagent_stop_handler.py:1047-1052`)
#         emits a FIELDLESS `SliceCommitBlocked` (no `pinned_commit_sha`, no
#         `block_reason`). The NORMAL block path (`:1036-1041`) emits it WITH
#         `pinned_commit_sha=pinned_sha` + `block_reason=failed`, so the bounded-block
#         count (`count_slice_commit_blocked`, keyed on `(slice_id, pinned_commit_sha,
#         block_reason)`) matches identical-key priors and terminates at N=3. The
#         TIMEOUT path's fieldless record can NEVER match that key → a
#         gate-subprocess-TIMEOUT-driven re-fire loop on the SAME commit is
#         UNCOUNTABLE → the slice-02 N=3 bound is DEFEATED for timeout-originated
#         blocks (backstopped only by slice-03's coarse stale-timeout).
#
# THE SLICE VALUE (DISCUSS Slice Plan slice-06): "A gate-subprocess TIMEOUT-
# originated re-fire loop on the same commit terminates at N=3 like any other block —
# instead of looping unbounded because the timeout-path block was uncountable."
# EXTEND the timeout-except emit (`:1048`) to thread `pinned_commit_sha=pinned_sha`
# (already resolved at `:933`) + `block_reason="gate-timeout"` — so identical timeout
# blocks on the same `(slice, sha, "gate-timeout")` key count toward N=3 and the
# bounded-block terminal fires on the 3rd.
#
# ── DRIVING PORT (Mandate-13, invariant 1+2): real forced-timeout hook subprocess ──
# The ATs drive the REAL `handle_subagent_stop` G_COMMIT exit-gate hook over its JSON
# stdin protocol AS A SUBPROCESS — exactly as the shipped, proven slice-02
# (`composition_slice_02.py`) + slice-05 (`composition_slice_05.py`) siblings drive
# it — against a REAL git repo under tmp_path, with the gate subprocess FORCED TO
# TIME OUT via the production timeout-fault seam `NWAVE_U2_FORCE_GATE_TIMEOUT=1` (the
# GREEN-added sibling of the existing `NWAVE_U2_FORCE_HANDLER_FAULT` test seam at
# `subagent_stop_handler.py:917`, already driven through the real hook subprocess by
# the `atdd_pure_spine_hardening` slice02/slice04 compositions). The seam raises a
# real `subprocess.TimeoutExpired` from inside the gate try-block → the REAL `except
# subprocess.TimeoutExpired` branch (the R-69-F defect site) fires DETERMINISTICALLY
# and FAST — NOT a 120s sleep (a real-timeout test against the 120s
# `G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS` constant would be too slow, and the
# constant has no env override; the fault seam is the realistic injection point the
# composition machinery supports). The durable terminal record is observed by a
# RE-READ COUNT DELTA over the GENUINE-terminal records on the ledger (the slice-04/05
# observable pattern). NEVER a direct
# `from des...subagent_stop_handler import _handle_g_commit_exit_gate` at the test
# boundary. `AtCompletionLedger` is imported ONLY to SEED the 2 prior `(slice, sha,
# "gate-timeout")` blocks + RE-READ the durable terminal record (the S2
# tolerable-variant — seed/observe through the production writer/reader).
#
# ── THE DIVERGENCE PAIR (the anti-vacuity discriminator, dispatch-required) ──
# AT-01 (3rd identical timeout → terminate) vs AT-02 (single timeout, no priors →
# ordinary block). A fix that NEVER counts the timeout block (today's fieldless emit)
# fails AT-01 (no terminal at the 3rd). A fix that ALWAYS terminates a timeout
# (count-blind) fails AT-02 (a first single timeout is wrongly terminated). The pair
# pins the terminal is keyed on the Nth identical `(slice, sha, "gate-timeout")`
# block, nothing else — exactly like an ordinary block.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + git + filesystem only (the hook resolves a real repo + seeds/reads a real
# ledger JSONL + the forced TimeoutExpired exercises the real except branch),
# cross-OS. The terminal is exit 0 with NO `{decision:block}` body (DESIGN OQ-5 /
# DV-5: loud via stderr + durable ledger record, NEVER a non-zero exit). The
# durable-record observable is a re-read count delta over the GENUINE-terminal event
# set (EXCLUDING the non-terminal `SliceCommitBlocked` re-fire record) — port-exposed
# observables, never internal fields.
#
# Universe (Mandate 8): {outcome.terminated, outcome.blocked}. Internal fields
# (Popen handle, env dict, transcript bytes, raw ledger path) NEVER appear.
#
# Layer 3/4 (forced-timeout subprocess against tmp_path): example-only (Mandate 9 v2 —
# @real-io: the driven set includes a real filesystem adapter + a real git subprocess
# + a real hook subprocess → example-based, NOT PBT). Sad paths explicit (Mandate 11).
# No PBT machinery.
#
# Carpaccio ceiling = 2 ATs (≤3), authored as a @coupled group bound by ONE contract —
# the timeout-block-countability fix (R-69-F): the gate terminates on the 3rd
# identical timeout (AT-01 durable record + non-block) and does NOT over-fire on a
# single timeout (AT-02 discriminator).

Feature: A timeout-driven re-fire loop terminates at N=3 like any other block
  As an operator running /nw-deliver on my own machine in the background
  I want a gate-subprocess timeout that keeps re-firing on the same commit to terminate at the N=3 bound
  So that a timeout-originated hang is bounded like any other block, not left to loop until the coarse stale-timeout

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — R-69-F: the 3rd identical timeout block leaves a DURABLE terminal
  # (RED today). Two prior `(slice, sha, "gate-timeout")` blocks are recorded; the
  # gate is then forced to time out a 3rd time on the SAME key. The bounded-block
  # terminal must fire — writing a durable `SliceCommitBlockedTerminal` (DDD-5 / DV-1,
  # the slice-04 shared `_emit_terminating_indeterminate`) and returning a NON-block
  # body so the harness reaches a Stop. RED today: the timeout emit is FIELDLESS, so
  # `count_slice_commit_blocked` (keyed on `(slice, sha, block_reason)`) never matches
  # the 2 seeded fielded priors → count 0 (< N-1=2) → no terminal → a {decision:block}
  # re-fire → `terminated` is False / `blocked` is True. GREEN once the timeout emit
  # threads `pinned_commit_sha` + `block_reason="gate-timeout"` → count==N-1=2 → the
  # bounded-block terminal fires.
  # contract-shape:bounded-change — the 3rd identical timeout appends exactly one
  # durable terminal record for this commit; the outcome stays non-block.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-06 @kpi @gate-timeout @contract-shape:bounded-change
  Scenario: A third identical gate-timeout closes the commit gate with a durable terminal
    Given two prior gate-timeout blocks are recorded for the slice and commit
    When the commit exit gate times out for the returning crafter
    Then the spine closes the timed-out commit gate with a durable terminal instead of re-firing the crafter

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — the anti-vacuity discriminator (single timeout → ordinary block,
  # GREEN today). A SINGLE gate timeout with NO priors recorded: the bounded-block
  # count is 0 (< N-1=2) → the gate must take the ORDINARY block path (a
  # {decision:block} re-fire), it must NOT fire the bounded-block terminal. GREEN
  # today (the fieldless emit re-blocks anyway) and MUST STAY GREEN post-GREEN: the
  # fielded emit still has count 0 for a first timeout → ordinary block. A count-blind
  # fix that terminated EVERY timeout would wrongly terminate this single timeout.
  # Pairs with AT-01 to bracket the contract: a fix that NEVER counts the timeout
  # block fails the 3rd-timeout terminal pin; a count-blind one that ALWAYS terminates
  # fails THIS pin.
  # contract-shape:unbounded-preservation — a single timeout with no priors leaves the
  # ordinary block behaviour unchanged (no bounded-block terminal; the
  # genuine-terminal ledger record set is otherwise unchanged).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-06 @discriminator @no-false-positive @contract-shape:unbounded-preservation
  Scenario: A single gate-timeout is re-fired the ordinary way without a terminal
    Given no prior gate-timeout block is recorded for the slice and commit
    When the commit exit gate times out for the returning crafter
    Then the spine re-fires the crafter because a single timeout does not terminate
