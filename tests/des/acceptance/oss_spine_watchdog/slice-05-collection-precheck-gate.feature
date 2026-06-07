@feature-oss-spine-watchdog @slice-05
# Feature: A real collection crash on the live spine TERMINATES the G_COMMIT gate
#          with a loud durable terminal instead of re-firing the crafter —
#          slice-01's collection precheck wired INTO the gate handler BEFORE E2.
# Slice: 05 — collection-precheck gate-wiring feature-end-fix. The LAST slice; it
#         closes BLOCKER-1 of the deep feature-end review (`a360758f`, 2026-06-05):
#         slice-01 shipped the collection-precheck PROBE (`run_contract_gate
#         --collect-only`, the worker-side `crashing_module` capture) but the
#         G_COMMIT exit-gate handler NEVER CALLS it. grep `collect-only|precheck` in
#         `_handle_g_commit_exit_gate` = 0. So on the LIVE spine a real collection
#         crash STILL flows into E2 → exit non-zero → the block branch →
#         `{decision:block}` → the harness RE-FIRES the crafter forever — the exact
#         #68 loop the walking-skeleton (slice-01) exists to kill is NOT killed on
#         the production hot path. "Walking-skeleton value half-delivered."
#
# THE SLICE VALUE (DISCUSS Slice Plan slice-05): "A real collection crash on the
# live spine TERMINATES the G_COMMIT gate with a loud named failure instead of
# re-firing — slice-01's collection precheck wired INTO the gate handler BEFORE E2."
# EXTEND `_handle_g_commit_exit_gate` (precheck `run_contract_gate --collect-only`
# call before E2 via `_run_gate_subprocess`, no-skip env D-7; exit-2 → terminal via
# the slice-04 shared helper `_emit_terminating_indeterminate`).
#
# ── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess (THE AT-tier fix) ──
# This is the EXACT defect BLOCKER-1 is about, so the AT-tier is load-bearing. The
# slice-01 ATs drove the `--collect-only` PROBE DIRECTLY (the wrong tier — they
# asserted the PROBE names a module, never that the GATE INVOKES the probe).
# Slice-05 drives the REAL `handle_subagent_stop` G_COMMIT exit-gate hook over its
# JSON stdin protocol AS A SUBPROCESS, exactly as the shipped, proven slice-02
# (`composition_slice_02.py`) + slice-04 (`composition_slice_04.py`) siblings drive it:
#     python -c "... from ...subagent_stop_handler import handle_subagent_stop;
#                sys.exit(handle_subagent_stop())"
# against a REAL git repo under tmp_path whose COMMITTED contract suite crashes on
# collection (a committed import-time-crashing test module, isolated to tmp_path —
# the SHAPE, not the BLAST RADIUS). The durable terminal record is observed by a
# RE-READ COUNT DELTA over the GENUINE-terminal records on the ledger (the slice-04
# observable pattern). NEVER a direct
# `from des...subagent_stop_handler import _handle_g_commit_exit_gate` at the test
# boundary.
#
# ── WHY THE TIER MATTERS (the crux BLOCKER-1 rejected on) ──
# The deep review rejected the feature because slice-01's ATs "validated the wrong
# thing" — they asserted the `--collect-only` probe names a module, never that the
# GATE INVOKES the probe. So the wiring was never specified by a test → the worker
# EXTEND shipped but the gate-call never did, and the #68 loop survives on the
# production hot path. Slice-05's ATs drive the REAL gate hook and assert the
# OBSERVABLE the DESIGN promises (a real collection crash TERMINATES the gate; a
# clean commit does NOT) — the right tier for the BLOCKER root.
#
# ── THE DIVERGENCE PAIR (the anti-vacuity discriminator, dispatch-required) ──
# AT-01/AT-02 (collection crash → terminate) vs AT-03 (collection-OK → gate proceeds
# to the ordinary block path). A precheck that NEVER fires the collection terminal
# fails AT-01/AT-02 (the crash re-fires); one that ALWAYS fires it (collection-blind)
# fails AT-03 (a clean commit is wrongly collection-terminated). The pair pins the
# terminal is keyed on a COLLECTION CRASH (exit 2), nothing else.
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python + git + filesystem only (the hook resolves a real repo + the real precheck
# collects a real synthetic suite + reads/writes a real ledger JSONL), cross-OS. The
# terminal is exit 0 with NO `{decision:block}` body (DESIGN OQ-5 / DEVOPS DV-5: loud
# via stderr + durable ledger record, NEVER a non-zero exit). The durable-record
# observable is a re-read count delta over the GENUINE-terminal event set (EXCLUDING
# the non-terminal `SliceCommitBlocked` re-fire record) — port-exposed observables,
# never internal fields.
#
# Universe (Mandate 8): {outcome.terminated, outcome.blocked}. Internal fields
# (Popen handle, env dict, transcript bytes, raw ledger path) NEVER appear.
#
# Layer 3/4 (subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io: the
# driven set includes a real filesystem adapter + a real git subprocess + a real
# collection-precheck subprocess + a real hook subprocess → example-based, NOT PBT).
# Sad paths explicit (Mandate 11). No PBT machinery.
#
# Carpaccio ceiling = 3 ATs, authored as a @coupled group bound by ONE contract — the
# collection-precheck-before-E2 wiring (DESIGN R-2): the gate terminates on a real
# collection crash (AT-01 durable record + AT-02 non-block) and does NOT over-fire on
# a clean-collecting commit (AT-03 discriminator).

Feature: A real collection crash terminates the commit gate instead of re-firing the crafter
  As an operator running /nw-deliver on my own machine in the background
  I want a real collection crash on the live spine to close the commit gate loud and terminating
  So that the crafter is not re-fired for an hour on a phantom hang the walking skeleton exists to kill

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — BLOCKER-1 (R-69-D): a real collection crash leaves a DURABLE terminal
  # (RED today). A returning crafter whose committed contract suite crashes on
  # collection: the gate must run the no-skip collection precheck BEFORE E2, detect
  # the exit-2 crash, and TERMINATE via the slice-04 shared
  # `_emit_terminating_indeterminate` — writing a durable terminal ledger record
  # (DDD-5 / DV-1), not a `SliceCommitBlocked` re-fire record. RED today: the gate
  # runs NO precheck (grep `collect-only|precheck` in the handler = 0); the crash
  # flows into E2 → the block branch → a `SliceCommitBlocked` re-fire record →
  # genuine-terminal count delta is 0 → `terminated` is False. GREEN once the
  # precheck-before-E2 wiring terminates the gate on exit 2.
  # contract-shape:bounded-change — the gate appends exactly one durable terminal
  # record for this collection-crashing commit; the outcome stays non-block.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @kpi @collection-crash @contract-shape:bounded-change
  Scenario: A collection crash closes the commit gate with a durable terminal
    Given a committed slice whose contract suite crashes on collection
    When the spine runs the commit exit gate on the returning crafter
    Then the spine closes the commit gate with a durable terminal instead of re-firing the crafter

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — BLOCKER-1 (R-69-D): the collection terminal is NON-block — no re-fire
  # (RED today). The load-bearing "loud → TERMINATING" half: a real collection crash
  # must make the gate return a NON-block body so the harness reaches a Stop, NOT
  # `{decision:block}` (which re-fires the crafter — the #68 loop). RED today: no
  # precheck → the crash re-blocks → `blocked` is True. GREEN once the precheck
  # short-circuits to the non-block terminal on exit 2. This is the earned-trust
  # probe that the wired precheck causes a Stop on a REAL crash, not just that the
  # probe names a module.
  # contract-shape:bounded-change — terminating the crash appends one durable
  # terminal record; the outcome stays non-block (the harness Stops, not re-fires).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @collection-crash @contract-shape:bounded-change
  Scenario: A collection crash terminates the commit gate without re-firing the crafter
    Given a committed slice whose contract suite crashes on collection
    When the spine runs the commit exit gate on the returning crafter
    Then the spine names the collection crash and does not re-fire the crafter

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — the anti-vacuity discriminator (collection-OK → ordinary block,
  # GREEN today). A returning crafter whose committed contract suite collects
  # cleanly but whose commit still fails the gate for an ORDINARY reason (no
  # `Gate-Scope:` trailer → E2 exit 1): the collection precheck sees exit 0 and lets
  # the gate proceed to the ORDINARY block path — it must NOT fire the collection
  # terminal. GREEN today (the ordinary block path is unchanged — no precheck) and
  # MUST STAY GREEN post-GREEN: a collection-blind precheck that terminated EVERY
  # commit would wrongly collection-terminate this clean commit. Pairs with AT-01/02
  # to bracket the contract: a precheck that NEVER terminates fails the crash pins; a
  # collection-blind one that ALWAYS terminates fails THIS pin.
  # contract-shape:unbounded-preservation — a clean-collecting commit leaves the
  # ordinary block behaviour unchanged (no collection terminal; the genuine-terminal
  # ledger record set is otherwise unchanged).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @discriminator @no-false-positive @contract-shape:unbounded-preservation
  Scenario: A cleanly-collecting commit is blocked the ordinary way without a collection terminal
    Given a committed slice whose contract suite collects cleanly but still fails the commit gate
    When the spine runs the commit exit gate on the returning crafter
    Then the spine blocks the commit gate without firing the collection terminal
