@feature-des-spine-control-plane-ssot @slice-04
# Feature: The spine sources its per-lifecycle gate composition from ONE place —
#          the flavor YAML — so a maintainer changes which gate(s) fire at a
#          lifecycle boundary via a readable flavor-YAML row, not a Python
#          if-ladder + a hardcoded frozenset (gate-composition SSOT 3 -> 1).
# Slice: 04 — gate-composition SSOT (Class C, @infrastructure, NOT a walking
#         skeleton). The LEAD facet of #67 (DESIGN facet-1, DDD-1). Consolidates
#         the THREE representations of "what gate fires at lifecycle event E":
#           1. the SSOT (intended): `nWave/flavors/atdd_pure.yaml:36-87` declares
#              all four lifecycle events;
#           2. the live wiring (1 of 4): `flavor_dispatcher.dispatch_lifecycle_event`
#              is called only from `carpaccio_intercept.py:522` for `dispatch.pre`;
#           3. the DEAD wiring (3 of 4): `subagent.stop` + `commit.pre` +
#              `session.init` are DEAD YAML — hand-wired as an if-ladder
#              (`subagent_stop_handler.py:1356-1370`) + a hardcoded feature-end
#              required-records frozenset (`_REQUIRED_FEATURE_END_RECORDS`,
#              `:820-829`, six literal names hand-edited across five prior
#              features — the edit-in-N-places fixture-fanout the SSOT mandate bans).
#         into ONE source: the flavor YAML composition. DESIGN Aggregate
#         `LifecycleComposition` invariant: `gates_fired_at(E) == yaml_composition(
#         flavor, E)` for all four E.
#
# THE MAINTAINER VALUE (DISCUSS Slice Plan row slice-04): "Maintainer changes
# which gates fire at a lifecycle boundary via one readable flavor-YAML row
# instead of a Python if-ladder (gate-composition SSOT 3 -> 1)." @infrastructure:
# a structural SSOT consolidation with no NEW operator-invocable behavior on its
# own (the gates that fire are identical) — but it is mechanically OBSERVABLE that
# the composition is now YAML-driven (a flavor-YAML edit changes which records the
# subagent.stop boundary demands) rather than frozenset-hardcoded.
#
# Driving port (Mandate-13, invariant 1+2): the spine's REAL `subagent.stop`
# lifecycle-event surface — `python -m
# des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop` — invoked
# exactly as Claude Code invokes it when a dispatched atdd_pure crafter returns
# (an `agent_transcript_path` payload on stdin). Layer-3 subprocess: the SUT is
# the real hook process; NEVER `from des.application.flavor_dispatcher import
# dispatch_lifecycle_event`, NEVER `from
# des.adapters.drivers.hooks.subagent_stop_handler import _handle_feature_end_gate`
# invoked at the test boundary. The gate composition that fires is read off the
# port's REAL behaviour (its stdout block-decision JSON + exit code), not an
# internal dispatcher call. This mirrors slice-01/03 house style (subprocess) and
# the d4_phase_3 precedent (the dispatcher's public entry IS the driving port).
#
# Integration surface (Mandate-13 invariant 4): every scenario crosses the REAL
# transcript -> context-resolution -> feature-end-gate -> required-records seam.
# The project is a real `.nwave/config.yaml` + feature-delta slice-plan + a real
# F_FINAL_REVIEW transcript on disk; the gate runs inside the production hook
# subprocess; the verdict is the hook's real block-decision path. The flavor
# composition is a real flavor file the `NWAVE_FLAVORS_DIR` override (the SSOT seam
# slice-04 wires) points at — no predicate is stubbed.
#
# Mechanical assertion (Mandate-13 invariant 5): Python-only, git-free, cross-OS —
# the feature-end topology is constructed by writing a synthetic F_FINAL_REVIEW
# transcript (the public HTML-comment marker block `/nw-deliver` renders) + a
# one-row shipped slice-plan (markdown fallback -> planned == shipped) + NO ledger
# (records absent -> the missing-records branch is reachable). NEVER by shelling
# out to a tool. `NWAVE_FRESHNESS=skip` (per-subprocess, DV-1) isolates the
# slice-01 install-freshness gate so its `stale` stderr chatter does not confound
# the stdout block-JSON parse AND a `.git/`-adjacency autoskip cannot mask the
# verdict (RCA #68 P1-B). The red-classification run additionally sets
# `NWAVE_FRESHNESS=""` at the pytest level for env-parity.
#
# Observable sink (Mandate-13 invariant 3): the hook's stdout block-decision JSON
# — `{"decision":"block","event":"FeatureEndCycleIncomplete","missing":[...]}` —
# whose `missing` list is the required-records profile the subagent.stop boundary
# demands. NOT internal dispatcher return values; NOT the frozenset's identity;
# NOT private function call counts. The `missing` set discriminates a YAML-sourced
# profile (slice-04 cure) from the hardcoded frozenset (today).
#
# Universe (Mandate 8): {boundary.outcome, boundary.missing_records,
# boundary.block_event}. Internal fields (Popen handle, env dict, raw stream
# bytes, the parsed JSON object) NEVER appear.
#
# State machine the spine enforces on the gate-composition seam (slice-04):
#   (feature-end return, PRODUCTION flavor) --subagent-stop--> blocks demanding
#       EXACTLY the shipped six records (behavior preserved)                (AT-03)
#   (feature-end return, EMPTY-records flavor) --subagent-stop--> NO LONGER
#       blocks on missing records (profile is YAML-sourced, not frozenset)  (AT-01)
#   (feature-end return, SENTINEL-record flavor) --subagent-stop--> blocks
#       naming the YAML-declared extra record (composition is YAML-driven)  (AT-02)
#
# Behavior-preservation guard (DEVOPS slice-04 deploy gate, the risk it names):
# "a mis-composed flavor YAML changes which gates fire. The composition AT
# (`gates_fired_at(E) == yaml_composition(flavor, E)`) is the deploy gate." AT-03
# IS that guard — it is GREEN today (the production six) and MUST stay GREEN after
# routing, catching any routing that changes the shipped behavior.
#
# Layer 3 (subprocess against tmp_path, @real-io — the driven set includes a real
# filesystem adapter the hook reads config + feature-delta + transcript from):
# example-only (Mandate 9 v2). Each feature-end verdict is one explicit named
# example per flavor composition (Mandate 11). No PBT.
#
# Carpaccio ceiling = 3 (Class C, @infrastructure, NOT a walking skeleton): 3 thin
# ATs. NOT a @coupled group — each AT is independently meaningful:
#   AT-01 = the load-bearing YAML-driven-ness discriminator (empty profile ->
#           boundary stops demanding the frozenset six);
#   AT-02 = the stronger `gates_fired_at(E) == yaml_composition(E)` invariant
#           (an ADDED record proves the profile is read from the YAML);
#   AT-03 = the behavior-preservation guard (production six unchanged — the
#           regression pin DEVOPS demands).
# AT-01 alone establishes "the frozenset no longer governs"; AT-02 pins the
# positive direction (the YAML composition governs); AT-03 pins that the
# consolidation is invariant-preserving on the shipped flavor.

