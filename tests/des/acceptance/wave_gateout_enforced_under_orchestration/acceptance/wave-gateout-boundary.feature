@feature-wave-gateout-enforced-under-orchestration @driving_port @real-io
Feature: An unresolvable DES return fails closed; a non-DES return passes through

  slice-06 (fail-closed boundary + ADD-not-mutate regression). The final slice
  closes the fail-OPEN leak in the wave-only reachability route and locks the
  no-regression contract:

    * UNRESOLVABLE DES return -> REFUSE (degrade-LOUD). A return carrying a DES-WAVE
      marker the resolver cannot resolve -- the wave is OUT-OF-VOCABULARY, OR the
      DES-PROJECT-ID is absent -- must NEVER silently passthrough-allow. A DES-WAVE
      was clearly declared; the resolver could not map it; that is INDETERMINATE,
      which degrades LOUD to a refusal, distinct from a genuine non-DES return.
      ACTIVE-RED at HEAD: _resolve_wave_only_context returns None for such a return,
      which the caller maps to the silent passthrough-allow.
    * GENUINE NON-DES return -> ALLOW (byte-stable). A return with NO DES-WAVE marker
      at all is a genuinely non-DES agent and stays allowed -- the fail-closed cure
      must not over-reach. GREEN-on-keystone.
  Driving surface (Mandate-13 driving-port-only): the REAL SubagentStop hook entry
  driven through the production composition root with a constructed return on stdin.
  The observable is the hook decision body on stdout. Reuses the slice-01 primitives.

  Real-Surface Binding:
    AT-13 -> handle_subagent_stop -> _resolve_des_context -> _resolve_wave_only_context
             with an OUT-OF-VOCABULARY DES-WAVE; observable = block (ACTIVE-RED: today
             returns None -> silent passthrough-allow).
    AT-14 -> the same path with a DES-WAVE but NO DES-PROJECT-ID; observable = block
             (ACTIVE-RED: today `not project_id` -> None -> silent passthrough-allow).
    AT-15 -> handle_subagent_stop with NO DES-WAVE marker (genuine non-DES return);
             observable = allow (the existing passthrough, byte-stable).

  # AT-13 (fail-closed, ACTIVE-RED): an out-of-vocabulary DES-WAVE must fail closed.
  @slice-06 @feature-wave-gateout-enforced-under-orchestration @error @contract-shape:unbounded-preservation
  Scenario: A return declaring an out-of-vocabulary wave is refused, not silently allowed
    Given a wave-agent returns under orchestration declaring an out-of-vocabulary wave
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused

  # AT-14 (fail-closed, ACTIVE-RED): a DES-WAVE without a project id must fail closed.
  @slice-06 @feature-wave-gateout-enforced-under-orchestration @error @contract-shape:unbounded-preservation
  Scenario: A return carrying a wave marker but no project identity is refused
    Given a wave-agent returns under orchestration with a wave marker but no project identity
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused

  # AT-15 (regression-lock, GREEN): a genuinely non-DES return stays allowed.
  @slice-06 @feature-wave-gateout-enforced-under-orchestration @contract-shape:unbounded-preservation
  Scenario: A genuinely non-DES return passes through untouched
    Given an agent returns under orchestration carrying no DES wave marker at all
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is allowed
