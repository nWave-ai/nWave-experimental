@feature-f-coherence-and-attestation @slice-02
Feature: The code-fact fallback chain walks precision tiers and answers structurally
  As a maintainer on a supported language
  I want the higher-precision structural answer when it is available
    -- the fallback chain walking AstAdapter -> TextSearchAdapter, each
    declaring its own confidence
  So that I get the best available precision and every tier's confidence is
    honestly declared while the chain keeps answering

  # slice-02 of f-coherence-and-attestation (JOB-028). Completes the open-core
  # CodeFactPort foundation: adds the AstAdapter (approx, REUSING the sole
  # testarch import-ast site -- NO second parser, C2) + the full fallback CHAIN
  # negotiation. Builds ON slice-01 (the port + the TextSearchAdapter floor +
  # the floor-only chain already shipped, commit 30646e7a8); slice-01's 8 ATs
  # stay GREEN.
  #
  # ADR-LA-001 D6-R1 / D9 RED_TO_GREEN(b): the paid TsunamiAdapter stub was a
  # fabricated precision tier -- no production caller ever wires it, and
  # LA1-L7 (a `binding-resolved` answer requires a real `TransportWitness`)
  # makes it unrepresentable in OSS. Its scenarios (a fictional `present`
  # counter-case, a `tsunami-absent` skip event, a Tsunami-only capability
  # skip) are deleted with the stub, never frozen here.
  #
  # DRIVING SURFACES (Mandate-13, Layer 3 composition -- the REAL src/des seams):
  #   AT-1 -> the REAL AstAdapter via the CodeFactPort over a real tmp_path Python
  #           tree; observable = the CodeFactResult envelope tagged provider=ast @
  #           confidence=approx (the structural payload computed syntactically).
  #   AT-2 -> the REAL CodeFactChain negotiation over a real tree; observable =
  #           the FIRST provider covering the capability at the floor, tagged
  #           with that tier's confidence (Ast approx), ranged over the LOCKED
  #           stable-core capability set.
  #   Drive on the SEAM / the CodeFactResult envelope / the provider-selection
  #   -- NEVER a line number.
  #
  # LOCKED vocabulary (ADR-LA-001 §2/§5a, ratified with SF 2026-06-14,
  # kebab-lowercase, BYTE-LOCKED cross-tier) -- CONSUMED, never re-authored:
  #   provider   : ast | textsearch  (the OSS-reachable tokens; `tsunami` stays
  #                a reserved future-provider token, D4)
  #   confidence : approx | noisy   (1:1 down the chain)
  #
  # DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (in composition docstring):
  #   A1 AstAdapter ctor = AstAdapter(root=<tree>) (mirroring TextSearchAdapter).
  #   DELIVER MUST wire these to whatever real seam shapes it ships (update the
  #   single driving-port invocation, not a line number).

  # AT-1 -- the AstAdapter answers a stable-core capability STRUCTURALLY at
  # `approx`, REUSING the sole testarch import-ast parser (no second parser, C2),
  # tagged with the LOCKED ast/approx provenance. Ranges over the LOCKED
  # stable-core capability set (PBT-shaped over a finite set -> Scenario Outline).
  @slice-02 @driving_port @real-io @us-ast-adapter @property @contract-shape:bounded-change
  Scenario Outline: The AstAdapter answers stable-core capability <capability> structurally at approx confidence
    Given a maintainer asks the structural tier for the capability <capability>
    When the ast tier answers the structural fact over a real source tree
    Then a structural answer is returned by the chain
    And the structural answer is tagged ast at approx confidence
    And the structural answer carries locked cross-tier provenance tokens

    Examples:
      | capability            |
      | query.callers-of      |
      | query.reads-of        |
      | query.never-wired     |
      | query.atoms-in-file   |

  # AT-2 -- the full chain negotiation returns the FIRST provider covering the
  # capability at the floor. On a real, parseable Python-only target the
  # structural tier wins -> Ast `approx`. Ranges over the LOCKED stable-core
  # capability set.
  @slice-02 @driving_port @real-io @us-chain-negotiation @property @contract-shape:bounded-change
  Scenario Outline: The fallback chain negotiates the structural tier for capability <capability>
    Given the negotiation targets the stable-core capability <capability>
    When the fallback chain negotiates the best available provider
    Then a structural answer is returned by the chain
    And the structural answer is tagged ast at approx confidence
    And the structural answer carries locked cross-tier provenance tokens

    Examples:
      | capability            |
      | query.callers-of      |
      | query.never-wired     |
      | query.atoms-in-file   |
