@feature-oss-spine-watchdog @slice-03
# Feature: The DES spine closes a re-fired-without-progress agent loud after a
#          timeout, instead of the operator discovering it stale by hand an hour
#          later.
# Slice: 03 — stale-agent timeout (#68 P2-E). DISCUSS D-3/D-5, Slice Plan row
#         slice-03; RCA root #68 (the 68-min stale-loop; RCA instance #2 = a
#         compaction-restarted agent waiting on a never-arriving background
#         notification). On a returning atdd_pure agent, the SubagentStop hook
#         computes the wall-clock gap between the agent's LAST PROGRESS SIGNAL
#         (the AT-completion ledger's most-recent record `timestamp` for this
#         `(feature_id, slice_id)`) and NOW. If the gap EXCEEDS the threshold
#         (DESIGN OQ-4: default 20 minutes) AND no `completed`/`blocked` terminal
#         record exists for the key, the hook emits `StaleAgentClosed` — a
#         terminating INDETERMINATE (a non-block return: exit 0, NO `decision:block`
#         body — DESIGN OQ-5 / D-3) that NAMES the staleness, plus a durable
#         `StaleAgentClosed` ledger record — instead of leaving the agent to hang.
#         A FRESH gap (within the threshold) or an ALREADY-TERMINAL agent is left
#         alone (DESIGN OQ-4 / G-3 — a legitimately-working or already-done agent
#         is never closed).
#
# THE SLICE VALUE (DISCUSS Slice Plan slice-03): "When a background agent is
# re-fired without progress past a timeout, the operator's spine closes it with a
# loud INDETERMINATE instead of the operator discovering it stale by hand an hour
# later."
#
# ── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess ──
# The driving port is the REAL `handle_subagent_stop` SubagentStop hook, invoked
# over its JSON stdin protocol AS A SUBPROCESS, exactly as the shipped, proven
# slice-02 sibling (`composition_slice_02.py`) drives the G_COMMIT exit gate:
#     python -c "... from ...subagent_stop_handler import handle_subagent_stop;
#                sys.exit(handle_subagent_stop())"
# A real git repo under tmp_path carries a returning atdd_pure agent's A_GREEN
# transcript (a generic re-fired return → the `_handle_atdd_pure_return` path the
# stale check grafts onto, DESIGN R-7). The agent's LAST PROGRESS ledger record is
# seeded as PRECONDITION substrate through the production `AtCompletionLedger`
# writer carrying an EXPLICIT timestamp (the F-13 producer-timestamp contract) so
# the stale gap is deterministic WITHOUT a real sleep — the S2 tolerable-variant.
# NEVER a direct `from des...subagent_stop_handler import _handle_atdd_pure_return`.
#
# ── THE CONTROLLABLE CLOCK (deterministic stale gap, NO real sleep) ──
# The progress signal is the ledger record `timestamp` (reuse-first, no new store,
# mirrors D-8). The AT seeds a STALE record timestamped 25 minutes ago and a FRESH
# record timestamped 2 minutes ago against the DESIGN OQ-4 default 20-minute
# threshold. The explicit timestamp is honoured by the writer (F-13), so the gap
# the hook computes is deterministic without any real wall-clock time passing.
#
# ── R1 config-SSOT surface NOT YET LANDED (the 20-min default residue) ──
# DESIGN OQ-4 / D-10: slice-03 reads the threshold from R1's `.nwave/config.yaml`
# control-plane. Confirmed empirically 2026-06-04: `.nwave/config.yaml` EXISTS but
# exposes only `workflow`/`atdd_pure`/`gate` keys — NO stale-threshold surface yet.
# So GREEN uses the hard-coded 20-minute default (DESIGN OQ-4) with a named R1
# residue. The seeded gaps (25 / 2 min) straddle the default independent of config.
#
# ── THE TERMINAL ASSERTION (the load-bearing NEW behavior, RED today) ──
# The generic atdd_pure return handler (`_handle_atdd_pure_return`,
# `subagent_stop_handler.py:1360-1420`) today does NOT read the ledger timestamps,
# does NOT compute a staleness gap, and has NO StaleAgentClosed emission — a
# returning atdd_pure agent gets the NORMAL return (allow, exit 0, no
# StaleAgentClosed record). So a STALE agent currently gets the same normal return
# as a fresh one. AT-01 asserts the stale agent is CLOSED (a StaleAgentClosed
# terminal: non-block, loud, durable record) — RED today (no close happens), GREEN
# once DELIVER grafts the timestamp-gap check + threshold + StaleAgentClosed
# emission into `_handle_atdd_pure_return` (DESIGN R-7). That is the slice-03
# feature debt this AT specifies.
#
# ── THE ANTI-VACUITY DISCRIMINATOR (DESIGN OQ-4 / G-3 guardrail, GREEN today) ──
# AT-02 (fresh gap) + AT-03 (already-terminal) are the no-false-positive guardrail:
# a check that ALWAYS closes a returning agent would wrongly close them; the current
# never-close handler passes them. Together with AT-01 (which the never-close
# handler fails) they bracket the contract: a closer that NEVER closes fails AT-01;
# one that ALWAYS closes fails AT-02/AT-03. AT-02 forces the threshold-comparison;
# AT-03 forces the no-existing-terminal precondition.
#
# ── Integration surface (Mandate-13 invariant 4) ──
# Every scenario crosses the REAL SubagentStop seam — a real git repo, a real
# ledger JSONL the timestamp read scans, and the real fresh-interpreter hook
# subprocess. No mock of the handler; isolated to tmp_path so it never touches the
# real repo or ledger.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + git + filesystem only (the hook resolves a real repo + reads a real
# ledger), cross-OS. The terminal is exit 0 with NO `{decision:block}` body
# (DESIGN OQ-5 / DEVOPS: the terminal is loud via stderr + ledger record, NEVER a
# non-zero exit — a non-zero-exit assertion would invert the contract and red CI).
#
# Universe (Mandate 8): {outcome.closed, outcome.names_staleness}. Internal fields
# (Popen handle, env dict, transcript bytes, raw ledger path) NEVER appear.
#
# Layer 3/4 (subprocess against tmp_path): example-only (Mandate 9 v2 — the driven
# set includes a real filesystem adapter + a real git subprocess + a real hook
# subprocess → @real-io → example-based, NOT PBT). Sad paths explicit (Mandate 11).
# No PBT machinery.
#
# Carpaccio ceiling = 3 ATs, authored as a @coupled group bound by ONE contract —
# the stale-agent terminal's decision (close on a stale gap with no existing
# terminal vs leave-alone a fresh or already-terminal agent) on its real
# driving-port surface.

