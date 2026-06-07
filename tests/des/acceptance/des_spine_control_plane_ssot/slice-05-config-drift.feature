@feature-des-spine-control-plane-ssot @slice-05
# Feature: The DES spine hook hot path catches a stale shipped CONFIG asset + names it LOUD
# Slice: 05 — config-asset drift envelope (the SYS-4 / AD-27 fix). Closes the
#         binding R1 ToC constraint. The freshness envelope today
#         (`runtime/tree_hash.py:61` `canonical_tree_hash`) globs ONLY `*.py`, so
#         a drifted shipped config asset (`lib/nWave/flavors/atdd_pure.yaml` — the
#         gate-composition SSOT slice-04 just made authoritative — or
#         `framework-catalog.yaml`) drifts SILENTLY: the exact same
#         multi-representation-drift disease, one asset-class over. DISCUSS Slice
#         Plan slice-05, DESIGN SYS-4, DDD-3.
#
# THE OPERATOR VALUE (DISCUSS Slice Plan row slice-05): "Operator sees a LOUD
# `install-freshness.config-drift` warning when a shipped config asset is stale,
# and the session proceeds (degrade-loud)." (The `feature_end_profile`
# required-records consolidation rides in the same slice on the DELIVER side —
# DDD-3 — but its operator-visible value is the config-drift warning here; the
# required-records edit is a maintainer-facing YAML ergonomics win, not a
# separately-observable AT surface at the hook driving port.)
#
# Driving port (Mandate-13, invariant 1+2): the HOOK ENTRYPOINT IMPORT —
#   `python -c "import des.adapters.drivers.hooks.claude_code_hook_adapter"`
# i.e. the hook PROCESS STARTUP, exactly as slice-01 (the freshness gate fires as
# an import-time side effect). The SAME driving port as slice-01; slice-05 widens
# the gate's ENVELOPE to the shipped `lib/nWave/` config assets. Driven against a
# synthetic install layout under tmp_path (the `des/` package under `lib/python/`
# + the config assets under `lib/nWave/` + a schema-v2 manifest), CWD set to a
# `.git/`-bearing project directory. Layer-3 subprocess / Layer-4 wiring_e2e: the
# SUT is the real installed hook process startup, NOT a domain function. NEVER
# `from des.runtime.freshness import ...` invoked at the test boundary.
#
# ── THE LOAD-BEARING RED (verify-the-instrument) ──
# AT-01 constructs the AD-27 topology — a fresh `*.py` tree (so the slice-01
# `*.py` envelope resolves state C / silent) BUT a DRIFTED shipped
# `flavors/atdd_pure.yaml` (installed content != the manifest's schema-v2
# `config_assets_tree_hash` snapshot). Today the gate hashes ONLY `*.py`
# (`canonical_tree_hash` globs `*.py`; the manifest is schema v1 with NO
# `config_assets_tree_hash`; `FreshnessStateLabel` has NO config-drift state),
# so the probe sees a MATCHES `*.py` tree → state C → SILENT PROCEED, and the
# LOUD `install-freshness.config-drift` warning is NEVER emitted. AT-01 RED-fails
# the assertion (the warning is absent). AT-02 (fresh config, silent) is the
# content-discriminator regression pin that proves the gate compares config
# CONTENT, not the mere presence of `lib/nWave/` (without AT-02, a config-drift
# warning that fired on any `lib/nWave/` presence would pass AT-01 vacuously).
#
# Degrade-loud contract (DISCUSS D1, DEVOPS DV-2/DV-4, resolving DESIGN OQ#1):
# the HOOK degrades LOUD (warns + proceeds, exit 0) on config drift. It NEVER
# hard-blocks the session. The CLI keeps its exit-78 REFUSE; the hook path is
# degrade-loud — the OSS non-halting ACL semantics, mirroring slice-01.
#
# Observable sink (Mandate-13 invariant 3, DEVOPS DV-5 dual-emit): the LOUD
# warning is observable on TWO surfaces — (a) a structured
# `install-freshness.config-drift` event on stderr (operator reads in-flow) AND
# (b) a persisted record in the JsonlAuditLogWriter SSOT (`audit-*.log` under the
# `AuditLogPathResolver` dir, the KPI-1 substrate — NOT a new `audit.jsonl`
# representation). AT-01 asserts stderr; AT-03 asserts the persisted SSOT record.
#
# Integration surface (Mandate-13 invariant 4): every scenario crosses the REAL
# installed-config-vs-snapshot seam — a real synthetic `lib/nWave/` config tree +
# a real schema-v2 manifest + the real freshness probe (re-)hashing the config
# assets. No mock of the probe; the drift is a genuine filesystem-content
# divergence in a shipped `*.yaml`.
#
# Mechanical assertion (Mandate-13 invariant 5): Python-only, GIT-FREE — the
# `.git/`-adjacency topology is a filesystem fixture (an empty `.git/` dir),
# NEVER a `git` subprocess. The config hash is filesystem content, no git. Cross-OS.
#
# Universe (Mandate 8): {exit_code, verdict} via assert_state_delta on the PROCEED
# outcome; the stderr-event + audit-record assertions are example-based equality
# (port-exposed observables on ConfigHookOutcome). Internal fields (Popen handle,
# env dict, manifest dict) NEVER appear.
#
# Layer 3/4 (subprocess against tmp_path): example-only (Mandate 9 v2 — the driven
# set includes a REAL filesystem adapter → @real-io → example-based, NOT PBT). Sad
# paths explicit (Mandate 11). No PBT machinery imported.
#
# AT-completeness taxonomy (C-categories): AT-01 = C2 (state transition: fresh →
# config-drift) + C6 (negative/robustness: stale config → explicit LOUD typed
# event, never silent coercion). AT-02 = C2 (the legal no-drift transition stays
# silent) + the content-discriminator boundary (C1). AT-03 = C6 observability +
# the KPI-1 persistence contract.

