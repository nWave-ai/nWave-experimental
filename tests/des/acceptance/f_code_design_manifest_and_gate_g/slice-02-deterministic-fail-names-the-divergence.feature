@feature-f-code-design-manifest-and-gate-g @slice-02 @driving_port
Feature: The coherence gate returns a deterministic failing verdict that names the divergence
  When a code-design manifest is present, its stable example-table row-id is the join key
  that makes a design-AT divergence CONFIRMABLE. So a dropped row (a manifest row no tagged
  acceptance scenario covers) or an undeclared scenario (an acceptance scenario whose @row tag
  names a row the manifest never declared) is a confirmed divergence: the gate returns a
  deterministic FAILING verdict whose diagnostic NAMES the offending row, replacing the
  UNVERIFIED cap the loose prose contract once forced.

  Contract-shape is pure-function per scenario: the gate reads the manifest and the acceptance
  tests as data and returns a verdict envelope, with no observable side effect
  (@contract-shape:pure-function). The scenarios drive the REAL coherence-gate mechanism at the
  composition root over a real manifest and a real acceptance module on real data (@driving_port).

  Witnesses: CT-2 (dropped manifest row -> FAIL naming the dropped row-id) + CT-3 (undeclared
  acceptance scenario -> FAIL naming the undeclared row-id). The deterministic FAIL is the half
  of KPI-1 that replaces the prose-era UNVERIFIED fallback once a manifest pins the join key.

  @slice-02 @in-memory @contract-shape:pure-function @row:dropped-row-fails-and-is-named
  Scenario: The gate fails and names the dropped row when a manifest row has no covering acceptance scenario
    Given a code-design manifest with a row that no tagged acceptance scenario covers
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns a failing verdict
    And the coherence gate diagnostic names the dropped row

  @slice-02 @in-memory @contract-shape:pure-function @row:undeclared-scenario-fails-and-is-named
  Scenario: The gate fails and names the undeclared row when an acceptance scenario tags a row the manifest never declared
    Given a code-design manifest against acceptance tests that tag a row the manifest never declared
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns a failing verdict
    And the coherence gate diagnostic names the undeclared row

  @slice-02 @in-memory @contract-shape:pure-function @row:manifest-backed-fail-is-not-capped
  Scenario: A manifest-backed failing verdict is deterministic and is never capped as unverified
    Given a code-design manifest with a row that no tagged acceptance scenario covers
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns a failing verdict
    And the coherence gate does not surface the North-Star cap
