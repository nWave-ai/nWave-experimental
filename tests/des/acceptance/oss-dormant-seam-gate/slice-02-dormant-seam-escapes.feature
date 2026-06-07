@feature-oss-dormant-seam-gate @slice-02
Feature: A flagged dormant seam clears two honest, never-silent ways
  As an nWave operator finishing a slice at GREEN-phase under atdd_pure
  I want a flagged dormant seam to clear when I either add a real call-site
    (including indirect wiring) OR mark it as owned residue -- and the
    owned-residue clearing to be recorded, never silently swallowed
  So that I can honestly resolve a dormant-seam warning without either being
    forced to wire dead code OR hiding a deliberate residue behind a silent
    suppression (every escape stays loud and auditable -- the OSS non-halting
    ACL over the SF Published-Language)

  # slice-02 of oss-dormant-seam-gate -- THE TWO NEVER-SILENT ESCAPES (DISCUSS D5
  # + DESIGN D-4 + Per-Slice Companion slice-02). Layers the escapes on slice-01's
  # detection seam:
  #   escape (a) -- a real production call-site INCLUDING indirect wiring clears
  #     the seam (slice-01 already cleared the DIRECT from-import call; slice-02
  #     adds the INDIRECT attribute-call floor `import module; module.symbol()`).
  #     The deep binding-resolved precision (entry-point / registry) is slice-03.
  #   escape (b) -- a `# dormant-ok: <F-id>` owned-residue marker clears the seam
  #     AND records the clearing naming the owning F-id (auditable owned residue,
  #     never a silent suppression -- the key never-silent contract).
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): identical to
  # slice-01 -- the REAL `des dormant-seam-gate` composition-root CLI invoked as a
  # subprocess black box (`python -m des.cli.dormant_seam_gate`). The detector /
  # marker-scan / call-site resolution are NEVER imported-and-called at the step
  # boundary. The observable surface is the single-line JSON verdict on stdout
  # (now carrying an `escapes` record for escape b), the loud human warning on
  # stderr, and the process exit code.
  #
  # RED-for-right-reason (ADR-025 + ADR-028; verified empirically against shipped
  # slice-01 production 2026-06-07): slice-01 IGNORES the `# dormant-ok:` marker
  # (the marked symbol stays flagged `verdict: indeterminate`, named in the
  # warning, with NO escape record) AND resolves only the direct from-import call
  # shape (an attribute-call caller is NOT recognised, so the indirectly-wired
  # symbol is wrongly flagged dormant). The Then-steps assert CLEARED + RECORDED,
  # so they fail with a semantic AssertionError -- never a collection / import /
  # setup error (the step modules import only test-local types). The ATs PASS once
  # DELIVER lands the marker line-scan + the escape-record verdict surface + the
  # indirect-wiring call-site resolution.
  #
  # HARD INVARIANT (non-halting, KPI-2 guardrail): every escape outcome stays exit
  # 0; no scenario asserts a block / refuse. The escapes never introduce a halting
  # path.
  #
  # NON-VACUITY (perturbation-bound -- the escapes clear ONLY when their honest
  # condition is present):
  #   * a `# dormant-ok` marker on a NON-dormant (wired) symbol emits NO escape
  #     record (the symbol was never flagged, so there is nothing to escape -- a
  #     spurious record would be a false-positive suppression report);
  #   * a dormant seam with NO call-site and NO marker still warns (the slice-01
  #     contract, re-pinned as the escape control pole).
  #
  # SUT verdict model (C2 / C5 -- the escape decision table over a net-new
  # effectful public symbol):
  #   | call-site | marker | verdict for the symbol                         |
  #   | none      | none   | DORMANT -> warn-loud (control pole)            |
  #   | none      | yes    | CLEARED + RECORDED (escape b owned residue)   |
  #   | indirect  | none   | CLEARED, no record (escape a wiring floor)    |
  #   | direct    | yes    | not dormant; marker emits NO record (control) |
  #
  # CONTRACT-SHAPE (2026-05-15 mandate, machine-parseable):
  #   * the marker / indirect / unmarked scenarios are @contract-shape:bounded-change
  #     -- the verdict surface CHANGES in a bounded, named way (a symbol moves out
  #     of the flagged set and INTO an escape record, or stays flagged);
  #   * the wired-marker non-vacuity control is @contract-shape:unbounded-preservation
  #     -- the property is that NO escape record appears for a never-flagged symbol
  #     (preservation of the absence across the verdict surface).
  #
  # TAG SCHEME (strict-markers safe -- mirrors slice-01 + the sibling suites):
  # scenario @tags become dynamic pytest marks via pytest-bdd's tag pipeline; the
  # project's filterwarnings suppresses PytestUnknownMarkWarning so
  # --strict-markers does not reject them. Binding goes through the RELATIVE
  # `scenarios("../<feature>")` from the slice-02 steps module. Every step
  # decorator's literal text is UNIQUE within this feature directory (S1
  # step-text-uniqueness: slice-02 step literals are distinct from slice-01's).

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: An owned-residue marker clears the dormant seam and records who owns it
    Given a dormant effectful seam carrying a dormant-ok owned-residue marker
    When the developer runs the escape-aware dormant-seam gate at GREEN-phase
    Then the gate no longer flags the marked seam as dormant
    And the gate records the clearing naming the owning residue id
    And the escape-aware gate exits with code zero

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: An indirect wiring call-site clears the dormant seam
    Given a dormant effectful seam reached only by an indirect wiring call-site
    When the developer runs the escape-aware dormant-seam gate at GREEN-phase
    Then the gate no longer flags the indirectly-wired seam as dormant
    And the escape-aware gate exits with code zero

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A marker on a seam that production code already calls records nothing
    Given a wired effectful seam that also carries a dormant-ok owned-residue marker
    When the developer runs the escape-aware dormant-seam gate at GREEN-phase
    Then the gate records no escape for the already-wired seam
    And the escape-aware gate exits with code zero

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A dormant seam with no call-site and no marker still warns loudly
    Given a dormant effectful seam with neither a call-site nor a marker
    When the developer runs the escape-aware dormant-seam gate at GREEN-phase
    Then the gate still names the unescaped seam in its loud warning
    And the escape-aware gate exits with code zero
