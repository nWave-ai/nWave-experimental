@feature-oss-spine-watchdog @slice-01 @walking-skeleton
# Feature: The DES spine never silently re-fires an agent on a collection crash.
# Slice: 01 — collection-health precheck (the walking skeleton). DISCUSS D-5/D-6,
#         Slice Plan row slice-01; RCA root #68 (the 68-min stale-loop). Before
#         the G_COMMIT exit gate can `block` on E2 — which, on a pytest COLLECTION
#         crash, makes the harness re-fire the agent forever (no max-attempts) —
#         the spine runs a whole-tree contract-suite COLLECTION precheck. A
#         collection crash → a LOUD SINGLE failure that NAMES the broken module
#         (KPI-3), terminating; NOT a silent opaque re-fire.
#
# THE WALKING SKELETON (DISCUSS Slice Plan slice-01): "When the contract suite
# fails to collect, the operator gets a single loud failure naming the broken
# module instead of a silent hour-long re-fire loop." It attacks the loop's ROOT
# (a collection crash is what kept E2 failing) and is the thinnest end-to-end
# vertical: precheck runs → collection crash detected → operator reads
# `collection crashed: <module>` → no re-fire follows.
#
# ── DRIVING PORT (Mandate-13, invariant 1+2): Layer-3 subprocess ──
# The collection-health precheck is the contract gate's `--collect-only`
# collection probe (DESIGN OQ-1 RESOLVED: EXTEND `run_contract_gate
# --collect-only`), invoked exactly as the G_COMMIT exit-gate precheck (DESIGN
# R-2) invokes it:
#     python -m des.cli run-contract-gate --collect-only --print-digest --repo <p>
# The SUT is the REAL contract gate + its fresh-interpreter collection worker
# (`_collect_scope_worker.py`) collecting a synthetic project tree under tmp_path.
# NEVER `from des.cli.run_contract_gate import _collect_scope` invoked at the test
# boundary — the only production reference is the `des.cli` subprocess module path
# (the tolerable-variant of the S2 driving-port-only invariant).
#
# ── THE KPI-3 NAMED-MODULE ASSERTION (the load-bearing NEW behavior) ──
# Empirically (2026-06-01) the precheck ALREADY exit-2-detects a collection crash
# and ALREADY exit-0-passes a clean suite — those are the regression pins (AT-02).
# What does NOT exist yet (DESIGN R-1 "the ONE genuine gap, a bounded EXTEND"):
# the failure payload only carries `pytest collection exited 2` / `pytest_exit_code`
# — it does NOT NAME THE CRASHING MODULE. KPI-3 ("100% of collection crashes name
# a module") demands the precheck name the importable module whose import raised.
# AT-01 + AT-03 assert `crash_named=True` + `named_module=<the broken module>` —
# RED today (the name is absent), GREEN once DELIVER EXTENDs the worker to capture
# the failing collector's nodeid (`pytest_collectreport`) and thread it through.
# That is the slice-01 feature debt this AT specifies.
#
# ── THE ENV-PARITY EARNED-TRUST PROBE (DISCUSS D-7 / DEVOPS DV-4) ──
# AT-03 reproduces the RCA #68 P1-B masked-collection shape: even when the
# operator's env carries `NWAVE_FRESHNESS=skip` (the pipenv `.env` topology that
# masked the original regression), the precheck must STILL detect AND name the
# collection crash — because a COLLECTION crash is a pytest-collection failure,
# independent of the freshness gate. The masked run was the bug; the no-skip
# collection is the cure. This is the env-parity assertion the dispatch mandates.
#
# ── Integration surface (Mandate-13 invariant 4) ──
# Every scenario crosses the REAL collection seam — a real synthetic project tree
# with a REAL broken-import test module, collected by the REAL fresh-interpreter
# pytest worker. No mock of the probe; the crash is a genuine import-time
# ModuleNotFoundError on a real filesystem fixture, isolated to tmp_path so it
# never poisons the actual test tree (DEVOPS CI constraint: the SHAPE, not the
# BLAST RADIUS).
#
# ── Mechanical assertion (Mandate-13 invariant 5) ──
# Python-only, GIT-FREE (the synthetic project is a filesystem fixture, no `git`
# subprocess), cross-OS, language-agnostic. The COLLECTION RUNS NO-SKIP
# (NWAVE_FRESHNESS cleared in the precheck subprocess — the precheck's whole point
# is env-parity; the masked-collection was RCA #68 P1-B).
#
# Universe (Mandate 8): {outcome.exit_code, outcome.crash_named,
# outcome.named_module}. Internal fields (Popen handle, env dict, raw worker
# bytes, marker-line prefix) NEVER appear.
#
# Layer 3 (subprocess against tmp_path): example-only (Mandate 9 v2 — the driven
# set includes a REAL filesystem adapter + a REAL pytest subprocess → @real-io →
# example-based, NOT PBT). Sad paths explicit (Mandate 11). No PBT machinery.
#
# Carpaccio ceiling = 3 ATs, authored as a @coupled @walking-skeleton group: the
# three are bound by ONE contract — the collection-precheck's verdict on its real
# driving-port surface (crash-named vs clean-proceed vs crash-named-under-skip).

