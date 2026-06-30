@feature-sustainable-test-suite
Feature: The readiness gate fires the sustainability content gate before dispatch

  slice-06 (gate-wiring) of sustainable-test-suite. Slices 02-04 shipped the
  `des validate-feature-delta --require-sustainability` content gate as a working
  CLI, but NO wave gate-stack invoked it, so it never fired automatically
  ("catalogued != wired"). This feature wires a 7th invariant SUSTAINABILITY into
  the single-invocation aggregate readiness gate
  (`des verify-readiness-pre-dispatch`, wired into the atdd_pure flavor gate_stack
  at dispatch.pre), mirroring invariant 6 REUSE_FIRST: it calls
  `validate_sustainability_content` on the feature-delta and FAILS readiness when
  the `## Test Reuse & Consolidation Analysis` section is declared-but-missing or
  malformed.

  As a maintainer who owns the sustainable-test-suite guarantee
  I want the DELIVER-entry readiness gate to FIRE the sustainability content
  check automatically before a crafter dispatch
  So that the shipped sustainability gate cannot sit catalogued-but-unwired and
  silently never fire (the gap that let slices 02-04 ship a never-invoked gate)

  Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED readiness gate
  `des verify-readiness-pre-dispatch` run as a real subprocess on a hermetic
  tmp_path workspace whose feature-delta satisfies the SIX pre-existing readiness
  invariants (slice-plan, scenario tags, AT-review ledger, gate-output, pre-commit
  scope, reuse-first). The sustainability section is the ONLY variable -- any
  refusal is attributable to the 7th invariant alone. The subprocess is the SUT;
  no production module is imported at the step boundary.

  Active-RED: at HEAD `verify-readiness-pre-dispatch` ships SIX invariants (no
  sustainability check). A feature-delta whose sustainability section is
  declared-but-missing/malformed therefore CLEARS readiness on that axis, so the
  must-block scenario fails with a clean AssertionError (MISSING_FUNCTIONALITY:
  the gate does not refuse + the `sustainability` invariant id never appears),
  NOT an ImportError. DELIVER adds the 7th invariant and turns it GREEN.

  @slice-06 @walking_skeleton @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A dispatch-ready feature missing its sustainability section is refused
    Given a dispatch-ready feature whose feature-delta carries no sustainability section
    When the readiness gate runs at dispatch readiness
    Then the readiness gate refuses the dispatch on the sustainability dimension
    And the sustainability readiness invariant is reported as failed
    And the sustainability remediation names the Test Reuse & Consolidation section

  @slice-06 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A dispatch-ready feature with a malformed sustainability section is refused
    Given a dispatch-ready feature whose feature-delta carries a malformed sustainability section
    When the readiness gate runs at dispatch readiness
    Then the readiness gate refuses the dispatch on the sustainability dimension
    And the sustainability readiness invariant is reported as failed

  @slice-06 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A dispatch-ready feature with a well-formed sustainability section clears the dimension
    Given a dispatch-ready feature whose feature-delta carries a well-formed sustainability section
    When the readiness gate runs at dispatch readiness
    Then the sustainability readiness invariant is reported as satisfied

  @slice-06 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A methodology-exempt feature clears the sustainability dimension without a populated section
    Given a dispatch-ready feature whose feature-delta carries a methodology-exempt sustainability marker
    When the readiness gate runs at dispatch readiness
    Then the sustainability readiness invariant is reported as satisfied
