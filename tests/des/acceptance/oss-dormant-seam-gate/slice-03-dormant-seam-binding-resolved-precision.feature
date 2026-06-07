@feature-oss-dormant-seam-gate @slice-03
Feature: A registry-dispatched seam is not false-flagged, because the gate resolves bindings
  As an nWave operator finishing a slice at GREEN-phase under atdd_pure
  I want a net-new effectful symbol wired only by an entry-point / registry
    registration (with no source call-site by design) to be recognised as
    wired -- and two same-named symbols to be kept distinct by their module --
  So that the gate produces zero false-positives on dispatched symbols and zero
    false-negatives on name-collisions: the dormant-seam warning stays trusted
    (false-positive noise would erode trust in the gate itself -- KPI-3)

  # slice-03 of oss-dormant-seam-gate -- BINDING-RESOLVED PRECISION (DISCUSS D6 +
  # DESIGN D-3 / Reuse R6 + Per-Slice Companion slice-03). Layers binding-resolved
  # precision on slice-01/02's detection + call-site seams:
  #   no false-positive -- a net-new effectful symbol wired ONLY by a
  #     `[project.entry-points."nwave.lang.adapter"]` registration (the canonical
  #     OSS anchor; no direct/attribute source call-site BY DESIGN) must NOT be
  #     flagged dormant; the gate resolves the registration INTO the call-site set
  #     (mirroring the real `discovery.py` resolve-and-probe seam, on SOURCE
  #     rather than installed metadata -- see the entry-point-resolution note).
  #   no false-negative -- two distinct `main` symbols in different modules are
  #     distinct identities; a call to one is NOT a call-site for the other
  #     (module-qualified identity, not the bare name `main`).
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): identical to
  # slice-01/02 -- the REAL `des dormant-seam-gate` composition-root CLI invoked as
  # a subprocess black box (`python -m des.cli.dormant_seam_gate`). The detector,
  # the entry-point resolution, and the discovery resolve-and-probe seam are NEVER
  # imported-and-called at the step boundary. Observable surface: the single-line
  # JSON verdict on stdout, the loud human warning on stderr, the process exit code.
  #
  # ANCHOR REALISM (DISCUSS D3 / DESIGN D-3 / R6): the entry-point registration is
  # the REAL form `discovery.py` resolves -- a pyproject
  # `[project.entry-points."nwave.lang.adapter"]` table whose value is a
  # `module.path:Symbol` reference (the repo's own `_conformance_fixture =
  # "scripts...:ConformanceFixtureLanguageAdapter"` shape). This proves the ACTUAL
  # false-positive class, not a synthetic stand-in.
  #
  # RED-for-right-reason (ADR-025 + ADR-028; verified against shipped slice-02
  # production 2026-06-07): slice-02 resolves ONLY source call-sites (direct
  # from-import + indirect attribute-call). It does NOT parse the pyproject
  # entry-point group, so an entry-point-only registered symbol has NO resolved
  # call-site and is wrongly flagged dormant. The Then-step asserts the symbol is
  # CLEARED -> fails with a semantic AssertionError -- never a collection / import /
  # setup error (the step modules import only test-local types). The AT PASSES once
  # DELIVER lands the entry-point-group resolve-into-call-site read. (The
  # name-collision scenario may be GREEN-on-arrival -- slice-02 already keys on
  # module-qualified identity -- and stands as the no-false-negation regression
  # guard across slice-03's resolution change.)
  #
  # HARD INVARIANT (non-halting, KPI-2 guardrail): every precision outcome stays
  # exit 0; no scenario asserts a block / refuse.
  #
  # NON-VACUITY (perturbation-bound -- the resolution clears ONLY on a real
  # registration / call-site):
  #   * a genuinely-dormant symbol that is NEITHER source-called NOR entry-point-
  #     registered STILL warns (KPI-1 recall control -- the entry-point clear is
  #     not vacuously always-on);
  #   * in the collision fixture the dormant same-named symbol still warns -- the
  #     presence of a wired namesake does NOT vacuously clear it.
  #
  # SUT verdict model (C2 / C5 -- the precision decision table over a net-new
  # effectful public symbol):
  #   | wiring                          | verdict for the symbol                |
  #   | entry-point registration only   | WIRED (cleared -- resolved call-site) |
  #   | none (no call-site, no registry)| DORMANT -> warn-loud (recall control) |
  #   | same name, source call-site     | WIRED (cleared -- module-qualified)   |
  #   | same name, no call-site         | DORMANT -> warn-loud (no false-neg)   |
  #
  # CONTRACT-SHAPE (2026-05-15 mandate, machine-parseable):
  #   * the entry-point + name-collision scenarios are
  #     @contract-shape:bounded-change -- the flagged set CHANGES in a bounded,
  #     named way (a symbol moves out of / stays in the flagged set by resolved
  #     identity);
  #   * the unregistered recall control is @contract-shape:unbounded-preservation
  #     -- the property is that the warning is PRESERVED for a genuinely-dormant
  #     symbol regardless of the precision changes (the clear does not leak onto it).
  #
  # TAG SCHEME (strict-markers safe -- mirrors slice-01/02 + the sibling suites):
  # scenario @tags become dynamic pytest marks via pytest-bdd's tag pipeline; the
  # project's filterwarnings suppresses PytestUnknownMarkWarning so
  # --strict-markers does not reject them. Binding goes through the RELATIVE
  # `scenarios("../<feature>")` from the slice-03 steps module. Every step
  # decorator's literal text is UNIQUE within this feature directory (S1
  # step-text-uniqueness: slice-03 step literals are distinct from slice-01/02's).

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A symbol wired only by an entry-point registration is not flagged dormant
    Given a dormant effectful seam wired only by a nwave.lang.adapter entry-point registration
    When the developer runs the binding-resolving dormant-seam gate at GREEN-phase
    Then the gate resolves the entry-point wiring and clears the dispatched seam
    And the binding-resolving gate exits with code zero

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Two same-named symbols are kept distinct by their defining module
    Given two same-named effectful seams in different modules where production calls only one
    When the developer runs the binding-resolving dormant-seam gate at GREEN-phase
    Then the gate flags the uncalled namesake and clears the called namesake by module identity
    And the gate names the uncalled namesake in its loud warning
    And the binding-resolving gate exits with code zero

  @slice-03 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A seam with neither a call-site nor a registration still warns loudly
    Given a dormant effectful seam with neither a call-site nor an entry-point registration
    When the developer runs the binding-resolving dormant-seam gate at GREEN-phase
    Then the gate still names the unregistered seam in its loud warning
    And the binding-resolving gate exits with code zero