Feature: The spine closes a re-fired-without-progress agent loud after a timeout
  As an operator running /nw-deliver on my own machine in the background
  I want a re-fired-without-progress agent to be closed loud once it goes stale past a timeout
  So that I learn it stalled from the spine's own terminal state, not by hunting it down by hand an hour later
  And an agent making fresh progress, or one that has already finished, is never closed prematurely

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — THE TERMINAL (the leading outcome, RED today). The agent's last
  # progress is older than the threshold (a 25-min-old seed against the 20-min
  # default) and no completed/blocked terminal exists for the key → the spine must
  # CLOSE the agent loud (a StaleAgentClosed terminating INDETERMINATE — no
  # {decision:block} — naming the staleness + a durable ledger record), instead of
  # leaving it to hang. North-Star KPI-1: zero silent stale-hangs. The never-close
  # handler (today) fails this scenario.
  # contract-shape:bounded-change — the stale gap changes the observable decision
  # from leave-alone to a bounded, named close (one declared mutation: a single
  # StaleAgentClosed terminal record appended for this key).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @stale-timeout @kpi @contract-shape:bounded-change
  Scenario: A returning agent gone stale past the timeout is closed loud instead of left to hang
    Given a returning agent whose last progress is older than the stale threshold
    When the spine evaluates the returning agent when the hook fires
    And the spine finishes evaluating the returning agent
    Then the spine closes the agent loud instead of leaving it to hang

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — FRESH PROGRESS NOT CLOSED (the threshold axis, GREEN today). DESIGN
  # OQ-4 / G-3 guardrail: "the watchdog MUST NOT close a legitimately-working
  # agent." The agent's last progress is recent (a 2-min-old seed, within the
  # 20-min threshold) → the gap does NOT exceed the threshold → the spine must
  # leave the agent alone (normal return, no StaleAgentClosed). Proves the close
  # fires only on a stale gap, never punishing fresh progress.
  # contract-shape:unbounded-preservation — a fresh-progress return leaves the
  # leave-alone behaviour unchanged (the agent and ledger are otherwise unchanged;
  # no premature close).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @no-false-positive @contract-shape:unbounded-preservation
  Scenario: A returning agent with fresh progress is left alone because it is still working
    Given a returning agent whose last progress is recent
    When the spine evaluates the returning agent when the hook fires
    And the spine finishes evaluating the returning agent
    Then the spine leaves the agent alone because its progress is fresh

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — ALREADY-TERMINAL NOT DOUBLE-CLOSED (the precondition axis, GREEN
  # today). DESIGN OQ-4: the close fires ONLY when no completed/blocked terminal
  # exists for the key. The agent's progress gap is large (a 25-min-old seed) BUT a
  # SliceCommitVerified terminal already exists for the key → the spine must NOT
  # emit StaleAgentClosed (don't close an already-terminal agent). The precondition
  # axis of the guardrail, distinct from AT-02's fresh-gap axis.
  # contract-shape:unbounded-preservation — an already-terminal agent leaves the
  # leave-alone behaviour unchanged (no double-close; the ledger is otherwise
  # unchanged).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-03 @no-false-positive @contract-shape:unbounded-preservation
  Scenario: A stale agent that has already reached a terminal state is left alone instead of double-closed
    Given a returning agent whose last progress is older than the stale threshold but has already reached a terminal state
    When the spine evaluates the returning agent when the hook fires
    And the spine finishes evaluating the returning agent
    Then the spine leaves the agent alone because it is already terminal
