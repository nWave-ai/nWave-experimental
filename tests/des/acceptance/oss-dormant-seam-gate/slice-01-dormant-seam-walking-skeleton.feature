@feature-oss-dormant-seam-gate @slice-01
Feature: A net-new effectful seam with no production call-site is warned loudly without blocking the wave
  As an nWave operator finishing a slice at GREEN-phase under atdd_pure
  I want the spine to mechanically catch a net-new effectful symbol that has
    no production call-site, surfaced as a loud INDETERMINATE warning naming
    that dormant seam
  So that a feature that passed every per-slice gate cannot ship dormant-green
    theater -- while the warning never blocks the move (OSS is hooks-only and
    non-halting, an ACL over the SF Published-Language)

  # slice-01 of oss-dormant-seam-gate -- THE WALKING SKELETON (DISCUSS D2 +
  # DESIGN Per-Slice Companion slice-01). The thinnest honest end-to-end
  # vertical: net-new-delta detection -> no-call-site witness -> INDETERMINATE
  # loud-warn naming the seam -> non-halting (exit 0). No escapes (slice-02), no
  # binding-resolved precision (slice-03), no static-tree scoping (slice-04).
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
  # `des dormant-seam-gate` composition-root CLI, invoked as a subprocess black
  # box (`python -m des.cli.dormant_seam_gate`). The detector function is NEVER
  # imported-and-called at the step boundary (that would be a Layer-1 unit test
  # masquerading as an AT). The observable surface is the single-line JSON
  # verdict on stdout, the loud human warning on stderr, and the process exit
  # code. (DESIGN slice-01 row also names the real GREEN-phase hook tap; for the
  # walking-skeleton the CLI composition root IS the real entry point the hook
  # invokes -- driving it directly as a subprocess proves the same wiring without
  # an extra hook-protocol indirection. The hook-tap leg is a slice-02+ concern.)
  #
  # RED-for-right-reason (ADR-025 + ADR-028, pre-DELIVER fail-for-right-reason
  # gate): `des.cli.dormant_seam_gate` does NOT exist on disk yet, so the
  # subprocess fails to import the module and produces NO JSON verdict. The
  # Then-steps assert against that absent verdict and fail with a semantic
  # AssertionError (the verdict could not be parsed / the named seam is absent /
  # the exit code is non-zero) -- never a collection / import / setup error in
  # the test process itself (the step modules import only test-local types). The
  # ATs PASS once DELIVER lands the pure detector + the changed-symbol port +
  # the composition-root CLI.
  #
  # HARD INVARIANT (non-halting, KPI-2 guardrail): the gate only WARNS + ALLOWS
  # on a dormant seam. No scenario asserts a block / refuse. The dormant-seam
  # INDETERMINATE warning stays exit 0 (distinct from the cannot-evaluate exit-3
  # INDETERMINATE, which is a slice-02+ degrade-LOUD concern).
  #
  # NON-VACUITY (perturbation-bound): the dormant-fires scenario is paired with a
  # CLEAN control -- a net-new effectful symbol WITH a real production call-site
  # produces a clean verdict and NO warning. The warning is therefore not
  # vacuously always-on; it is bound to the presence/absence of the call-site.
  #
  # SUT verdict model (C2 / C5): per net-new effectful public symbol the gate
  # resolves to {dormant (no resolved production call-site -> warn-loud), wired
  # (>=1 production call-site -> clean)}. The materially-distinct decision-table
  # rows (C5): a net-new effectful symbol with zero call-sites -> INDETERMINATE
  # warning naming it; the same shape WITH a call-site -> clean.
  #
  # TAG SCHEME (strict-markers safe -- mirrors the sibling suites
  # oss-upstream-gate-pair-traceability / oss-hook-side-phase-injection):
  # scenario @tags are converted to dynamic pytest marks by pytest-bdd's tag
  # pipeline; the project's filterwarnings (pyproject.toml) suppresses
  # PytestUnknownMarkWarning so --strict-markers does not reject them. Binding
  # goes through pytest-bdd's scenario machinery via the RELATIVE
  # `scenarios("../<feature>")` from the steps/ module (the proven-collecting
  # form). The immutable contract-shape tag is machine-parseable per the
  # 2026-05-15 mandate.

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A net-new effectful seam with no production call-site is named in a loud warning that does not block the wave
    Given a feature whose net-new delta adds an effectful public symbol that no production code calls
    When the developer runs the dormant-seam gate against that feature at GREEN-phase
    Then the gate names the dormant seam in its loud warning
    And the gate lets the wave proceed without blocking
    And the gate exits with code zero

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A net-new effectful seam that production code already calls produces no warning
    Given a feature whose net-new delta adds an effectful public symbol that production code calls
    When the developer runs the dormant-seam gate against that feature at GREEN-phase
    Then the gate stays silent about the wired seam
    And the gate exits with code zero

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The dormant-seam warning is surfaced as a non-halting indeterminate verdict
    Given a feature whose net-new delta adds an effectful public symbol that no production code calls
    When the developer runs the dormant-seam gate against that feature at GREEN-phase
    Then the gate reports an indeterminate verdict that warns without refusing the wave
    And the gate exits with code zero
