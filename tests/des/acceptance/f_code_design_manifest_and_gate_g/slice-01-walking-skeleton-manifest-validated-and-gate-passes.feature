@feature-f-code-design-manifest-and-gate-g @slice-01 @walking-skeleton @driving_port
Feature: An architect's code-design manifest is validated and gate-G passes against bijective acceptance tests
  An architect who emits a code-design manifest with an example-tables block has it
  mechanically validated at DESIGN-OUT (schema-valid, every sut symbol grep-findable),
  and the design-AT coherence gate, run end-to-end against that manifest and the
  slice's acceptance tests, returns a passing verdict when the manifest rows and the
  acceptance scenarios cover each other exactly. This is the thinnest end-to-end
  vertical: a real manifest, real validation, the real coherence gate, real data.

  Contract-shape is declared PER SCENARIO (not feature-level): the gate-G scenarios
  drive evaluate_gate_g at the composition root with in-memory CodeFactPort doubles
  (@in-memory @contract-shape:pure-function); the manifest-validation scenario runs
  the REAL validator subprocess (@real-io @contract-shape:bounded-change -- HIGH-2 +
  HIGH-3: the subprocess scenario carries @real-io individually, and the feature
  header carries no @in-memory because the slice mixes treatments).

  Witnesses: CT-1 (manifest bijection -> PASS) + CT-4 (manifest validated at
  DESIGN-OUT). The walking-skeleton closes the whole vertical through the
  production composition root on real fixtures.

  @slice-01 @in-memory @contract-shape:pure-function @row:bijection-passes
  Scenario: The coherence gate passes when every manifest row is covered by a tagged acceptance scenario
    Given a code-design manifest whose example-table rows and the tagged acceptance scenarios cover each other exactly
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns a passing verdict

  @slice-01 @real-io @contract-shape:bounded-change @row:manifest-validated
  Scenario: The manifest is accepted at design-out when every declared symbol is findable in its cited file
    Given a code-design manifest that is schema-valid and whose every declared symbol is findable in its cited file
    When the manifest is validated at design-out
    Then the manifest is accepted

  @slice-01 @in-memory @contract-shape:pure-function @row:passing-verdict-is-not-a-cap
  Scenario: A manifest-backed passing verdict is deterministic and never capped as unverified
    Given a code-design manifest whose example-table rows and the tagged acceptance scenarios cover each other exactly
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns a passing verdict
    And the coherence gate does not surface the North-Star cap

  @slice-01 @in-memory @contract-shape:pure-function @row:empty-acceptance-set-against-empty-manifest
  Scenario: The coherence gate passes when a manifest declaring no rows is matched by acceptance tests declaring none
    Given a code-design manifest declaring zero example-table rows matched by acceptance tests declaring none
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns a passing verdict
