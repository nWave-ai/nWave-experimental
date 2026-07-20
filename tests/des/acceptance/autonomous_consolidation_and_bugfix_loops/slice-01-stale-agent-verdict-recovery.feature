@feature-autonomous-consolidation-and-bugfix-loops @slice-01
# Feature: A stale-closed agent recovers its own last-stated verdict, no
#          relay, no wait. Charter:
#          docs/product/expectations/autonomous-consolidation-and-bugfix-loops/
#          a-stale-closed-agent-recovers-its-own-verdict.md
# Slice: 01 (the WALKING SKELETON, feature-delta Slice Plan row slice-01,
#         Locked Decision D-1). D-5 REUSE: `StaleAgentClosed`
#         detection/closure is SHIPPED (oss-spine-watchdog,
#         `_maybe_emit_stale_agent_closed`) and is NOT rebuilt here. This
#         slice EXTENDS that trigger: on every `StaleAgentClosed` emission the
#         spine parses the closed agent's OWN transcript for its
#         last-stated verdict and writes a PAIRED recovery record to the
#         AT-completion ledger in the SAME tick -- so a `StaleAgentClosed`
#         record is NEVER orphaned (D-8).
#
# ── DISTILL-interim parsing contract (feature-delta Open Question 1 --
# no DESIGN wave ran for this feature; resolved here as the concrete,
# testable acceptance criteria DELIVER must implement) ──
# An ASSISTANT-role transcript message containing a line matching
# `VERDICT:\s*(PASS|FAIL|BLOCKED)` (case-insensitive) is a stated verdict.
# The recovery scans EVERY assistant message (not only the last one) and
# keeps the LAST (most recent) matching marker -- a verdict "buried under
# noise" (later tool-call / retry turns with no marker) must still resolve.
# No matching marker anywhere / zero assistant messages / unparseable
# assistant-turn content => UNRECOVERABLE, honestly recorded, NEVER a
# fabricated guess. Full contract:
# tests/des/acceptance/autonomous_consolidation_and_bugfix_loops/steps/domain_types_slice_01.py
#
# ── DRIVING PORT (Mandate-13, invariant 1+2) ──
# The driving port is the REAL `handle_subagent_stop` SubagentStop hook,
# invoked over its JSON stdin protocol via the SAME faithful in-process
# driving-port pattern the shipped oss-spine-watchdog slice-03 sibling uses
# (`run_hook_in_process` -- the sanctioned, behaviour-identical replacement
# for a forked `python -c "... handle_subagent_stop()"` subprocess). A real
# git repo under tmp_path carries a returning atdd_pure agent's A_GREEN
# transcript. NEVER a direct
# `from des...subagent_stop_handler import _maybe_emit_stale_agent_closed`
# invocation in test bodies.
#
# ── THE TERMINAL ASSERTION (the load-bearing NEW behavior, RED today) ──
# The shipped `_maybe_emit_stale_agent_closed` closes a stale, no-terminal
# agent (GREEN today -- D-5 reuse) but does NOT parse the closed agent's
# transcript, does NOT write any recovery record, and has NO
# `StaleAgentVerdictRecovered`/`StaleAgentVerdictUnrecoverable` emission
# today -- so a `StaleAgentClosed` record is currently ALWAYS orphaned. Every
# scenario below asserts BOTH halves: the close (already GREEN) AND the
# paired recovery (RED today, the slice-01 feature debt this AT specifies).
#
# ── THE NO-ORPHAN INVARIANT (D-8, asserted alongside EVERY scenario) ──
# "the spine ... pairs it, same tick, with ..." is the SAME shared assertion
# in every positive AND every honest-failure Then step -- proving the
# `StaleAgentClosed`-with-no-recovery-record class never occurs, rather than
# isolating it into one separate scenario the other scenarios could then
# quietly violate.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + git + filesystem only (the hook resolves a real repo + reads a
# real ledger JSONL, as in production), cross-OS. The terminal stays exit 0
# with NO `{decision:block}` body -- unchanged from the shipped stale-close
# contract.
#
# Universe (Mandate 8): {outcome.closed, outcome.paired_recovery,
# outcome.recovered, outcome.recovered_verdict, outcome.unrecoverable_reason,
# outcome.distinguishable, outcome.durable_on_reread,
# outcome.new_record_count}. Internal fields (Popen handle, env dict, raw
# transcript bytes, raw ledger path) NEVER appear.
#
# Layer 3/4 (real git repo + real ledger JSONL + real hook invocation
# against tmp_path): example-only (Mandate 9 v2 -- the driven set includes a
# real filesystem adapter + a real git subprocess + a real hook invocation
# => @real-io => example-based, NOT PBT). Sad paths explicit (Mandate 11).
# No PBT machinery. Parametrize density via Scenario Outline over the
# transcript-state space (clear-PASS / clear-FAIL / buried-under-noise /
# ambiguous / empty / corrupted), per the max-PBT-density mandate applied at
# its layer-appropriate mechanism.
#
# Carpaccio ceiling: 4 counted scenarios (2 Scenario Outlines each collapse
# to ONE parsed scenario + 2 plain Scenarios), authored as a @coupled group
# bound by ONE contract -- the paired-recovery record on the shared,
# shipped close terminal.

