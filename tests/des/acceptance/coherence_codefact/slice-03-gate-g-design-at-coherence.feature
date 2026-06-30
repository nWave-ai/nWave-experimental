@feature-f-coherence-and-attestation @slice-03
Feature: A mechanical gate-G catches design↔AT divergence the review-rubric could only suspect
  As a maintainer running DISTILL with a design contract present
  I want design↔AT divergence caught by a MECHANICAL gate-G
    -- a prose `[REF] Code-Design` example-table diffed against the AT-AST via the
    slice-01/02 CodeFactPort substrate, returning a §17 GateVerdict
  So that a dropped example-table row or a signature mismatch cannot ship green,
    not just an LLM-adherence-dependent review-rubric that might miss it

  # slice-03 of f-coherence-and-attestation (JOB-028). Wires the gate-G
  # review-rubric SEAM f-distill NAMED but DEFERRED (its OB-2 table forward-
  # references the CodeFactPort queries `query.atoms-in-file` over the AT module +
  # `query.adr-section` over the design prose) to the ACTUAL mechanical AST diff.
  # gate-G CONSUMES the slice-01/02 substrate; it does NOT fork it (C2 -- no second
  # `import ast`). Builds ON slices 01+02 (the port + the TextSearchAdapter floor +
  # the AstAdapter + the full CodeFactChain negotiation already shipped); their ATs
  # stay GREEN.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition -- the REAL src/des seam):
  #   gate-G is driven at the COMPOSITION ROOT (a real gate-G callable over the
  #   real CodeFactPort substrate) -- NOT a subprocess `des gate-g` dispatch: the
  #   `des` dispatcher _REGISTRY has no gate-g row at HEAD, so a subprocess dispatch
  #   would be a collection-stage failure, not a semantic RED (mirrors slice-01's
  #   composition-root ASSUMPTION). The observable is the §17 GateVerdict + the
  #   diagnostic the mechanical diff names -- NEVER a line number.
  #
  #   AT-9  -> gate-G over a BIJECTIVE design `[REF] Code-Design` example-table ↔ AT
  #            pair (every ExampleTableRow maps to a covering scenario + vice versa);
  #            observable = §17 verdict PASS.
  #   AT-10 -> gate-G over a CONFIRMABLE divergence (a dropped example-table row --
  #            domain example 4 `f-export-csv` empty-dataset row -- OR a signature
  #            the AT references that the design never declared); observable = §17
  #            verdict FAIL + a NON-EMPTY diagnostic naming the divergence.
  #   AT-11 -> the OB-G cap (two cases):
  #            (a) prose-only suspected-but-unconfirmable drift (the diff runs
  #                against the PROSE `[REF] Code-Design`, NOT a D3
  #                code-design.manifest.yaml which is DEFERRED) -> §17 verdict
  #                UNVERIFIED + the North-Star cap surfaced LOUD (NOT a false PASS,
  #                NOT a confirmed FAIL).
  #            (b) manifest-or-adapter-absent (the CodeFactPort AstAdapter cannot
  #                run -- unsupported language) -> §17 verdict INDETERMINATE
  #                (degrade-LOUD -- the mechanism could not run).
  #
  # §17 verdict map (ADR-GV-001, FIVE verdicts -- CONSUMED unchanged, no sixth, C6):
  #   bijection found no objection                      -> PASS
  #   confirmable row/signature divergence              -> FAIL
  #   suspected-but-unconfirmable drift (prose, no D3)  -> UNVERIFIED (North-Star cap)
  #   mechanism could not run (adapter/lang absent)     -> INDETERMINATE
  #
  # OB-G RESOLVED (DEFER D3): gate-G diffs the AT-AST against the PROSE
  # `## Wave: DESIGN / [REF] Code-Design` block (read via `query.adr-section`), NOT a
  # D3 code-design.manifest.yaml (DEFERRED). The North-Star cap is UNVERIFIED-on-
  # suspected-drift -- mirroring f-distill OB-1 / f-deliver OB-1 option-c.
  #
  # active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the gate-G mechanism is
  # ABSENT -- `src/des/cli/gate_g.py` does not exist (verified: no gate_g module, no
  # `des gate-g` dispatcher row). Each scenario RED-fails with a semantic
  # AssertionError naming the missing gate-G mechanism, never a collection / import /
  # setup error. GREEN once DELIVER lands the gate-G mechanical diff over the
  # slice-01/02 CodeFactPort substrate.
  #
  # DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (in the composition docstring --
  # the SEAM, never a line number): A1 the gate-G entry (composition-root callable
  # `evaluate_gate_g` / `run_gate_g` / `gate_g` / `GateG().evaluate`); A2 the input
  # shape (the design contract path + the AT module path, OR a single feature-root);
  # A3 the verdict envelope (a §17 GateVerdict + diagnostic + cap-surfaced flag).
  # DELIVER MUST wire these to whatever real seam shapes it ships.

  # AT-9 -- the happy bijection: every design example-table row maps to a covering
  # AT scenario and vice versa -> gate-G finds no objection -> §17 PASS.
  @slice-03 @driving_port @real-io @us-gate-g-bijection @contract-shape:unbounded-preservation
  Scenario: A bijective design and acceptance set passes the coherence gate
    Given a design contract whose example-table rows and the acceptance scenarios are bijective
    When the coherence gate diffs the design contract against the acceptance tests
    Then the coherence gate returns a passing verdict

  # AT-10 -- the confirmable divergence: a dropped example-table row (the f-export-csv
  # empty-dataset row, domain example 4) OR a signature the AT references that the
  # design never declared -> the bijection is broken -> §17 FAIL + a diagnostic
  # naming the divergence. PBT-shaped over the divergence kinds -> Scenario Outline.
  @slice-03 @driving_port @real-io @us-gate-g-divergence @property @contract-shape:unbounded-preservation
  Scenario Outline: A confirmable design and acceptance divergence of kind <divergence> fails the coherence gate
    Given a design contract with a confirmable <divergence> against the acceptance tests
    When the coherence gate diffs the design contract against the acceptance tests
    Then the coherence gate returns a failing verdict
    And the coherence gate names the divergence in a diagnostic

    Examples:
      | divergence         |
      | dropped-row        |
      | signature-mismatch |

  # AT-11(a) -- the OB-G North-Star cap: a divergence is SUSPECTED but the prose
  # `[REF] Code-Design` is not machine-diffable to a row-level bijection (no D3
  # manifest, DEFERRED) -> §17 UNVERIFIED + the North-Star cap surfaced LOUD (NOT a
  # false PASS, NOT a hard FAIL).
  @slice-03 @driving_port @real-io @us-gate-g-cap-unverified @contract-shape:unbounded-preservation
  Scenario: A suspected but unconfirmable design drift surfaces the North-Star cap as unverified
    Given a design contract whose prose suspects a drift the row-level diff cannot confirm
    When the coherence gate diffs the design contract against the acceptance tests
    Then the coherence gate returns an unverified verdict
    And the coherence gate surfaces the North-Star cap loudly

  # AT-11(b) -- the OB-G degrade-LOUD: the CodeFactPort AstAdapter cannot run (the
  # target language is unsupported) -> the inspection substrate cannot run -> §17
  # INDETERMINATE (the mechanism could not run -- never a false green).
  @slice-03 @driving_port @real-io @us-gate-g-adapter-absent @contract-shape:unbounded-preservation
  Scenario: An unsupported language for the inspection adapter degrades the coherence gate to indeterminate
    Given a design contract whose acceptance tests are in a language the inspection adapter cannot parse
    When the coherence gate diffs the design contract against the acceptance tests
    Then the coherence gate returns an indeterminate verdict
    And the coherence gate did not run a real mechanical diff
