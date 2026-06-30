@feature-f-wave-contract-coherence @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
Feature: The DISCUSS wave gate stack is authored once in the registry and the dispatcher fires it from there

  A maintainer authors the DISCUSS wave's gate-in / gate-out stack ONCE in the
  canonical, flavor-independent wave-contract registry (nWave/waves/discuss.yaml),
  and the dispatcher resolves the DISCUSS gate stack FROM the registry as the
  default source -- behaviour byte-identical to the flavor-sourced stack today --
  so the gate-stack fact has one authoring locus the prose can point at instead of
  the flavor-private copy.

  Driving surface (Mandate-13 driving-port-only): the REAL wired spine
  wave_gate_stack_dispatch.resolve_stack read over the SHIPPED
  nWave/waves/discuss.yaml registry file from the repo (Layer 3 composition through
  its real read path -- the entry the live PreToolUse / SubagentStop callers use).
  Observable: the ordered gate-id sequence the dispatcher resolves for the DISCUSS
  gate-in / gate-out boundaries. No production module is imported-and-called for its
  business logic -- only the REAL resolution seam reads the SHIPPED registry file.

  # AT-1: the canonical registry file for DISCUSS exists and is schema-valid --
  #       it carries the gate_stack SSOT with both gate-in and gate-out boundaries.
  @slice-01 @feature-f-wave-contract-coherence @AT-1
  Scenario: The canonical DISCUSS wave-contract registry declares the gate stack
    Given the canonical wave-contract registry file for the DISCUSS wave is shipped in the repo
    When the maintainer reads the DISCUSS wave-contract from the registry
    Then the DISCUSS wave-contract declares a gate stack with a gate-in and a gate-out boundary

  # AT-2: the dispatcher resolves the DISCUSS gate-in and gate-out stacks FROM the
  #       registry as the default source (not the flavor-private copy).
  @slice-01 @feature-f-wave-contract-coherence @AT-2
  Scenario Outline: The dispatcher resolves the DISCUSS <boundary> stack from the registry
    Given the canonical wave-contract registry file for the DISCUSS wave is shipped in the repo
    When the dispatcher resolves the DISCUSS <boundary> stack from the registry as the default source
    Then the resolved <boundary> stack is sourced from the registry and lists at least one gate

    Examples:
      | boundary |
      | gate-in  |
      | gate-out |

  # AT-3: the wired spine resolves the DISCUSS stack to the SAME gate-id sequence
  #       the registry FILE declares -- two independent reads (registry-FILE-declared
  #       vs spine-resolved) agree, proving the registry -> dispatcher wiring end-to-end
  #       (slice-06 retarget: "in force today" is now the wired spine, not the deleted
  #       flavor-private stack).
  @slice-01 @feature-f-wave-contract-coherence @AT-3
  Scenario Outline: The wired spine resolves the DISCUSS <boundary> stack to the registry-declared sequence
    Given the canonical wave-contract registry file for the DISCUSS wave is shipped in the repo
    When the dispatcher resolves the DISCUSS <boundary> stack from the registry as the default source
    Then the resolved gate-id sequence equals the DISCUSS <boundary> sequence in force today

    Examples:
      | boundary |
      | gate-in  |
      | gate-out |
