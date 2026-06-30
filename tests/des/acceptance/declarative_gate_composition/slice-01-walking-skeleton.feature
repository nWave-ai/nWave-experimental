@feature-f-declarative-gate-composition @slice-01 @walking-skeleton @real-io @contract-shape:bounded-change @JOB-026
Feature: The DISCUSS wave gate stack is declared as data and iterated by the generic handlers

  A maintainer declares the DISCUSS wave's gate-in / gate-out stack as an ordered
  gate-ID list in wave_gate_stacks.discuss, and the generic PreToolUse / SubagentStop
  handlers select the active-wave stack off the wave-active anchor and iterate the
  catalog gates in declared order, blocking at the first veto -- behavior-preserved
  against the imperative DISCUSS branches, with each gate's specific veto-reason and
  recovery carried through -- so changing the DISCUSS gate stack becomes a one-line
  list edit instead of handler surgery.

  Driving surface: the REAL PreToolUseService / SubagentStopService via the
  production composition root (Layer 3 composition); the REAL resolve_wave_gate_stack
  pure seam over the shipped atdd_pure.yaml; the REAL des verify-discuss-review
  subcommand (Layer 3 subprocess). Observables: the HookDecision (block + reason +
  carried recovery_suggestions) and the declared gate stack as data.

  # AT-1: the DISCUSS gate-IN stack is declared as data and iterated, halting at the veto.
  # AT-2: the DISCUSS gate-OUT stack is declared as data and iterated, halting at the veto.
  @AT-1 @AT-2 @slice-01
  Scenario Outline: The declared DISCUSS <boundary> stack is iterated and halts at the first veto
    Given the DISCUSS gate stack is declared and the <site> precondition is armed
    When the active discuss-wave dispatch iterates the declared <boundary> stack
    Then the declared discuss <boundary> stack is the source of the veto
    And the <boundary> veto still blocks the dispatch
    And the block names the <boundary> reason

    Examples:
      | boundary | site             |
      | gate-in  | DISCUSS_GATE_IN  |
      | gate-out | DISCUSS_GATE_OUT |

  # AT-4: each composed gate's SPECIFIC veto-reason + recovery is carried through the generic iteration.
  @AT-4 @slice-01
  Scenario Outline: The carried recovery names the fix specific to the <site> veto
    Given the DISCUSS gate stack is declared and the <site> precondition is armed
    When the active discuss-wave dispatch iterates the declared <boundary> stack
    Then the block carries the recovery with parity to the imperative branch

    Examples:
      | boundary | site             |
      | gate-in  | DISCUSS_GATE_IN  |
      | gate-out | DISCUSS_GATE_OUT |

  # AT-2 companion: the PO-review consumer veto is promoted to its own catalog gate_id (OB-2).
  @AT-2 @slice-01
  Scenario: The PO-review consumer veto is a declared catalog gate
    Given the DISCUSS gate stack is declared and the DISCUSS_GATE_OUT precondition is armed
    When the active discuss-wave dispatch iterates the declared gate-out stack
    Then the PO-review consumer veto is a registered catalog gate

  # Run-ORDER AT (§22.0 MEDIUM advisory): the wave gate-in composition runs BEFORE
  # the wave-agnostic dispatch.pre composition -- the two-composition order, not each
  # in isolation (a DISCUSS precondition must fire before carpaccio).
  @AT-1 @run-order @slice-01
  Scenario: The wave gate-in composition runs before the wave-agnostic dispatch
    Given the DISCUSS gate stack is declared and the DISCUSS_GATE_IN precondition is armed
    When the active discuss-wave dispatch iterates the declared gate-in stack
    Then the wave gate-in stack composes before the wave-agnostic dispatch
