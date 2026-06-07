@feature-des-spine-control-plane-ssot @slice-01 @walking_skeleton
# Feature: The DES spine hook hot path catches stale installed code + names it LOUD
# Slice: 01 — hook-freshness wiring (the walking skeleton). Attacks friction #58
#         (a dev edits `src/des`, the installed `~/.claude/lib/python/des/` tree
#         drifts, and the PreToolUse/SubagentStop hooks silently enforce the OLD
#         tree → 2h/248k-token thrash). DISCUSS US-1, Slice Plan slice-01.
#
# THE WALKING SKELETON (DISCUSS Slice Plan row slice-01): "Operator sees a LOUD
# `install-freshness.stale` warning naming the digest mismatch when the spine
# runs stale installed code, and the session proceeds (degrade-loud)."
#
# Driving port (Mandate-13, invariant 1+2): the HOOK ENTRYPOINT IMPORT —
#   `python -c "import des.adapters.drivers.hooks.claude_code_hook_adapter"`
# i.e. the hook PROCESS STARTUP, exactly as the installed hook process imports
# the adapter at launch. DESIGN SYS-2 wires `assert_fresh_or_explain` into the
# hook adapter IMPORT (mirroring `des.cli/__init__.py`), so the freshness gate
# fires as an import-time side effect BEFORE any handler logic runs. Driven
# against a synthetic installed tree under tmp_path, with CWD set to a
# `.git/`-bearing project directory. Layer-3 subprocess / Layer-4 wiring_e2e:
# the SUT is the real installed hook process startup, NOT a domain function.
# NEVER `from des.runtime.freshness import ...` invoked at the test boundary.
#
# ── THE DV-2 "reaches-the-probe" REQUIREMENT (the load-bearing constraint) ──
# DESIGN Gap A wires the gate into the hook; but the `.git/`-adjacency AUTOSKIP
# (`freshness.py:122-138`) short-circuits BEFORE the probe in the EXACT #58
# topology (installed-tree drift on a project that has `.git/`). A naive AT that
# asserts only "the hook CALLS the gate" would PASS while the gate auto-skips and
# emits NOTHING — shipping a dead-wired walking skeleton ("shipped-the-call ≠
# reaches-the-probe"). DV-2 resolves this: the hook site passes
# `suppress_git_autoskip=True` so the probe RUNS despite the project `.git/`.
#
# THE WALKING-SKELETON SCENARIO BELOW (AT-01) CONSTRUCTS THE #58 TOPOLOGY AND
# ASSERTS THE LOUD `install-freshness.stale` WARNING IS ACTUALLY EMITTED — not
# merely that the gate was reached. That is the verify-the-instrument assertion.
#
# State machine the hook freshness gate enforces at the hook entrypoint (slice-01
# reachable states; B/C/config-drift land in later slices):
#   (installed tree == repo source) ----------> FRESH      → PROCEED exit 0, silent
#   (installed tree DRIFTED from repo source) -> STALE(#58) → PROCEED exit 0, LOUD
#                                                 `install-freshness.stale` warning
#   (customer host: source unreachable) -------> A         → PROCEED exit 0, silent
#                                                 (install fidelity unchanged)
#   (NWAVE_FRESHNESS=skip set) ----------------> SKIP       → PROCEED exit 0, skipped
#
# Degrade-loud contract (DISCUSS D1, DEVOPS DV-2/DV-4 — resolves DESIGN OQ#1):
# the HOOK degrades LOUD (warns + proceeds, exit 0). It NEVER hard-blocks the
# session (that would brick an in-flight agent on a false positive). The CLI keeps
# its exit-78 REFUSE; the hook path is degrade-loud. This is the verbatim
# resolution of the DESIGN-left-open "hook refuse vs degrade" question.
#
# Observable sink (Mandate-13 invariant 3, DEVOPS DV-5 dual-emit): the LOUD
# warning is observable on TWO surfaces — (a) a structured `install-freshness.stale`
# event on stderr (operator reads in-flow) AND (b) a persisted record in the
# JsonlAuditLogWriter SSOT (`audit-*.log` under the `AuditLogPathResolver` dir,
# read by JsonlAuditLogReader + the KPI-1 query path — the SINGLE existing audit
# sink, NOT a new `audit.jsonl` representation). AT-01 asserts stderr; AT-05
# asserts the persisted SSOT audit record (the KPI-1 substrate).
#
# Integration surface (Mandate-13 invariant 4): every scenario crosses the REAL
# installed-vs-repo seam — a real synthetic installed `des/` tree + a real drifted
# `src/des` source tree + the real freshness probe re-hashing the source. No mock
# of the probe; the drift is a genuine filesystem-content divergence.
#
# Mechanical assertion (Mandate-13 invariant 5): Python-only, GIT-FREE — the
# `.git/`-adjacency topology is constructed as a filesystem fixture (an empty
# `.git/` directory), NEVER by shelling out to `git`. Cross-OS, language-agnostic.
#
# Universe (Mandate 8): {exit_code, verdict, stderr_event, audit_records}. Internal
# fields (Popen handle, env dict, stdin bytes, manifest dict) NEVER appear.
#
# Layer 3/4 (subprocess against tmp_path): example-only (Mandate 9 v2 — the driven
# set includes a REAL filesystem adapter → @real-io → example-based, NOT PBT). Sad
# paths explicit (Mandate 11). No PBT machinery imported.