Feature: The spine hook hot path catches a stale shipped config asset and names it LOUD
  As a developer running a feature through the DES spine on my own machine
  I want a hook fire on a drifted shipped config asset to emit a LOUD, named warning
  So that I reinstall before trusting a run that read a stale gate-composition config
  And the session still proceeds (a freshness miss must never brick me mid-flow)
  And a fresh install with matching config keeps proceeding silently (no false warning)

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — THE LOAD-BEARING CONFIG-DRIFT WARNING (SYS-4 / AD-27, the operator value).
  # Constructs the AD-27 topology (fresh `*.py` tree, DRIFTED shipped
  # `flavors/atdd_pure.yaml`) and asserts the LOUD `install-freshness.config-drift`
  # warning is ACTUALLY EMITTED on stderr — NOT merely that the gate was reached.
  # RED today: the `*.py`-only envelope cannot see the config drift (state C →
  # silent), so the warning is absent. This is the verify-the-instrument scenario.
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @config-drift @ad-27 @contract-shape:bounded-change
  Scenario: A stale shipped config asset fires a hook and the operator sees a LOUD config-drift warning while the session proceeds
    Given a synthetic installed spine whose shipped configuration has drifted from the install snapshot
    And the operator runs from a developer checkout with a `.git` directory present
    When a spine hook fires on the hook hot path
    Then the operator sees a LOUD `install-freshness.config-drift` warning naming the stale asset
    And the spine hook proceeds the session with exit code 0

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — FRESH CONFIG (the content-discriminator regression pin, boundary C1/C2).
  # When the shipped config assets MATCH their install snapshot (a fresh reinstall,
  # no config drift), the hook proceeds silently — no false-positive config-drift
  # warning. This is the discriminator that proves the gate compares config
  # CONTENT, not the mere presence of `lib/nWave/`. GREEN today (the `*.py` envelope
  # already resolves state C / silent on a fresh tree) — and MUST stay GREEN after
  # the config envelope lands (the widened hash must not over-fire on matching config).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @fresh-config @contract-shape:unbounded-preservation
  Scenario: A freshly reinstalled spine with matching config fires a hook and proceeds silently with no false warning
    Given a synthetic installed spine whose shipped configuration matches the install snapshot
    And the operator runs from a developer checkout with a `.git` directory present
    When a spine hook fires on the hook hot path
    Then the spine hook proceeds the session with exit code 0
    And the operator sees no freshness warning of any kind

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — THE KPI SINK (DEVOPS DV-5 dual-emit, KPI-1 north-star substrate).
  # The LOUD config-drift warning must PERSIST to the JsonlAuditLogWriter SSOT
  # (`audit-*.log`, read by JsonlAuditLogReader + the KPI-1 query path), not only
  # flash on ephemeral stderr. Same AD-27 topology as AT-01; asserts the SECOND
  # observable surface — the queryable record KPI-1 ("0 silent-stale spine runs",
  # extended to config assets) is measured against. RED today (no config-drift
  # event reaches the gate, so no record is persisted).
  # ─────────────────────────────────────────────────────────────────────────
  @coupled @driving_port @real-io @slice-05 @kpi @config-drift @contract-shape:bounded-change
  Scenario: A stale shipped config asset records the config-drift warning in the persistent audit log
    Given a synthetic installed spine whose shipped configuration has drifted from the install snapshot
    And the operator runs from a developer checkout with a `.git` directory present
    When a spine hook fires on the hook hot path
    Then the persistent audit log records one config-drift freshness event naming the remediation
