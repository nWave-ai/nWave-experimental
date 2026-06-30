@feature-f-nonbypassable-attestation @slice-05
Feature: A wave cannot be entered off-spine silently — guard verdicts
  As an orchestrator dispatching a wave-OWNER agent
  I want a dispatch lacking the matching DES-WAVE marker to be BLOCKED (warn+ask),
    while an on-spine marker (or an exempt reviewer) is ALLOWED and recognized
  So that entering DISCOVER/DIVERGE/DISCUSS/DESIGN/DEVOPS/DISTILL/DELIVER off-spine
    is a conscious EXCEPTION the human concedes, never the silent default the
    flow-v2 incident exploited one level up from per-commit bypass

  # slice-05 of f-nonbypassable-attestation (DDD-8, KPI-1 family at the wave
  # boundary) — the GUARD-VERDICT half of the split slice-05 (carpaccio sizing
  # fix 2026-06-16: the original slice-05 carried 10 scenarios, over the
  # carpaccio ceiling of 5). slice-05 (guard half) = the 5 guard-verdict states (BLOCK-no-marker +
  # the four ALLOW recognitions). slice-06 (skip half) = the 5 skip-authorization states.
  #
  # The production guard is PRODUCTION RUNTIME enforcement in the DES runtime --
  # a pure domain policy (src/des/domain/wave_dispatch_guard_policy.py) + a
  # `des.cli` gate (src/des/cli/verify_wave_dispatch.py) mirroring
  # verify_readiness_pre_dispatch.py, composed onto dispatch.pre. NOT the
  # hand-placed ~/.claude personal hook (which has no repo source -- DDD-8). The
  # ATs drive the IN-TREE gate, hermetically. slice-05 (guard half)'s DELIVER BUILDS that runtime
  # (the policy + the `des verify-wave-dispatch` gate + dispatch.pre + installer);
  # slice-06 (skip half)'s DELIVER is ATs-only (the runtime is already built by slice-05 (guard half)).
  #
  # DRIVING SURFACE (Mandate-13, Layer-3 subprocess): the REAL in-tree gate
  #   `python -m des.cli.verify_wave_dispatch`, driven via its ARGS calling
  #   convention (§22.0 H-2): --subagent-type, --prompt-path (a tmp fixture FILE
  #   holding the dispatch prompt -- hermetic, no ~/.claude), --repo-root,
  #   --session-id. observable = the process EXIT CODE (ALLOW=0 / BLOCK=1 /
  #   malformed=2) + the one JSON line printed on stdout {event, subagent_type,
  #   wave, verdict, reason}. No guard logic is re-implemented in the step bodies
  #   (the AT drives the real shipped gate, never a test-local reimplementation --
  #   protocol-driver contract).
  #
  # DORMANT-SEAM (D11 / DDD-8): the net-new load-bearing seams are (a) the
  #   wave->owner map + DISPATCH_GUARD_VOCABULARY in the new domain policy, and (b)
  #   the verify_wave_dispatch gate composed onto dispatch.pre. At HEAD neither the
  #   policy nor the gate module exists, so `python -m des.cli.verify_wave_dispatch`
  #   cannot ALLOW or BLOCK -- it exits non-zero on module-absence. Each scenario
  #   drives THAT seam through the real gate entry point + asserts the exit-code
  #   observable effect.
  #
  # DISTINCT FIXTURE PER VERDICT (§22.0 gap): marker-absent / marker-present /
  #   platform-architect-design / platform-architect-devops / reviewer are
  #   GENUINELY different dispatch states (different args + different on-disk prompt
  #   fixtures), never one payload re-asserted with different Thens.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD the verify_wave_dispatch gate +
  #   the wave_dispatch_guard_policy do not exist, so every scenario observes a
  #   module-absent non-zero exit that is NEITHER the expected ALLOW (0) nor the
  #   expected BLOCK (1) -- semantic AssertionErrors against the expected verdict.
  #   GREEN once DELIVER ships the policy + the gate + the dispatch.pre row (DDD-8).

  # ---- CT-8: off-spine wave-owner without the marker is BLOCKED --------------

  @slice-05 @walking_skeleton @driving_port @real-io @us-non-silent-wave-entry @error @contract-shape:bounded-change
  Scenario: Dispatching a wave-owner with no DES-WAVE marker is blocked
    Given the orchestrator dispatches a wave-owner agent
    And the dispatch carries no DES-WAVE marker
    When the orchestrator dispatches the agent
    Then the dispatch is blocked with a warn-and-ask reason

  # ---- CT-9: on-spine marker allows; reviewers always allowed ----------------

  @slice-05 @walking_skeleton @driving_port @real-io @us-non-silent-wave-entry @contract-shape:bounded-change
  Scenario: Dispatching the same wave-owner with the matching marker is allowed and recognized
    Given the orchestrator dispatches a wave-owner agent
    And the dispatch carries the matching DES-WAVE marker
    When the orchestrator dispatches the agent
    Then the dispatch is allowed and names the recognized on-spine signal

  @slice-05 @driving_port @real-io @us-non-silent-wave-entry @contract-shape:bounded-change
  Scenario: Dispatching the platform architect with the design marker is allowed and recognized
    Given the orchestrator dispatches the platform architect agent
    And the dispatch carries the design wave marker
    When the orchestrator dispatches the agent
    Then the dispatch is allowed and names the recognized on-spine signal

  @slice-05 @driving_port @real-io @us-non-silent-wave-entry @contract-shape:bounded-change
  Scenario: Dispatching the platform architect with the devops marker is allowed and recognized
    Given the orchestrator dispatches the platform architect agent
    And the dispatch carries the devops wave marker
    When the orchestrator dispatches the agent
    Then the dispatch is allowed and names the recognized on-spine signal

  @slice-05 @driving_port @real-io @us-non-silent-wave-entry @contract-shape:bounded-change
  Scenario: Dispatching a reviewer agent is always allowed
    Given the orchestrator dispatches a reviewer agent
    And the dispatch carries no DES-WAVE marker
    When the orchestrator dispatches the agent
    Then the reviewer dispatch is always allowed
