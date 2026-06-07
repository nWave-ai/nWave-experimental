@feature-oss-spine-watchdog @slice-02
# Feature: The DES spine terminates a persistently-blocked agent within N=3
#          identical blocks instead of re-firing it forever.
# Slice: 02 — bounded-block terminal N=3 (#68 P1-A). DISCUSS D-3/D-4, Slice Plan
#         row slice-02; RCA root #68 (the 68-min stale-loop; ledger seq 5,7-16 =
#         11 identical blocks for one (slice, sha) key). On a returning atdd_pure
#         crafter whose commit fails an exit gate, the G_COMMIT intercept emits a
#         `SliceCommitBlocked` + `{decision:block}` today UNCONDITIONALLY — which
#         Claude Code re-fires forever (no max-attempts). Slice-02: before
#         re-emitting the block, count prior identical `SliceCommitBlocked` records
#         for `(slice_id, pinned_commit_sha)` from the ledger (D-8); on the 3rd
#         identical block emit a terminating INDETERMINATE (a non-block return:
#         exit 0, NO `decision:block` body — DESIGN OQ-5 / D-3) that NAMES the
#         bounded-block reason, instead of another `{decision:block}`. A new SHA or
#         a different block reason RESETS the count (D-4 — genuine progress is
#         never punished).
#
# THE SLICE VALUE (DISCUSS Slice Plan slice-02): "After 3 identical exit-gate
# blocks for the same slice and commit, the agent terminates with a loud
# INDETERMINATE instead of re-firing forever."
#
# ── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess ──
# The driving port is the REAL `handle_subagent_stop` SubagentStop hook, invoked
# over its JSON stdin protocol AS A SUBPROCESS, exactly as the shipped, proven
# sibling drives the G_COMMIT exit gate
# (`tests/des/acceptance/atdd_pure_spine_hardening/steps/slice02_composition.py`)
# and as THIS feature's slice-01 sibling proves the real-hook port is reachable:
#     python -c "... from ...subagent_stop_handler import handle_subagent_stop;
#                sys.exit(handle_subagent_stop())"
# A real git repo under tmp_path carries an E1-incomplete HEAD commit (the slice's
# `.feature` AT authored on disk but kept OUT of the commit) so the intercept
# reaches its `SliceCommitBlocked` block branch. The SUT is the REAL intercept;
# prior `SliceCommitBlocked` records are seeded as PRECONDITION substrate through
# the production `AtCompletionLedger` writer (the S2 tolerable-variant). NEVER a
# direct `from des...subagent_stop_handler import _handle_g_commit_exit_gate`.
#
# ── THE TERMINAL ASSERTION (the load-bearing NEW behavior, RED today) ──
# The block branch (`subagent_stop_handler.py:672-678`) re-emits SliceCommitBlocked
# + `{decision:block}` UNCONDITIONALLY today — it never counts prior blocks, never
# switches to a terminating INDETERMINATE; `_emit_g_commit_ledger_event` writes the
# blocked record WITHOUT a `pinned_commit_sha` field; there is NO
# `count_slice_commit_blocked(slice_id, pinned_commit_sha)` query. So the 3rd
# identical block STILL `{decision:block}`s today. AT-01 asserts the 3rd identical
# block TERMINATES (no `decision:block`) AND the diagnostic NAMES the bound — RED
# today (the gate still blocks), GREEN once DELIVER threads `pinned_commit_sha`
# (DDD-2a), adds the count query (DDD-2b), and switches the block branch on the Nth
# identical block (R-6). That is the slice-02 feature debt this AT specifies.
#
# ── THE ANTI-VACUITY DISCRIMINATOR (DISCUSS D-4 guardrail, GREEN today) ──
# AT-02 (new SHA) + AT-03 (different reason) are the progress-resets guardrail: a
# gate that ALWAYS terminates at the 3rd block REGARDLESS of key would wrongly
# terminate them; the current always-block gate passes them. Together with AT-01
# (which the always-block gate fails) they bracket the contract: a gate that NEVER
# terminates fails AT-01; a gate that terminates on ANY 3rd block fails AT-02/AT-03.
#
# ── Integration surface (Mandate-13 invariant 4) ──
# Every scenario crosses the REAL intercept seam — a real git repo with a real
# `git rev-parse HEAD` the handler pins, a real ledger JSONL the count reads, and
# the real fresh-interpreter hook subprocess. No mock of the intercept; isolated to
# tmp_path so it never touches the real repo or ledger.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + git + filesystem only (the hook pins a real HEAD SHA via git, as in
# production), cross-OS. The terminal is exit 0 with NO `{decision:block}` body
# (DESIGN OQ-5 / DEVOPS: the terminal is loud via stderr + ledger, NEVER a non-zero
# exit — a non-zero-exit assertion would invert the contract and red CI).
#
# Universe (Mandate 8): {outcome.blocked, outcome.names_bound}. Internal fields
# (Popen handle, env dict, transcript bytes, raw ledger path) NEVER appear.
#
# Layer 3/4 (subprocess against tmp_path): example-only (Mandate 9 v2 — the driven
# set includes a real filesystem adapter + a real git subprocess + a real hook
# subprocess → @real-io → example-based, NOT PBT). Sad paths explicit (Mandate 11).
# No PBT machinery.
#
# Carpaccio ceiling = 3 ATs, authored as a @coupled group bound by ONE contract —
# the bounded-block terminal's decision (terminate on the 3rd IDENTICAL block vs
# re-fire on genuine progress) on its real driving-port surface.

