@feature-fix-robustness-pbt-density-gate @slice-05 @wiring @driving_port @real-io
Feature: The robustness density gate is wired into the spine so a slice cannot exit DISTILL while a declared unbounded input domain remains uncovered shallow or unfalsifiable
  As an nWave framework developer running the atdd_pure spine
  I want the robustness density gate CLI to be wired into the AT-review
    verdict producer that DISTILL exits through, into the SubagentStop hook
    chain that the slice dispatch passes through, and into the framework
    catalog quality_gates registry that downstream tooling inspects, so that
    a slice whose declared unbounded input domain coverage or genuineness
    layers fail mechanically blocks the dispatch, the gate's own composition
    root is itself probed end-to-end against a real sub-agent dispatch never
    a mocked one, and the gate is exercised against a real design component
    manifest emitted by the manifest producer never only hand-authored fixtures
  So that the wiring slice ships only when the complete blocking gate
    layers one plus two plus three demos end-to-end, the gate's own
    composition root cannot ship as a registration that exists but is never
    exercised which is the fixture-only-wiring defect the gate exists to
    prevent, and the cross-feature seam against the design manifest producer
    is a demonstrated seam not a calendar dependency

  # carpaccio slice-05 (DESIGN slice plan, ## Wave: DISCUSS / [REF] Slice Plan).
  # WIRING slice -- last by design (feature-delta § 6 line 410). Builds on
  # slice-01 walking-skeleton parser, slice-02 empty-declaration guard,
  # slice-03 genuineness layers 1+3, and slice-04 genuineness layer 2 (mutmut).
  # Slice-05 ships only when the COMPLETE blocking gate (layers 1 + 2 + 3) is
  # green so it demos end-to-end against the full gate, not a partial one.
  #
  # CONTRACT SOURCE: this slice is authored against the feature-delta
  # `docs/feature/fix-robustness-pbt-density-gate/feature-delta.md` section 6
  # slice-05 row and section 6 grounding subsection ("Slice-05 wiring --
  # concrete grounding (review point S2)" lines 425-462). Three ATs:
  #   AT1 (at_review_verdict integration): the real DISTILL-exit AT-review
  #        verdict producer `scripts/cli/at_review_verdict.py` consults the
  #        robustness density gate CLI exit code; an exit-zero CLI verdict
  #        lets the verdict producer write an APPROVED ATReviewVerdict
  #        ledger record, an exit-nonzero CLI verdict blocks the producer
  #        from writing the APPROVED record. The integration surface is
  #        the producer's `record_at_review_verdict` /
  #        `record_review_outcome` path -- the gate CLI runs at DISTILL-exit
  #        and its exit code gates the verdict write.
  #   AT2 (live SubagentStop hook chain, B4): a real sub-agent dispatch
  #        passes through the real SubagentStop hook chain; the hook chain
  #        invokes the robustness density gate CLI for the dispatched slice;
  #        a CLI exit-one verdict mechanically blocks the dispatch outcome
  #        from completing. NEVER MOCKED -- the registration is the gate's
  #        own composition root and an unprobed registration is the very
  #        fixture-only-shipping defect the gate exists to prevent.
  #        Inverse of slice-04 M2 (slice-04 MUST NOT touch live mutmut;
  #        slice-05 AT2 MUST NOT mock the hook chain).
  #   AT3 (real-producer seam, B1): the robustness density gate CLI is run
  #        against a `component-manifest.yaml` emitted by the REAL M
  #        slice-04 manifest producer (the `nw-design` step) for a throwaway
  #        feature, NOT a hand-authored fixture. Converts the M-slice-04
  #        cross-feature edge from a calendar dependency into a demonstrated
  #        seam -- without this AT, M-slice-04-shipped is asserted but never
  #        demonstrated against the robustness gate.
  #
  # Driving port: the SUT is the wiring substrate -- (a) the real
  # `scripts/cli/at_review_verdict.py` producer reading the gate CLI exit
  # code; (b) the real SubagentStop hook chain invoking the gate CLI; (c)
  # the real M-producer-emitted `component-manifest.yaml` consumed by the
  # gate CLI. All three ATs drive through the production composition root
  # at Layer 3 subprocess (AT1, AT3) or Layer 4 wiring_e2e hook chain (AT2)
  # per Mandate-13 (driving-port-only boundary -- NO direct production
  # imports in step composition, NO function-boundary invocation).
  #
  # CATALOG: slice-05 also adds a `quality_gates:` entry to
  # `nWave/framework-catalog.yaml` so downstream tooling can enumerate the
  # gate's coverage (per feature-delta § 5 catalog requirement and the
  # tacit-judgment-to-gate-roadmap line 65 inspectability mandate). The
  # registration is observable via the catalog's loader but is not directly
  # asserted as its own AT -- the registration is verified as part of AT1
  # (the verdict producer reads the catalog to know which gates to invoke).
  #
  # B4 ENFORCEMENT NOTE: AT2 is the live hook-chain integration test. Per
  # the feature-delta § 6 explicit mandate (line 443-449): "slice-05 AT2
  # MUST therefore be a live integration test against the real SubagentStop
  # hook chain -- a real sub-agent dispatch that the intercept actually
  # blocks on a non-zero CLI exit -- never a mocked hook dispatch." This is
  # the symmetric inverse of slice-04 M2 -- slice-04's ATs MUST NOT invoke
  # live mutmut, slice-05's AT2 MUST NOT mock the hook chain.
  #
  # B1 ENFORCEMENT NOTE: AT3 stages a throwaway feature whose
  # `component-manifest.yaml` is emitted by the REAL M slice-04 producer
  # (the `nw-design` step). The composition stages the throwaway feature
  # workspace, invokes the real `nw-design` producer subprocess, captures
  # the emitted manifest, and runs the robustness gate against it. The
  # gate's CLI exit code on this real-producer-emitted artifact is the
  # discriminating observable -- if the producer's output diverges in
  # shape from the hand-authored fixtures slices 01-04 used, AT3 surfaces
  # the divergence.
  #
  # CRAFT-BLOCKING EDGES: slice-05 craft-blocks on M slice-01, M slice-02,
  # M slice-03, AND M slice-04 (feature-delta § 9 N1 fix). AT3 cannot reach
  # GREEN without the real M slice-04 producer; M slice-04 remains
  # ready-blocking for slices 01-04 (it is craft-blocking only for
  # slice-05). A crafter starting slice-05 before M slice-04 ships will
  # stall on AT3.

  @slice-05 @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: The AT review verdict producer blocks an approved verdict when the robustness density gate refuses the slice
    Given a slice whose declared unbounded input domain "tree-vs-commit-file-divergence" is staged with a property-based test the robustness density gate refuses
    When the developer runs the AT review verdict producer for the slice with the robustness density gate wired into its DISTILL exit
    Then the AT review verdict producer does not write an approved AT review verdict ledger record
    And the AT review verdict producer surfaces the robustness density gate refusal as the blocking diagnostic

  @slice-05 @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: A real sub agent dispatch passing through the real SubagentStop hook chain is blocked when the robustness density gate refuses the slice
    Given a slice whose declared unbounded input domain "tree-vs-commit-file-divergence" is staged with a property-based test the robustness density gate refuses and a real sub agent dispatch is prepared for that slice
    When the real sub agent dispatch passes through the real SubagentStop hook chain with the robustness density gate registered as an intercept
    Then the SubagentStop hook chain blocks the dispatch outcome from completing
    And the SubagentStop hook chain surfaces the robustness density gate refusal as the blocking diagnostic

  @slice-05 @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: The robustness density gate exercised against a real design component manifest emitted by the manifest producer refuses a throwaway feature whose declared unbounded input domain has no property-based test coverage
    Given a throwaway feature whose design component manifest is emitted by the real design manifest producer and declares an unbounded input domain "tree-vs-commit-file-divergence" with no property-based test coverage in the slice scope
    When the developer runs the robustness density gate against the throwaway feature using the real design manifest producer emitted component manifest
    Then the robustness density gate refuses the throwaway feature
    And the robustness density gate diagnostic identifies the uncovered declared unbounded input domain