Feature: The spine sources its subagent-stop gate composition from one readable flavor YAML
  As a maintainer of the DES spine
  I want which gates fire at a lifecycle boundary to come from one flavor-YAML row
  So that I add or change a feature-end gate by editing one readable composition row
  Instead of hand-editing a Python if-ladder and a hardcoded required-records frozenset
  And so the gates that fire are exactly the composition the flavor YAML declares

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — YAML-SOURCED PROFILE (the load-bearing #67 discriminator): an EMPTY
  # feature-end required-records profile in the flavor makes the subagent-stop
  # boundary STOP demanding the hardcoded six. The required-records profile is
  # the flavor composition field, not the `_REQUIRED_FEATURE_END_RECORDS`
  # frozenset. Witnessed RED at DISTILL HEAD: the boundary blocks naming the six
  # regardless of the flavor (the if-ladder ignores `NWAVE_FLAVORS_DIR`).
  # ─────────────────────────────────────────────────────────────────────────
  @driving_port @real-io @slice-04 @gate-composition-ssot @yaml-driven @contract-shape:bounded-change
  Scenario: An empty feature-end record profile makes the subagent-stop boundary stop demanding the hardcoded records
    Given a feature whose only slice is shipped and that runs under a gate composition that demands no feature-end records at the subagent-stop boundary
    When the feature-end crafter returns to the subagent-stop boundary
    Then the boundary no longer demands any feature-end record

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — YAML-DRIVEN COMPOSITION (`gates_fired_at(E) == yaml_composition(E)`):
  # a flavor ADDING one feature-end required-record makes the subagent-stop
  # boundary block naming THAT record — proving the profile is read from the
  # flavor YAML composition, not the hardcoded frozenset. Witnessed RED: the
  # frozenset is the SSOT and the YAML-declared record never appears in `missing`.
  # ─────────────────────────────────────────────────────────────────────────
  @driving_port @real-io @slice-04 @gate-composition-ssot @yaml-driven @contract-shape:bounded-change
  Scenario: An added feature-end record in the composition is demanded at the subagent-stop boundary
    Given a feature whose only slice is shipped and that runs under a gate composition that adds one extra feature-end record at the subagent-stop boundary
    When the feature-end crafter returns to the subagent-stop boundary
    Then the boundary demands the extra feature-end record the composition declares

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — BEHAVIOR PRESERVATION (the DEVOPS deploy gate / regression pin): with
  # the SHIPPED flavor (no override), the subagent-stop boundary blocks demanding
  # EXACTLY the production six records — byte-identical to today's if-ladder +
  # frozenset verdict. GREEN today; MUST stay GREEN after the routing, catching
  # any consolidation that changes the shipped composition. This is the guard the
  # SSOT-mandate demands: the declared delta of "route through the YAML" must NOT
  # change the gates that actually fire on the shipped flavor.
  # ─────────────────────────────────────────────────────────────────────────
  @driving_port @real-io @slice-04 @gate-composition-ssot @behavior-preservation @regression @contract-shape:unbounded-preservation
  Scenario: The shipped flavor preserves exactly the production feature-end records at the subagent-stop boundary
    Given a feature whose only slice is shipped and that runs under the shipped gate composition
    When the feature-end crafter returns to the subagent-stop boundary
    Then the boundary demands exactly the shipped feature-end records
