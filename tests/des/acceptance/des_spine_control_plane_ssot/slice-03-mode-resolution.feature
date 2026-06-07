@feature-des-spine-control-plane-ssot @slice-03
# Feature: The spine resolves ONE workflow-mode answer, so the DELIVER dispatch and
#          verify-integrity agree — and verify never hunts for a roadmap.json the
#          active mode never wrote (#65 dissolved).
# Slice: 03 — mode-resolution SSOT (Class C, NOT a walking skeleton). Consolidates
#         the two-resolver / two-opposite-default divergence (DDD-5/6/7):
#           * `workflow_mode._resolve_workflow_mode` (`:92`)  absent -> classic
#             (consumed by verify_deliver_integrity:539 [#65], init_log:135,
#              session_start_handler:229)
#           * `init_log.resolve_dispatch_mode` (`:63`/`_read_workflow_mode:104`)
#             absent -> atdd_pure (the DELIVER-dispatch resolver)
#         into ONE `resolve_workflow_mode -> WorkflowMode` with ONE absent-key
#         default (atdd_pure, DDD-7). DISCUSS US-3, Slice Plan slice-03, DESIGN
#         Domain-Scope (Context-B Mode-Resolution), Outcome KPI-3.
#
# THE OPERATOR VALUE (DISCUSS Slice Plan row slice-03 + US-3): "Operator gets ONE
# mode answer so DELIVER and verify-integrity agree; verify never hunts for a
# roadmap.json the active mode never wrote (#65 dissolved)."
#
# Driving port (Mandate-13, invariant 1+2): the spine's TWO mode-reading driving
# CLIs — `des verify-integrity` (the verify role, wired at `des.cli.__main__:45`
# kebab dispatcher) and `des init-log` (the DELIVER-dispatch role) — invoked
# exactly as the operator + `/nw-deliver` invoke them. Layer-3 subprocess: the SUT
# is the real CLI process; NEVER `from des.application.workflow_mode import
# _resolve_workflow_mode` invoked at the test boundary, NEVER `from des.cli.init_log
# import resolve_dispatch_mode`. The mode answer is read off each port's REAL
# behaviour (exit code + refusal surface), not an internal resolver call.
#
# Integration surface (Mandate-13 invariant 4): every scenario crosses the REAL
# config -> resolver -> consumer seam. The mode config is a real `.nwave/config.yaml`
# on disk (or its deliberate ABSENCE — the #65 trigger); the resolver runs inside
# the production CLI; the consumer is the CLI's real verdict path (verify's
# atdd_pure branch / classic roadmap hunt; init-log's atdd_pure refusal / classic
# log creation). No predicate is stubbed.
#
# Mechanical assertion (Mandate-13 invariant 5): Python-only, git-free, cross-OS —
# the UNCONFIGURED topology is constructed by simply NOT writing a
# `.nwave/config.yaml` (never by shelling out to a tool). `NWAVE_FRESHNESS=skip`
# isolates the slice-01 install-freshness gate so the mode answer is observed
# without freshness chatter AND is not masked by a `.git/`-adjacency autoskip
# (RCA #68 P1-B: a skip-masked freshness state must not confound this assertion;
# the skip masks slice-01's gate ONLY, never the slice-03 mode answer).
#
# Observable sink (Mandate-13 invariant 3): the process exit code + the structured/
# plain-text refusal surface (verify: the `roadmap.json not found` phantom-refusal
# present-or-absent; init-log: the `workflow.mode is atdd_pure` refusal vs the
# `Created execution-log.json` banner). NOT internal resolver return values; NOT
# private function call counts.
#
# Universe (Mandate 8): {verify.exit_code, verify.outcome, verify.roadmap_hunt}.
# Internal fields (Popen handle, env dict, raw stream bytes) NEVER appear.
#
# State machine the spine enforces on the mode seam (slice-03), absent-key case:
#   (unconfigured project) --verify--> resolves atdd_pure, checks the ledger that
#                                      EXISTS -> NO phantom roadmap hunt  (AT-01)
#   (unconfigured project) --DELIVER+verify--> BOTH ports resolve the SAME answer
#                                      (atdd_pure): init-log REFUSES (roadmap-free),
#                                      verify takes the atdd_pure branch  (AT-02)
#
# #65-dissolution observable: the legacy bug is verify exit 2 `roadmap.json not
# found` on an unconfigured atdd_pure project (mode mis-resolved to classic).
# Witnessed at DISTILL HEAD: exit 2. AT-01 asserts that phantom-refusal is ABSENT
# post-consolidation; the verifier reaches its verdict by reading the
# AT-completion ledger the atdd_pure spine actually wrote.
#
# Layer 3 (subprocess against tmp_path, @real-io — the driven set includes a real
# filesystem adapter the CLIs read config + ledger from): example-only (Mandate
# 9 v2). The #65 sad path is one explicit named example (Mandate 11). No PBT.
#
# Carpaccio ceiling = 3 (Class C, NOT a walking skeleton): 2 thin, independent ATs.
# NOT a @coupled group — each AT is independently meaningful and shippable:
#   AT-01 = the #65-dissolution (verify resolves the active mode, no phantom hunt);
#   AT-02 = the cross-port default-consistency (DELIVER == verify on one answer).
# AT-01 alone dissolves #65 (the load-bearing operator value); AT-02 pins the
# stronger system-wide referential-transparency invariant AT-01 does not give on
# its own (one port resolving right is not yet "all ports agree").

