@feature-fix-freshness-gate-dev-checkout-autoskip @slice-01 @walking_skeleton
# Feature: DES freshness gate auto-skips when invoked from a developer git checkout
# Story: dogfood friction #16 closure (F-FRESHNESS-GATE-BLOCKS-DEV-SPINE)
# Slice: 01 — the entire bugfix in one carpaccio slice (slice cap 3 ATs).
#         AT-01: walking skeleton (dev checkout → auto-skip PROCEED).
#         AT-02: regression pin (customer install → DEGRADED REFUSE preserved).
#         AT-03: audit-trail (auto-skip emits a NEW structured event distinct
#                from the existing operator-set NWAVE_FRESHNESS=skip event).
#
# RCA SOURCE: docs/backlog.md friction #16 (autonomous night 2026-05-24). The
# `des` CLI dispatcher refuses every invocation with DEGRADED + "no install
# manifest — reinstall required" whenever the installed copy at
# `~/.claude/lib/python/des/` is out of sync with repo `src/des/`. Dev workflow
# makes this constant (every src edit invalidates the manifest). Operator pays
# `NWAVE_FRESHNESS=skip` ceremony on every CLI invocation. Fix: auto-skip when
# invoked from a checkout (CWD `.git/` adjacency).
#
# State machine the gate enforces (§1.3 four-state truth table, inherited from
# F-DES-SELF-HOSTED-GATE-SYNC, UNCHANGED):
#   (no install manifest) ------------> DEGRADED → REFUSE, exit 78
#   (manifest, source unreachable) ---> A         → PROCEED, exit 0 (silent)
#   (manifest, commit mismatch) ------> D         → REFUSE
#   (manifest, content match) --------> C         → PROCEED
#
# NEW short-circuit (THIS BUGFIX), fired BEFORE the four-state classification:
#   (CWD has `.git/` adjacency) ------> AUTOSKIP  → PROCEED, exit 0, audit
#                                        event `des.runtime.freshness.autoskipped`
#                                        on stderr (load-bearing audit evidence).
#
# Composition root (Pillar 3): every AT spawns `python -c "import des.cli"`
# against a synthetic installed tree under tmp_path, with PYTHONPATH pointing
# at the synthetic tree and CWD set to a tmp_path-staged dev-checkout-shaped
# directory (a `.git/` subdir + a `src/des/` dir present). So the production
# composition root (`des.cli/__init__.py` → `assert_fresh_or_explain()`) runs
# end-to-end — only the filesystem witnesses are tmp-scoped.
#
# Universe per Mandate 8: {exit_code, verdict, stderr_event}. Internal fields
# (Popen handle, env dict, stdin file) NEVER appear.
#
# Layer 3 (subprocess against tmp_path): example-only (Mandate 9), sad paths
# explicit (Mandate 11). No PBT machinery.

Feature: The freshness gate auto-skips when invoked from a developer git checkout
  As a developer running `des` CLI from a local git checkout
  I want the gate to PROCEED without requiring `NWAVE_FRESHNESS=skip` ceremony
  So that every spine cycle, test run, and hook fire stops paying daily friction
  And the audit trail keeps "why did the gate not refuse" answerable post-hoc
  And customer installs (no checkout adjacency) preserve their fail-closed REFUSE

  @walking_skeleton @driving_port @real-io @slice-01 @dev-checkout @contract-shape:bounded-change
  Scenario: Operator running des CLI from a git checkout PROCEEDS without REFUSE
    Given a synthetic installed DES tree at the standard install path
    And the installed tree has no `_install_manifest.json`
    And the operator runs from a developer checkout with a `.git` directory present
    When the operator imports `des.cli` against that installed tree
    Then the freshness gate PROCEEDS the invocation with exit code 0
    And the gate emits a structured event `des.runtime.freshness.autoskipped`

  @driving_port @real-io @slice-01 @error @customer @contract-shape:unbounded-preservation
  Scenario: Customer install on a host with no git checkout still REFUSES on stale manifest
    Given a synthetic installed DES tree at the standard install path
    And the installed tree has no `_install_manifest.json`
    And the operator runs from a customer host with no checkout adjacency
    When the operator imports `des.cli` against that installed tree
    Then the freshness gate REFUSES the invocation with exit code 78
    And the gate emits a structured event `des.runtime.freshness.refused`

  @driving_port @real-io @slice-01 @adapter-integration @audit-trail @contract-shape:bounded-change
  Scenario: Auto-skip emits a structured event distinguishable from operator-set skip
    Given a synthetic installed DES tree at the standard install path
    And the installed tree has no `_install_manifest.json`
    And the operator runs from a developer checkout with a `.git` directory present
    When the operator imports `des.cli` against that installed tree
    Then the gate emits a structured event `des.runtime.freshness.autoskipped`
    And the gate does not emit a structured event `des.runtime.freshness.skipped`