Feature: A stale-closed agent recovers its own last-stated verdict, no relay, no wait
  As an operator who armed a background loop and stepped away
  I want the spine to recover a stale-closed agent's own last-stated verdict from its transcript, same tick
  So that I never wait on a relay that never arrives, and a StaleAgentClosed record is never an orphaned mystery

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 -- THE WALKING SKELETON (the leading outcome, RED today). The
  # feature's SINGLE @walking_skeleton scenario (feature-delta WS Strategy):
  # a stale-closed agent whose transcript clearly states a verdict is
  # recovered end-to-end through the real, installed hook -- proving the
  # artifact is wired, not just the recovery logic in isolation. Litmus: a
  # non-technical operator reads "the spine told me exactly what happened
  # without me having to dig."
  # contract-shape:bounded-change -- one declared mutation: a single paired
  # recovery record appended alongside the close, for this key.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @walking_skeleton @slice-01 @stale-verdict-recovery @kpi @contract-shape:bounded-change @covers-R1 @covers-R2
  Scenario: A stale-closed agent's own transcript recovers its last verdict by default, no relay, no wait
    Given a stale-closed agent whose transcript clearly stated a PASS verdict before going quiet
    When the spine evaluates the returning agent when the hook fires
    And the spine finishes evaluating the returning agent
    Then the spine closes the agent loud and pairs it, same tick, with a recovered verdict of "PASS"
    And the recovered verdict is durable and marked transcript-recovered, not agent-reported

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 -- VERDICT CONTENT CORRECTNESS (RED today). The recovered verdict
  # must match what the agent actually stated -- PASS, FAIL, and a verdict
  # "buried under noise" (stated early, then more assistant turns with no
  # marker follow -- charter "What to explore"). Scenario Outline collapses
  # to ONE counted scenario (carpaccio); 3 Examples maximize density.
  # contract-shape:bounded-change -- same declared mutation as AT-01, proven
  # across the transcript-content axis.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @stale-verdict-recovery @contract-shape:bounded-change @covers-R1 @covers-R2
  Scenario Outline: A stale-closed agent's clearly-stated verdict is recovered and durably recorded, same tick
    Given a stale-closed agent whose transcript <transcript_state>
    When the spine evaluates the returning agent when the hook fires
    And the spine finishes evaluating the returning agent
    Then the spine closes the agent loud and pairs it, same tick, with a recovered verdict of "<expected_verdict>"
    And the recovered verdict is durable and marked transcript-recovered, not agent-reported

    Examples:
      | transcript_state                                  | expected_verdict |
      | clearly stated a PASS verdict before going quiet   | PASS             |
      | clearly stated a FAIL verdict before going quiet   | FAIL             |
      | stated a verdict buried under later noise          | PASS             |

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 -- HONEST NON-RECOVERY, NEVER A FABRICATED VERDICT (CRITICAL
  # negative, RED today). D-8 negative-oracle: an ambiguous, empty, or
  # corrupted transcript must record an HONEST "could not recover a
  # verdict" -- never guess. Scenario Outline collapses to ONE counted
  # scenario; 3 Examples cover the unreadable/ambiguous axis.
  # contract-shape:bounded-change -- the declared mutation is the honest
  # StaleAgentVerdictUnrecoverable record, distinct from a fabricated guess.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @stale-verdict-recovery @negative @contract-shape:bounded-change @covers-R1 @covers-R3
  Scenario Outline: An unreadable or ambiguous transcript records an honest recovery-failed outcome, never a guess
    Given a stale-closed agent whose transcript <transcript_state>
    When the spine evaluates the returning agent when the hook fires
    And the spine finishes evaluating the returning agent
    Then the spine closes the agent loud and pairs it, same tick, with an honest could-not-recover record
    And no fabricated verdict is ever recorded for this agent

    Examples:
      | transcript_state                        |
      | carries no recognizable verdict marker  |
      | is empty                                |
      | is corrupted and unreadable             |

  # ─────────────────────────────────────────────────────────────────────────
  # AT-04 -- NO DOUBLE-WRITE ON RE-ARM (CRITICAL negative, GREEN-adjacent
  # today for the close half via the shipped no-double-close precondition;
  # RED today for the recovery half -- a naive recovery graft with no
  # precondition check would double-write on every re-fire). Charter "What
  # to explore": "does a second stale-close attempt double-write or
  # correctly no-op?"
  # contract-shape:unbounded-preservation -- a re-fire against an
  # already-closed, already-recovered agent leaves the ledger byte-for-byte
  # unchanged; no new mutation at all.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @stale-verdict-recovery @no-double-close @negative @contract-shape:unbounded-preservation @covers-R4 @covers-R5
  Scenario: Re-arming an already-closed agent never double-writes a recovery record
    Given a stale-closed agent whose transcript clearly stated a PASS verdict before going quiet
    And the spine has already closed and recovered this agent once
    When the spine evaluates the returning agent again when the hook re-fires
    Then the spine leaves the ledger byte-for-byte unchanged because the agent is already closed and recovered
