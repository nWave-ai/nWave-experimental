@feature-f-declarative-gate-composition @slice-02 @real-io @contract-shape:bounded-change @JOB-026
Feature: The generic iterator honors declared order, fails closed on unknown gates, degrades loud, and does not regress

  A maintainer reordering the declared DISCUSS composition gets iteration-order =
  declared-order with zero code change; a typo'd gate-id fails closed named (never
  a silent skip); a composed gate's INDETERMINATE degrades LOUD; and the already-wired
  event compositions plus the classic flavor are not regressed.

  Driving surface: the REAL flavor_dispatcher.dispatch_lifecycle_event +
  resolve_wave_gate_stack seams (Layer 3 composition), over a real flavor file with
  a real in-process gate_invoker Port. Observable: the CompositionResult (ordered
  gate_results, halted, blocking_gate_id) + the carried verdict + recovery.

  # AT-3: reordering the declared rows changes which gate vetoes first -- zero code change.
  @AT-3 @slice-02
  Scenario Outline: The gate at declared position one vetoes first (<first> before <second>)
    Given a DISCUSS gate-in stack declared in the order <first> then <second>
    When the declared stack is iterated
    Then the gate <first> vetoes first

    Examples:
      | first      | second     |
      | alpha-gate | beta-gate  |
      | beta-gate  | alpha-gate |

  # AT-5: a declared gate_id absent from the catalog fails closed, named, never skipped.
  @AT-5 @slice-02
  Scenario Outline: A declared uncatalogued gate id <gate_id> fails closed and is named
    Given the declared composition carries the uncatalogued gate id <gate_id>
    When the unknown gate is iterated
    Then the uncatalogued gate fails closed and is named

    Examples:
      | gate_id       |
      | cohesion-mec  |
      | totally-bogus |

  # AT-6: a composed gate whose mechanism could not run degrades LOUD (INDETERMINATE).
  @AT-6 @slice-02
  Scenario: A composed gate that cannot run degrades loud
    Given the declared composition carries the gate carpaccio-slice-gate whose mechanism cannot run
    When the indeterminate gate is iterated
    Then the indeterminate gate degrades loud

  # AT-7: the already-wired event compositions + classic flavor are not regressed by the lift.
  @AT-7 @slice-02
  Scenario Outline: The shipped <flavor> flavor event compositions are not regressed
    Given the shipped flavor <flavor>
    When the shipped event compositions are resolved
    Then the shipped event compositions iterate unchanged

    Examples:
      | flavor    |
      | atdd_pure |
      | classic   |