Feature: The spine resolves one workflow-mode answer so every port agrees
  As an operator running the DES spine on a project
  I want the DELIVER dispatch and verify-integrity to resolve the same workflow mode
  So that I can trust that the run and its verification agree on what mode they are in
  And verify-integrity never hunts for a roadmap.json the active mode never wrote
  Instead of chasing a phantom missing-artifact refusal on an unconfigured project

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — #65 DISSOLVED: verify resolves the active mode, no phantom roadmap
  # hunt (the load-bearing operator value, US-3 sad path → fixed).
  # On an UNCONFIGURED project the verifier must resolve the active mode
  # (atdd_pure, the one absent-key default per DDD-7) and check the AT-completion
  # ledger the atdd_pure spine actually wrote — NOT mis-resolve to classic and
  # refuse exit 2 `roadmap.json not found` for a file the active mode never
  # created. Witnessed RED at DISTILL HEAD: exit 2 phantom-roadmap refusal.
  # ─────────────────────────────────────────────────────────────────────────
  @driving_port @real-io @slice-03 @mode-ssot @regression-65 @contract-shape:unbounded-preservation
  Scenario: Verify-integrity on an unconfigured project resolves the active mode without hunting for a phantom roadmap
    Given a project with no workflow mode configured
    When the operator runs verify-integrity on the project
    Then verify-integrity resolves the active mode and checks the artifacts it actually wrote
    And verify-integrity never hunts for a roadmap the active mode never wrote

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — DEFAULT CONSISTENCY: the DELIVER dispatch and verify agree on ONE
  # mode answer (the system-wide referential-transparency invariant, US-3).
  # On the SAME unconfigured project, the DELIVER-dispatch port (init-log) and
  # the verify port must resolve the SAME mode answer (atdd_pure). The DELIVER
  # port resolving atdd_pure is OBSERVABLE as init-log REFUSING to create a
  # roadmap-based log (the spine is roadmap-free); the verify port resolving
  # atdd_pure is its atdd_pure branch. Today they DIVERGE — init-log creates a
  # classic log while verify hunts for a phantom roadmap.
  # ─────────────────────────────────────────────────────────────────────────
  @driving_port @real-io @slice-03 @mode-ssot @default-consistency @contract-shape:bounded-change
  Scenario: The DELIVER dispatch and verify-integrity resolve the same mode answer on an unconfigured project
    Given a project with no workflow mode configured
    When the operator starts a DELIVER dispatch and runs verify-integrity on the project
    Then the DELIVER dispatch and verify-integrity agree on one mode answer
    And the DELIVER dispatch refuses to create a roadmap-based log under that mode