Feature: The spine terminates a persistently-blocked agent within three identical blocks
  As an operator running /nw-deliver on my own machine in the background
  I want a persistently-blocked commit to terminate the agent loud after three identical blocks
  So that I get one actionable failure instead of an hour-long silent re-fire loop
  And an agent making genuine progress is never terminated prematurely (a new commit, or a different failure, resets the count)

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — THE TERMINAL (the leading outcome, RED today). Two prior identical
  # blocks for (slice, sha-X); the 3rd identical block must TERMINATE the agent
  # loud (a terminating INDETERMINATE — no {decision:block}) naming the bound,
  # instead of re-firing it. Journey row 2: count ≤ 3 then a terminating
  # INDETERMINATE. The always-block gate (today) fails this scenario.
  # contract-shape:bounded-change — the 3rd identical block changes the observable
  # decision from re-fire to a bounded, named terminal (one declared mutation).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @bounded-block @kpi @contract-shape:bounded-change
  Scenario: A third identical block terminates the agent loud instead of re-firing it
    Given two prior identical exit-gate blocks are recorded for the slice and commit
    When the spine evaluates the next exit-gate block for the same slice
    Then the spine terminates the agent loud instead of re-firing it

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — PROGRESS RESETS, NEW SHA (anti-premature-termination, GREEN today).
  # DISCUSS D-4 Anxiety: "will a watchdog terminate my agent prematurely while it's
  # legitimately working through a hard fix?" Two prior identical blocks for
  # (slice, sha-X); the agent AMENDS its commit (a new HEAD SHA) → a fresh count
  # key starting at 0 → the spine must still re-fire (NOT terminate). Proves the
  # terminal fires only on 3 IDENTICAL blocks, never punishing genuine progress.
  # contract-shape:unbounded-preservation — a progress-bearing block leaves the
  # re-fire behaviour unchanged (the bound preserved, no premature termination).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @progress-resets @contract-shape:unbounded-preservation
  Scenario: A block for a newly amended commit re-fires the agent because progress reset the count
    Given two prior exit-gate blocks are recorded then the next block arrives for a newly amended commit
    When the spine evaluates the arriving exit-gate block
    Then the spine re-fires the agent because genuine progress reset the count

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — PROGRESS RESETS, DIFFERENT REASON (the reason axis, GREEN today).
  # DISCUSS D-4: "a different block reason resets the count." Two prior blocks for
  # the SAME (slice, sha-X) but a DIFFERENT gate failure (the agent fixed E1, now
  # E2 fails); the incoming block's reason differs from the priors → the count of
  # IDENTICAL blocks is below the bound → the spine must still re-fire. The reason
  # axis of the reset guardrail, distinct from AT-02's SHA axis.
  # contract-shape:unbounded-preservation — a different-reason block leaves the
  # re-fire behaviour unchanged (the bound is per-reason, no premature termination).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-02 @progress-resets @contract-shape:unbounded-preservation
  Scenario: A block for a different gate failure re-fires the agent because the reason reset the count
    Given two prior exit-gate blocks are recorded then the next block arrives for a different gate failure
    When the spine evaluates the arriving exit-gate block
    Then the spine re-fires the agent because genuine progress reset the count
