@feature-sustainable-test-suite
Feature: A maintainer authors acceptance tests in nWave's shared business vocabulary
  As an nWave maintainer authoring a feature's acceptance tests
  I want one shared business-language step vocabulary that drives the system
    behind the scenes, instead of impl-bound per-feature scaffolding
  So that my scenarios read in nWave's ubiquitous language, survive an
    implementation refactor untouched, and reuse the same steps across features

  # slice-01 (walking skeleton) of sustainable-test-suite — the TWO-LAYER AUTHORED
  # business-language acceptance-test structure (Gojko/GOOS canon; DESIGN CORRECTION
  # DDD-1C..DDD-5C/8C/10C, 2026-06-22b). This keystone proves the CORRECT concept:
  # a reusable business-language layer the acceptance-test-designer AUTHORS, NOT a
  # generic config-parameterized engine (the indicted anti-pattern; DDD-1R..10R
  # superseded). There is NO vocabulary.yaml / bindings.yaml, NO generic_framework.
  #
  # THE TWO LAYERS (research Findings 1.2/1.10/1.12):
  #   * L1 — these business-language scenarios (the WHAT): declarative steps in
  #     nWave's ubiquitous language (feature-delta · slice plan · accept · reject ·
  #     the gate's verdict in its own words). Implementation-SILENT — the wording
  #     does NOT change if the implementation does (Cucumber litmus, Finding 1.8).
  #   * L2 — an AUTHORED automation/driver layer (the HOW): a GOOS-style
  #     `SlicePlanGateDriver` behind a `GatewayDriver` interface that drives the
  #     real nWave gate SUBCUTANEOUSLY (below any UI). The driver owns every
  #     impl specific — subprocess, argv, exit code, JSON verdict parse.
  #
  # REAL nWAVE BEHAVIOUR (DDD-5C: ONE real existing AT re-expressed two-layer): the
  # SHIPPED `des validate-feature-delta --require-slice-plan` gate. A maintainer
  # submits a feature-delta with a Slice Plan; the gate ACCEPTS a well-formed plan
  # and REJECTS a malformed / missing / value-less plan, naming the defect in its
  # own closed verdict vocabulary (accepted · missing-slice-plan ·
  # malformed-slice-plan · malformed-wave-heading · rejected-infra-only). Real,
  # deterministic, git-free, Python-only, observable. NOT the under-construction
  # `--require-sustainability` gate (slice-03 owns that) — a fully-shipped sibling.
  #
  # REFACTOR-RESILIENCE (DDD-1C/10C, Finding 1.2): the L1 scenarios name observable
  # business outcomes only; an implementation change to the gate is absorbed entirely
  # by the L2 driver. Scenario "An implementation refactor of the gate leaves the
  # business-language scenarios untouched" demonstrates this directly — the driver
  # is re-pointed at a second invocation surface and the SAME L1 steps still pass.
  #
  # AUTHORED REUSE (DDD-2C/8C, Findings 1.7/1.9): the SECOND feature's scenario
  # reuses the SAME declarative step TEXT, binding to ONE authored step definition —
  # reuse emerges in the authored vocabulary organized by domain concept, never from
  # added configuration.
  #
  # PBT+UNIVERSE (DDD-5C PREFERRED-where-quantifiable, Findings 2.3/2.4): the gate's
  # decision is a function of the plan SHAPE over a closed observable verdict
  # Universe, so the `@property` scenario expresses it as a property over a generated
  # plan-shape domain (model=the closed verdict Universe; generated plan shapes=the
  # When; the verdict-matches-shape invariant=the Then). The walking-skeleton happy
  # path stays example-based (layer-3 subprocess wiring proof; Mandate-9/11).
  #
  # DRIVING PORT (Mandate-13, Layer 3 subprocess composition root): the SHIPPED gate
  # `python -m des validate-feature-delta --require-slice-plan --format=json` is the
  # SUT, driven subcutaneously by the L2 driver. No production module is imported and
  # called at the step boundary; feature-delta fixtures are hermetic under tmp_path.
  #
  # Active-RED (ADR-025/028, atdd_pure): at HEAD the AUTHORED two-layer harness does
  # NOT exist — the `GatewayDriver` interface + the `SlicePlanGateDriver` concrete
  # driver + the shared business-step vocabulary are RED scaffolds that raise a clean
  # AssertionError (MISSING_FUNCTIONALITY) the moment a step drives the gate, NEVER an
  # ImportError. DELIVER's A_GREEN AUTHORS the driver + vocabulary (the shipped gate
  # already exists, so the green driver invokes it) and REMOVES the now-unused
  # generic_framework.py + its data dir. DELIVER does NOT unskip anything.

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A maintainer's well-formed slice plan is accepted in the gate's own words
    Given a maintainer has authored a feature-delta with a well-formed slice plan
    When the maintainer submits the feature-delta to the slice-plan gate
    Then the gate accepts the feature-delta
    And the gate's verdict reads "accepted" in its own words

  @slice-01 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A maintainer's feature-delta with no slice plan is rejected, naming the absence
    Given a maintainer has authored a feature-delta with no slice plan
    When the maintainer submits the feature-delta to the slice-plan gate
    Then the gate rejects the feature-delta
    And the gate's verdict reads "missing-slice-plan" in its own words

  # NOTE: the malformed-slice-plan and rejected-infra-only reject paths are covered
  # by the @property scenario below (it sweeps EVERY recognised shape and asserts the
  # verdict each determines, incl. both reject verdicts). slice-01 keeps ONE example
  # reject path (missing-slice-plan, above) at layer-3 + the property over the full
  # Universe, holding the slice within the carpaccio ceiling of 5 ATs.

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A second feature reuses the same business-language steps to author its gate check
    Given a maintainer has authored a feature-delta with a well-formed slice plan
    And a second feature's maintainer has authored a feature-delta with a well-formed slice plan
    When the maintainer submits both feature-deltas to the slice-plan gate
    Then the gate accepts both feature-deltas
    And the same authored business-language steps served both features without re-authoring

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: An implementation refactor of the gate leaves the business-language scenarios untouched
    Given a maintainer has authored a feature-delta with a well-formed slice plan
    And the gate's implementation is exercised through a refactored invocation surface
    When the maintainer submits the feature-delta to the slice-plan gate
    Then the gate accepts the feature-delta
    And the gate's verdict reads "accepted" in its own words

  # @property (DDD-5C): a property over the closed slice-plan-shape Universe — the
  # step bodies sweep EVERY recognised shape and assert the invariant for all, not one
  # example. Gherkin has no `Property:` keyword; the `@property` tag carries the PBT
  # semantic and the step definitions realise the finite-domain sweep.
  @slice-01 @property @driving_port @real-io @contract-shape:bounded-change
  Scenario: The gate's verdict is a deterministic function of the slice-plan shape, drawn from its closed verdict vocabulary
    Given the maintainer considers every recognised slice-plan shape
    When the maintainer submits the feature-delta to the slice-plan gate
    Then the gate's verdict for that shape is the one the shape determines
    And every verdict the gate emits is drawn from its closed verdict vocabulary
    And the accept-or-reject decision agrees with the verdict for that shape
