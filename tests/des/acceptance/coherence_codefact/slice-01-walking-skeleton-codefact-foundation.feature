@feature-f-coherence-and-attestation @slice-01
Feature: A code-fact gate always gets an honest, provider-tagged answer through one substrate
  As a maintainer running a code-fact gate on any target with only Python
  I want the fact (e.g. "does this net-new symbol have a production call-site?")
    re-derived through ONE substrate that always returns a usable answer tagged
    with which provider produced it and at what confidence
  So that I never depend on a per-gate hand-rolled `import ast` or a hallucinated
    claim, and a PASS stands on an honest, declared-confidence fact

  # slice-01 of f-coherence-and-attestation (walking skeleton, JOB-028). The
  # thinnest end-to-end vertical proving the load-bearing CodeFactPort substrate:
  # the port + the pure-Python TextSearchAdapter universal floor (always answers,
  # `noisy`) + ONE code-fact gate re-derived through it + {provider, confidence,
  # reason_code} tagging + the cross-tier Published-Language byte-lock guard.
  #
  # DRIVING SURFACES (Mandate-13):
  #   AT-1/AT-2/AT-3 -> Layer 3 composition: the REAL CodeFactPort /
  #     TextSearchAdapter / slice-01 code-fact gate via the production composition
  #     root; observable = the CodeFactResult envelope ({provider, confidence,
  #     reason_code, payload}) -- the floor adapter ALWAYS answers (never raises).
  #   AT-4 -> the REAL byte-lock guard mechanism: asserts the OSS-serialized
  #     locked-vocabulary token set is byte-identical to the committed
  #     locked-vocabulary.json fixture AND is SELF-PROBED (planted drift -> RED).
  #   The scenarios drive on the SEAM / the CodeFactResult envelope / the gate
  #   verdict / the guard's byte-comparison -- NEVER a line number.
  #
  # LOCKED vocabulary (ADR-LA-001 §2/§5a, ratified with SF 2026-06-14,
  # kebab-lowercase, BYTE-LOCKED cross-tier):
  #   capability ids : query.callers-of query.reads-of query.never-wired
  #                    query.atoms-in-file query.adr-section
  #   provider       : tsunami | ast | textsearch
  #   confidence     : binding-resolved | approx | noisy
  #   reason_code    : live-non-callable | absent
  #
  # active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the pinned seams are
  # ABSENT (src/des/ports/code_fact_port.py, the TextSearchAdapter, the slice-01
  # gate, tests/build/fixtures/locked-vocabulary.json + its guard). Each scenario
  # RED-fails with a semantic AssertionError (the expected observable is missing
  # because the seam is unbuilt), never a collection / import / setup error.
  # GREEN once DELIVER lands the seams.
  #
  # ASSUMPTION flagged to DELIVER (slice-01 gate_id): the Code-Design pins ONE
  # code-fact gate but no concrete `des <gate-id>` subcommand for it (gate_g.py is
  # slice-03). AT-3 drives the gate at the composition root via a real gate
  # callable (the dispatcher _REGISTRY has no slice-01 gate row at HEAD). DELIVER
  # MUST wire AT-3 to whatever real slice-01 code-fact gate callable it ships.

  # AT-1 -- the CodeFactPort foundation: the port + registry two-axis floor exist
  # and the substrate ALWAYS returns a usable answer for a LOCKED stable-core
  # capability, tagged with LOCKED {provider, confidence} provenance.
  @slice-01 @walking-skeleton @driving_port @real-io @us-codefact-foundation @property @contract-shape:bounded-change
  Scenario Outline: The CodeFactPort substrate always returns a provider-tagged answer for stable-core capability <capability>
    Given a code-fact gate requires the stable-core capability <capability>
    When the substrate is asked for the fact through the CodeFactPort
    Then a usable answer comes back
    And the answer carries provider and confidence provenance
    And the provider token is one of the locked cross-tier values
    And the confidence token is one of the locked cross-tier values

    Examples:
      | capability            |
      | query.callers-of      |
      | query.reads-of        |
      | query.never-wired     |
      | query.atoms-in-file   |
      | query.adr-section     |

  # AT-2 -- the universal floor: with only the pure-Python TextSearchAdapter
  # wired (no Tsunami, no AstAdapter -- the normal Python-only target), a
  # stable-core capability is still answered TEXTUALLY, tagged textsearch @ noisy
  # (lowest confidence loudly declared, never inflated).
  @slice-01 @walking-skeleton @driving_port @real-io @us-codefact-floor @contract-shape:bounded-change
  Scenario: The pure-Python floor answers a stable-core capability textually at noisy confidence
    Given a code-fact gate requires the stable-core capability query.callers-of
    When the substrate is asked for the fact through the CodeFactPort
    Then a usable answer comes back
    And the answer is tagged as the text-search floor at noisy confidence

  # AT-3 -- one code-fact gate re-derives query.never-wired THROUGH the port (not
  # a per-gate import ast), and the answer is tagged {provider, confidence}.
  # ADR-LA-001 D9 slice (c): the never-wired symbol case's disambiguating
  # signal (absent / live-non-callable) is owned by the never-wired PAYLOAD
  # schema (the `never_wired` bool), never the envelope.
  @slice-01 @walking-skeleton @driving_port @real-io @us-codefact-gate @contract-shape:bounded-change
  Scenario: A code-fact gate re-derives never-wired through the port and tags the provenance
    Given a net-new symbol with no production call-site
    When a code-fact gate re-derives whether it is never-wired through the port
    Then a usable answer comes back
    And the answer carries provider and confidence provenance
    And the never-wired answer carries a locked payload distinction

  # AT-4 -- the cross-tier Published-Language byte-lock guard: the committed
  # locked-vocabulary is byte-identical to the LOCKED language (PASS), and the
  # guard is SELF-PROBED -- a planted-drift variant makes it RED.
  @slice-01 @walking-skeleton @driving_port @real-io @us-byte-lock-guard @contract-shape:unbounded-preservation
  Scenario: The byte-lock guard passes on the pristine vocabulary and catches planted drift
    Given the published-language byte-lock guard
    When the guard runs against the pristine locked vocabulary
    Then the byte-lock guard passes
    When the guard runs against a planted-drift vocabulary variant
    Then the byte-lock guard goes red