Feature: The spine collection-health precheck names a broken module instead of looping
  As an operator running /nw-deliver on my own machine in the background
  I want a contract-suite collection crash to produce one loud failure naming the broken module
  So that I fix the import in seconds instead of discovering a silent hour-long re-fire loop by hand
  And a cleanly-collecting suite proceeds to the commit gate untouched (no spurious loud failure)
  And the crash is named even when my environment carries the freshness opt-out (env-parity)

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — THE WALKING SKELETON + THE KPI-3 named-module assertion (RED today).
  # Constructs the #68 root topology (a contract test module with a broken import)
  # and asserts the precheck fails LOUD (exit 2) and NAMES the crashing module —
  # NOT merely that collection exited 2. This is the load-bearing scenario the
  # dispatch mandates: the named module is the KPI-3 NEW behavior (feature debt).
  # ─────────────────────────────────────────────────────────────────────────
  @walking-skeleton @coupled @driving_port @real-io @slice-01 @kpi @collection-crash @contract-shape:bounded-change
  Scenario: A contract suite that crashes on collection fails loud and names the broken module
    Given a project whose contract suite fails to collect because a test module has a broken import
    When the spine runs the collection-health precheck before the commit gate
    Then the precheck fails loud and names the broken module

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — THE DISCRIMINATOR / no-false-positive (regression pin, GREEN today).
  # A cleanly-collecting contract suite must PROCEED the precheck (exit 0 with a
  # printed gate-scope digest) — NO spurious loud failure, the gate runs normally
  # and the agent is NOT re-fired. This proves the precheck distinguishes a
  # genuine collection crash from a healthy suite (the guardrail: the watchdog
  # MUST NOT add a hard-halt to a passing commit, DISCUSS D-3 / KPI guardrail G-2).
  # contract-shape:unbounded-preservation — the clean precheck observes the suite
  # and proceeds WITHOUT modifying anything (collection-only, no test side effects,
  # no re-fire).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @discriminator @contract-shape:unbounded-preservation
  Scenario: A cleanly-collecting contract suite proceeds to the commit gate with no loud failure
    Given a project whose contract suite collects cleanly
    When the spine runs the collection-health precheck before the commit gate
    Then the commit gate proceeds with no loud failure
    And the spine proceeds to the commit gate without re-firing the agent

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — THE ENV-PARITY EARNED-TRUST PROBE (RED today, DISCUSS D-7 / DV-4).
  # Reproduces the RCA #68 P1-B masked-collection shape: the operator's env carries
  # the freshness opt-out (NWAVE_FRESHNESS=skip, the pipenv `.env` topology that
  # masked the original regression). The precheck must STILL fail loud AND name the
  # crashing module — a COLLECTION crash is a pytest-collection failure, independent
  # of the freshness gate, so the skip mask must NOT hide it. Same crash topology as
  # AT-01; pins that the named-module behavior survives the env-parity condition.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @env-parity @collection-crash @contract-shape:bounded-change
  Scenario: A collection crash is named loud even when the operator has set the freshness opt-out
    Given a project whose contract suite fails to collect because a test module has a broken import
    And the operator runs with the freshness opt-out set in the environment
    When the spine runs the collection-health precheck before the commit gate
    Then the precheck fails loud and names the broken module
