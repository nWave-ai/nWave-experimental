@feature-wave-gateout-enforced-under-orchestration @driving_port @real-io
Feature: A DISCUSS wave-agent return under orchestration reaches its structural gate-out

  slice-03 (regression-lock, GREEN-on-keystone). The keystone wave-parametric route
  reaches the DISCUSS two-row gate-out stack [validate-feature-delta,
  verify-discuss-review] for a DISCUSS wave-agent returning via Agent(). This slice
  LOCKS the FIRST row -- the structural validate-feature-delta gate-out (the MECC
  floor over the feature-delta slice plan): a malformed / non-value-bearing slice
  plan (every slice @infrastructure) is refused with a SLICE_PLAN_REJECTED veto; a
  well-formed value-bearing slice plan is NOT blocked on structural grounds (the
  structural row passes).

  Driving surface (Mandate-13 driving-port-only): the REAL SubagentStop hook entry
  driven through the production composition root. Reuses the slice-01 driving
  primitives. Real-Surface Binding:
    AT-06 -> handle_subagent_stop reaching SubagentStopService.validate ->
             _discuss_gate_out_declarative -> _gate_out_structural ->
             DiscussGateOut.evaluate over the infra-only slice plan; observable =
             block (SLICE_PLAN_REJECTED).
    AT-07 -> the same path with a value-bearing slice plan; observable = the
             structural row does NOT block (DiscussGateOut.evaluate -> PASS).

  @slice-03 @feature-wave-gateout-enforced-under-orchestration @error @contract-shape:unbounded-preservation
  Scenario: A discuss return with a non-value-bearing feature-delta is refused
    Given a product-owner is returning a DISCUSS deliverable under autonomous orchestration
    And the feature-delta slice plan carries no user-observable value
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is refused with a non-value-bearing slice-plan reason

  @slice-03 @feature-wave-gateout-enforced-under-orchestration @contract-shape:unbounded-preservation
  Scenario: A discuss return with a value-bearing feature-delta is not blocked on structural grounds
    Given a product-owner is returning a DISCUSS deliverable under autonomous orchestration
    And the feature-delta slice plan carries user-observable value
    When the orchestration return is evaluated at the wave boundary
    Then the wave closure is not refused on structural grounds
