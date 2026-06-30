@feature-fix-wave-dispatch-marker-contract @slice-02
Feature: The wave-entry marker contract is declared once and mechanically guarded
  As an nWave maintainer who needs the test suite to actually exercise the
    dispatch shape the command templates ship
  I want the DES-WAVE-only entry shape to pass the production gate AND the
    entry-marker contract to be declared in one canonical home that the four
    command templates provably agree with
  So that the fixture-theater drift that hid the bug -- a green test validating
    a classic-marker path no template takes -- is eliminated and cannot recur

  # slice-02 of fix-wave-dispatch-marker-contract (depends-on slice-01). Root
  # Cause B: no SSOT reconciled the marker shape the templates EMIT (DES-WAVE
  # alone) with the shape the spine REQUIRES, and the slice-07d AT fixture
  # carried the full classic set so it never reached the :146 hinge.
  #
  # DRIVING SURFACES (Mandate-13):
  #   AT-2a -> Layer 3 composition: the REAL PreToolUseService.validate driven
  #     with the DES-WAVE-only shape EXACTLY as a template ships it.
  #   AT-2b -> the drift guard: pure Python + filesystem reconciliation over the
  #     entry-marker Contract SSOT block (flow-v2-design.md §22.7.A) + the four
  #     nWave/tasks/nw/{discuss,design,devops,distill}.md templates. Git-free,
  #     target-machine-agnostic, no new tool dependency. A closed finite file set
  #     -> example/parametrize treatment (NOT PBT, per the falsifier-gate).
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip):
  #   AT-2a -- the slice-01 wave_entering exemption is not shipped at HEAD, so
  #     the :146 veto fires on the template-shipped DES-WAVE-only entry -> BLOCK
  #     WAVE_MARKER_BYPASS where ALLOW is expected (semantic AssertionError).
  #   AT-2b -- the canonical entry-marker Contract SSOT block does not exist in
  #     flow-v2-design.md at HEAD (it is authored in this slice's DELIVER doc
  #     delta) -> the drift guard reports the absent SSOT block (semantic
  #     AssertionError). GREEN once DELIVER authors the §22.7.A Contract SSOT.
  # No @skip, no import / collection / setup error.
  #
  # SUT STATE MACHINE (C2): see composition_slice_marker_contract_02.py.

  # AT-2a -- the production shape passes via the real gate (the test the original
  # slice-07d fixture should have been: exercises the SHIPPED shape, not the
  # classic-marker shape Root Cause B's fixture took).
  @slice-02 @driving_port @real-io @us-contract-ssot @contract-shape:bounded-change
  Scenario Outline: The DES-WAVE-only shape a template ships passes the real gate for <wave>
    Given the <wave> wave is active with the template-shipped entry shape
    When the template-shipped dispatch is checked
    Then the template-shipped entry shape is allowed

    Examples:
      | wave    |
      | design  |
      | discuss |

  # AT-2b -- the drift guard: the entry-marker contract SSOT, the four command
  # templates, and the AT-2a fixture must all agree (closes Root Cause B
  # mechanically -- the SSOT<->emitter<->fixture tie the S5 "mechanical grep
  # contract" never built).
  @slice-02 @driving_port @real-io @us-contract-ssot @error @contract-shape:unbounded-preservation
  Scenario: The entry-marker contract, the command templates, and the fixture agree
    Given the entry-marker SSOT file and the four command templates exist in the repo
    When the entry-marker contract and the command templates are reconciled
    Then the contract, the templates, and the fixture agree with no drift
