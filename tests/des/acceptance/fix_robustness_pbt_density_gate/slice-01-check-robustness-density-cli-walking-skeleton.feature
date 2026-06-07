@feature-fix-robustness-pbt-density-gate @slice-01 @walking-skeleton
Feature: The robustness density gate asserts that every declared unbounded input domain is exercised by a property-based test
  As an nWave framework developer authoring a feature's acceptance tests
  I want the robustness density gate CLI to fail closed when a declared
    unbounded input domain has no property-based test covering it
  So that a Class-B defect cannot ship behind an example-only test over a
    domain the architect already named as unbounded

  # carpaccio slice-01 (DESIGN slice plan, ## Wave: DISCUSS / [REF] Slice Plan).
  # THE walking skeleton: the thinnest end-to-end vertical -- parse the
  # DISTILL projection of the M-feature component manifest, walk the slice
  # AT scope for `# domain:`-tagged @given strategies, exit 0/1/2.
  #
  # CONTRACT SOURCE: this slice is authored against the feature-delta
  # `docs/feature/fix-robustness-pbt-density-gate/feature-delta.md` section 3
  # (the mechanical check, Part 2 -- mechanical-approval CLI) and section 6
  # (slice-01 row). The CLI surface (modes, exit codes, declaration shape)
  # mirrors the sibling spine-gate CLIs `at_review_verdict.py` /
  # `carpaccio_slice_gate.py` (both grep-verified in `scripts/cli/`).
  # Slice-01 walks the parse + presence-check + exit-code seam; later slices
  # add empty-declaration semantics (slice-02), genuineness layers 1+3
  # (slice-03), genuineness layer 2 (slice-04), and the wiring slice
  # (slice-05).
  #
  # Layer 5 (WS @wiring_e2e): real stack, subprocess, real YAML parsing,
  # real AST/grep over a real staged test file. Example-only, no PBT
  # (Mandate 9/11). Traditional assertions permitted at layer 4+
  # (Mandate 8). No fixture-folding: the subject is the production CLI, the
  # composition stages real on-disk artifacts, the delivery form is the
  # invocation result.
  #
  # Driving port: `check_robustness_density` CLI invoked as a `python -m`
  # subprocess (per the project Infrastructure Policy spine-gate CLI row,
  # mirroring `at_review_verdict` / `carpaccio_slice_gate`).
  #
  # DEPENDENCY: M slice-01 (`nWave/schemas/component-manifest.schema.json`)
  # is shipped; the DISTILL projection (`unbounded-domains.yaml`) is a
  # subset of that schema. Grep-verified present in this repo at gate
  # author-time.

  @slice-01 @walking-skeleton @wiring_e2e @driving_port @real-io @contract-shape:pure-function
  Scenario: A declared unbounded input domain that is covered by a property-based test passes the gate
    Given a declared unbounded input domain "tree-vs-commit-file-divergence" carrying a property-based test that exercises it
    When the developer runs the robustness density gate against the declared scope
    Then the gate exit status indicates success

  @slice-01 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A declared unbounded input domain that has no property-based test fails the gate closed
    Given a declared unbounded input domain "tree-vs-commit-file-divergence" with no property-based test exercising it
    When the developer runs the robustness density gate against the declared scope
    Then the gate exit status indicates a check failed

  @slice-01 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A declaration document that cannot be parsed is rejected at the parser boundary
    Given a declaration document that cannot be parsed as a valid manifest projection
    When the developer runs the robustness density gate against the declared scope
    Then the gate exit status indicates a malformed declaration
