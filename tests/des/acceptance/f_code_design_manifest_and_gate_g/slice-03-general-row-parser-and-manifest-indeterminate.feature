@feature-f-code-design-manifest-and-gate-g @slice-03 @driving_port
Feature: The coherence gate is a general design-AT gate and degrades loud on an unsupported acceptance language
  The coherence gate reads the @row join key on ANY scenario wording, not only the one
  feature-specific phrasing the original hardcoded parser recognized. So every acceptance
  scenario is seen: a scenario with general wording that carries NO @row tag cannot be
  confirmed against any manifest row, and the gate caps at an UNVERIFIED verdict that NAMES
  the untagged scenario rather than silently passing it. And when the acceptance module is in
  a language the inspection substrate cannot parse, the gate degrades LOUD to an INDETERMINATE
  verdict even on the manifest source - it never fabricates a passing or failing verdict the
  mechanism could not actually compute.

  Contract-shape is pure-function per scenario: the gate reads the manifest and the acceptance
  module as data and returns a verdict envelope, with no observable side effect
  (@contract-shape:pure-function). The scenarios drive the REAL coherence-gate mechanism at the
  composition root over a real manifest and a real acceptance module on real data (@driving_port).

  Witnesses: CT-10b (an untagged scenario under a manifest -> UNVERIFIED naming it, never a
  silent pass) + CT-6 (an acceptance module in an unsupported language under a manifest ->
  INDETERMINATE, degrade-LOUD) + CT-5 (a generally-worded scenario on the PROSE path is
  recognized -> the hardcoded single-feature parser is mechanically gone). Together they make
  the gate a GENERAL coherence gate that reads the join key on any wording and never fabricates
  a verdict it could not compute.

  @slice-03 @in-memory @contract-shape:pure-function @row:untagged-general-scenario-is-named-not-passed
  Scenario: The gate caps at unverified and names an untagged scenario carried under a manifest
    Given a code-design manifest whose acceptance tests include a generally-worded scenario with no row tag
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns an unverified verdict
    And the coherence gate diagnostic names the untagged scenario

  @slice-03 @real-io @contract-shape:pure-function @row:manifest-unsupported-language-is-indeterminate
  Scenario: The gate is indeterminate when a manifest-backed acceptance module is in an unsupported language
    Given a code-design manifest whose acceptance module is in a language the inspection substrate cannot parse
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns an indeterminate verdict

  @slice-03 @real-io @contract-shape:pure-function @row:manifest-unsupported-language-mechanism-did-not-run
  Scenario: The gate reports the mechanism did not run when the manifest-backed acceptance language is unsupported
    Given a code-design manifest whose acceptance module is in a language the inspection substrate cannot parse
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate reports that the mechanism did not run

  @slice-03 @real-io @contract-shape:pure-function @row:prose-general-wording-is-recognized
  Scenario: The gate recognizes generally-worded prose-contract scenarios rather than only one feature-specific phrasing
    Given a prose design contract whose rows are covered one-to-one by generally-worded acceptance scenarios
    When the coherence gate reads the manifest and diffs it against the acceptance tests
    Then the coherence gate returns a passing verdict
