@feature-f-coherence-and-attestation @slice-02
Feature: The code-fact fallback chain walks precision tiers and degrades LOUD when one is absent
  As a maintainer on a supported language (and, when the paid Tsunami tier is present, a precise one)
  I want the higher-precision structural answer when it is available
    -- the fallback chain walking Tsunami -> AstAdapter -> TextSearchAdapter,
    each declaring its own confidence
  So that I get the best available precision, every tier's confidence is honestly
    declared, and a missing tier degrades LOUD (never silent) while the chain keeps answering

  # slice-02 of f-coherence-and-attestation (JOB-028). Completes the open-core
  # CodeFactPort foundation: adds the AstAdapter (approx, REUSING the sole
  # testarch import-ast site -- NO second parser, C2) + the TsunamiAdapter
  # paid-tier degrade-LOUD-when-absent seam + the full fallback CHAIN negotiation.
  # Builds ON slice-01 (the port + the TextSearchAdapter floor + the floor-only
  # chain already shipped, commit 30646e7a8); slice-01's 8 ATs stay GREEN.
  #
  # DRIVING SURFACES (Mandate-13, Layer 3 composition -- the REAL src/des seams):
  #   AT-1 -> the REAL AstAdapter via the CodeFactPort over a real tmp_path Python
  #           tree; observable = the CodeFactResult envelope tagged provider=ast @
  #           confidence=approx (the structural payload computed syntactically,
  #           never a faked binding-resolved).
  #   AT-2 -> the REAL CodeFactChain.query negotiation over a real tree (Tsunami
  #           absent -- the normal case); observable = the FIRST provider covering
  #           the capability at the floor, tagged with that tier's confidence
  #           (Tsunami absent -> Ast approx), ranged over the LOCKED stable-core
  #           capability set.
  #   AT-3 -> the REAL CodeFactChain with Tsunami ABSENT (probe fails -- the normal
  #           case); observable = the chain SKIPS Tsunami LOUDLY (the
  #           health.gate.code-fact.* skip signal) AND PROCEEDS to the next tier
  #           (not silent-fail, not a hang). Tsunami-PRESENT counter-case (via a
  #           probe-double) asserts provider=tsunami @ binding-resolved.
  #   AT-4 -> the REAL CodeFactChain on a Tsunami-ONLY capability with Tsunami
  #           ABSENT (C8); observable = the chain SKIPS LOUDLY
  #           (health.gate.code-fact.* event) + the gate PROCEEDS (does NOT block
  #           on Tsunami absence, does NOT fabricate a lower-tier answer).
  #   Drive on the SEAM / the CodeFactResult envelope / the provider-selection /
  #   the LOUD-skip signal -- NEVER a line number.
  #
  # LOCKED vocabulary (ADR-LA-001 §2/§5a, ratified with SF 2026-06-14,
  # kebab-lowercase, BYTE-LOCKED cross-tier) -- CONSUMED, never re-authored:
  #   provider   : tsunami | ast | textsearch
  #   confidence : binding-resolved | approx | noisy   (1:1 down the chain)
  #
  # active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the AstAdapter +
  # TsunamiAdapter modules are ABSENT and CodeFactChain is FLOOR-ONLY (no Tsunami
  # / Ast tiers, no loud-skip signal). Each scenario RED-fails with a semantic
  # AssertionError (the expected observable -- provider=ast, the loud-skip event,
  # the proceed-after-skip -- is missing because the seam is unbuilt/floor-only),
  # never a collection / import / setup error. GREEN once DELIVER lands the two
  # adapters + EXTENDS the chain to the full negotiation.
  #
  # DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (in composition docstring):
  #   A1 AstAdapter ctor = AstAdapter(root=<tree>) (mirroring TextSearchAdapter).
  #   A2 chain takes the Tsunami presence (tsunami_present=...) to wire the paid
  #      tier only when its probe passes.
  #   A3 the chain exposes its LOUD health.gate.code-fact.* skip events via a
  #      health_events()/skip_events() accessor.
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
  # capability at the floor. With Tsunami ABSENT (the normal Python-only target)
  # the structural tier wins -> Ast `approx`. Ranges over the LOCKED stable-core
  # capability set.
  @slice-02 @driving_port @real-io @us-chain-negotiation @property @contract-shape:bounded-change
  Scenario Outline: With Tsunami absent the chain returns the structural tier for capability <capability>
    Given the paid precision tier is not installed on this target
    And the negotiation targets the stable-core capability <capability>
    When the fallback chain negotiates the best available provider
    Then a structural answer is returned by the chain
    And the structural answer is tagged ast at approx confidence
    And the structural answer carries locked cross-tier provenance tokens

    Examples:
      | capability            |
      | query.callers-of      |
      | query.never-wired     |
      | query.atoms-in-file   |

  # AT-3 -- Tsunami ABSENT degrades LOUD: the chain SKIPS the Tsunami tier with a
  # LOUD health.gate.code-fact.* signal AND PROCEEDS to the next tier (not a
  # silent-fail, not a hang). The PRESENT counter-case (probe-double passes)
  # confirms the chain head answers tsunami @ binding-resolved.
  @slice-02 @driving_port @real-io @us-tsunami-degrade-loud @contract-shape:unbounded-preservation
  Scenario: An absent Tsunami tier is skipped loudly and the chain proceeds to the next tier
    Given the paid precision tier is not installed on this target
    And the negotiation targets the stable-core capability query.never-wired
    When the fallback chain negotiates the best available provider
    Then the absent precision tier is skipped with a loud health signal
    And the chain proceeds to the next tier and still answers

  @slice-02 @driving_port @real-io @us-tsunami-present @contract-shape:bounded-change
  Scenario: When the paid precision tier is installed the chain head answers at the precise confidence
    Given the paid precision tier is installed on this target
    And the negotiation targets the stable-core capability query.never-wired
    When the fallback chain negotiates the best available provider
    Then the precise tier is tagged tsunami at binding-resolved confidence

  # AT-4 -- C8: a Tsunami-ONLY capability with Tsunami ABSENT is SKIPPED LOUDLY
  # (a health.gate.code-fact.* ledger event) and the GATE PROCEEDS -- it does NOT
  # block on Tsunami absence, and it does NOT fabricate a lower-tier answer for a
  # capability only the paid tier can honor.
  @slice-02 @driving_port @real-io @us-tsunami-only-skip @contract-shape:unbounded-preservation
  Scenario: A premium-only capability with the precision tier absent skips loudly and the gate proceeds
    Given the paid precision tier is not installed on this target
    And the negotiation targets a premium-only capability the floor cannot honor
    When the fallback chain negotiates the best available provider
    Then the premium-only capability is skipped with a loud health signal
    And no lower tier is dressed up as covering the premium-only capability
    And the gate proceeds despite the loud skip
