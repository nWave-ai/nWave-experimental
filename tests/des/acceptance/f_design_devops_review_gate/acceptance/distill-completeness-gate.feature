@feature-f-design-devops-review-gate @driving_port @real-io
Feature: A DISTILL AT return has AT-completeness auto-checked from the gate-stack, not orchestration prose

  An acceptance-designer who returns DISTILL ATs has AT-completeness auto-checked
  MECHANICALLY -- `check-slice-at-completeness` (the EXISTING completeness CLI,
  zero new gate logic) is referenced from the DISTILL wave gate-stack `gate-out`
  (PRIMARY -- it fires on the DISTILL return, the wave it belongs to). So an incomplete slice
  is refused on the DISTILL return, NEVER relying on the `/nw-distill` orchestration prose step.

  Reconciliation flag (brief slice-06 registry MOVE): the DISTILL gate-out stack
  is authored in the canonical flavor-INDEPENDENT wave-contract registry
  `nWave/waves/distill.yaml` -- the registry HOME, mirroring the slice-01/02
  `nWave/waves/design.yaml` + `devops.yaml`, NOT the flavor. The feature-delta
  text "wave_gate_stacks.distill.gate-out (flavor)" predates the slice-06 registry
  move; `wave_gate_stack_dispatch.resolve_stack` reads the registry as the SOLE
  gate-stack source (ADR-FLOW-006 D6), so the flavor-private `distill` co-tenant
  block (atdd_pure.yaml, owned by f-coherence-and-attestation) is NOT the surface
  the spine resolves -- the registry file is.

  Driving surface (Mandate-13 driving-port-only): ONE real wired seam, no
  direct-domain import for business logic.
    * Layer 3 composition (AT-10) -- the REAL spine
      `wave_gate_stack_dispatch.resolve_stack("distill", "gate-out")` reading the
      SHIPPED `nWave/waves/distill.yaml` registry file (the same spine entry the
      live SubagentStop gate-out caller uses, subagent_stop_service.py:344). The
      observable is the ordered gate-id sequence; the SSOT-reuse cross-check is two
      independent reads (registry-FILE-declared vs spine-resolved) that must agree
      AND must carry the `check-slice-at-completeness` row.

  Synthetic substrate: NONE beyond the SHIPPED repo files -- both seams read
  shipped artifacts (the registry file the spine resolves, the flavor file the
  dispatcher resolves). No fixture authors the expected stack; the shipped
  artifact (or its absence) IS the contract under test.

  # AT-10 (PRIMARY): the DISTILL gate-out fact has ONE authoring locus (the
  #       canonical registry `nWave/waves/distill.yaml`, mirroring design.yaml +
  #       devops.yaml), and the WIRED spine resolves it FROM there to a gate-id
  #       sequence carrying `check-slice-at-completeness`. Two independent reads
  #       (registry-FILE-declared vs spine-resolved) agree, proving the
  #       registry -> dispatcher wiring -- the AT-completeness check auto-fires on
  #       the DISTILL return from the gate-stack, NOT from /nw-distill prose
  #       (closes KPI-3, CT-8). REUSES the slice-01 stdlib registry scanner + the
  #       spine resolver VERBATIM, parameterized to wave="distill".
  @slice-03 @feature-f-design-devops-review-gate @AT-10 @contract-shape:pure-function
  Scenario: The wired spine resolves the DISTILL gate-out stack from the canonical registry
    Given the canonical wave-contract registry file for the DISTILL wave is shipped in the repo
    When the dispatcher resolves the DISTILL gate-out stack from the registry as the default source
    Then the resolved gate-id sequence equals the DISTILL gate-out sequence the registry file declares
    And the resolved DISTILL gate-out stack includes the check-slice-at-completeness gate