Feature: The spine hook hot path catches stale installed code and names it LOUD
  As a developer running a feature through the DES spine on my own machine
  I want a hook fire on a stale install to emit a LOUD, named freshness warning
  So that I reinstall before trusting a run instead of debugging a phantom for hours
  And the session still proceeds (a freshness miss must never brick me mid-flow)
  And a customer install with no checkout keeps proceeding silently (fidelity unchanged)

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — THE WALKING SKELETON + THE DV-2 "reaches-the-probe" assertion.
  # Constructs the #58 topology (installed tree DRIFTED from repo source, project
  # `.git/` PRESENT) and asserts the LOUD `install-freshness.stale` warning is
  # ACTUALLY EMITTED on the observable sink — NOT merely that the gate was called.
  # This is the verify-the-instrument scenario the dispatch prompt mandates.
  # ─────────────────────────────────────────────────────────────────────────
  @walking_skeleton @coupled @driving_port @real-io @slice-01 @stale-#58 @contract-shape:bounded-change
  Scenario: A stale installed spine fires a hook and the operator sees a LOUD freshness warning while the session proceeds
    Given a synthetic installed spine whose code has drifted from the repository source
    And the operator runs from a developer checkout with a `.git` directory present
    When a spine hook fires on the hook hot path
    Then the operator sees a LOUD `install-freshness.stale` warning naming the digest mismatch
    And the spine hook proceeds the session with exit code 0

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — REGRESSION PIN (customer fidelity, the hard guardrail).
  # A customer install (manifest source_tree unreachable → state A) must keep
  # PROCEEDING SILENTLY, byte-identical to today. Asserts the freshness wiring
  # adds ZERO noise on the customer path (no stale warning, exit 0).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @customer @contract-shape:unbounded-preservation
  Scenario: A customer install on a host with no checkout proceeds silently when a hook fires
    Given a synthetic installed spine on a customer host with the source tree not reachable
    And the operator runs from a customer host with no checkout adjacency
    When a spine hook fires on the hook hot path
    Then the spine hook proceeds the session with exit code 0
    And the operator sees no freshness warning of any kind

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — FRESH DEV INSTALL (the positive of the #58 drift, boundary C3/C1).
  # When the installed tree MATCHES the repo source (a fresh reinstall, no
  # drift), the hook proceeds silently — no false-positive stale warning. This
  # is the discriminator that proves the gate compares CONTENT, not mere presence
  # of a `.git/` (the autoskip's coarse heuristic that #58 exploited).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @fresh @contract-shape:unbounded-preservation
  Scenario: A freshly reinstalled spine fires a hook and proceeds silently with no false warning
    Given a synthetic installed spine whose code matches the repository source
    And the operator runs from a developer checkout with a `.git` directory present
    When a spine hook fires on the hook hot path
    Then the spine hook proceeds the session with exit code 0
    And the operator sees no freshness warning of any kind

  # ─────────────────────────────────────────────────────────────────────────
  # AT-04 — OPERATOR OPT-OUT precedence (C5 mode-flag, C7 env).
  # The pre-existing `NWAVE_FRESHNESS=skip` operator opt-out must still
  # short-circuit AHEAD of everything — even in the #58 stale topology. A dev who
  # wants silence sets it and gets a `skipped` event, NOT a `stale` warning. This
  # pins the opt-out's precedence over the new hook wiring (orthogonality).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @opt-out @contract-shape:bounded-change
  Scenario: A stale installed spine stays silent on the stale warning when the operator opts out
    Given a synthetic installed spine whose code has drifted from the repository source
    And the operator runs from a developer checkout with a `.git` directory present
    And the operator has set the freshness opt-out
    When a spine hook fires on the hook hot path
    Then the spine hook proceeds the session with exit code 0
    And the operator sees a structured `des.runtime.freshness.skipped` acknowledgement
    And the operator sees no `install-freshness.stale` warning

  # ─────────────────────────────────────────────────────────────────────────
  # AT-05 — THE KPI SINK (DEVOPS DV-5 dual-emit, KPI-1 north-star substrate).
  # The LOUD warning must PERSIST to the JsonlAuditLogWriter SSOT (`audit-*.log`,
  # read by JsonlAuditLogReader + the KPI-1 query path), not only flash on ephemeral
  # stderr, and NOT to an orphan `audit.jsonl` no consumer reads (RELOOP_A: that was
  # a second audit-record representation — the disease this feature kills). This is
  # the queryable record KPI-1 ("0 silent-stale spine runs") is measured against.
  # Same #58 topology as AT-01; asserts the SECOND observable surface.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-01 @kpi @stale-#58 @contract-shape:bounded-change
  Scenario: A stale installed spine records the freshness warning in the persistent audit log
    Given a synthetic installed spine whose code has drifted from the repository source
    And the operator runs from a developer checkout with a `.git` directory present
    When a spine hook fires on the hook hot path
    Then the persistent audit log records one stale-install freshness event naming the remediation
