@feature-fix-robustness-pbt-density-gate @slice-02 @walking-skeleton
Feature: The robustness density gate fails closed on a silently-missing declaration and accepts an explicitly-empty one
  As an nWave framework developer authoring a feature's acceptance tests
  I want the robustness density gate CLI to refuse a silently-missing
    unbounded-input-domains block while accepting an explicit empty
    declaration carrying a one-line rationale
  So that "no declaration" cannot vacuously pass as "no unbounded domain"
    and a DISTILL projection cannot invent a domain that the DESIGN
    component manifest never authored

  # carpaccio slice-02 (DESIGN slice plan, ## Wave: DISCUSS / [REF] Slice Plan).
  # Builds on slice-01's walking-skeleton parser. Adds the fail-closed
  # absence semantics that make "no declaration" a refusal not a vacuous
  # pass, and the DECISION D1 provenance check that prevents DISTILL from
  # authoring fresh domains that the DESIGN component manifest never
  # declared.
  #
  # CONTRACT SOURCE: this slice is authored against the feature-delta
  # `docs/feature/fix-robustness-pbt-density-gate/feature-delta.md` section 6
  # (slice-02 row) and section 3 (DECISION D1 + Part 2 empty-declaration
  # guard). Three ATs:
  #   AT1: missing `unbounded-input-domains:` block + ATs present in scope
  #        -> `RobustnessDeclarationMissing` exit 1 (closes the
  #         telemetry-blindness pattern -- absence is not a pass).
  #   AT2: explicit `unbounded-input-domains: []` + one-line rationale
  #        (via the M schema's `unbounded-input-domains-empty-rationale`
  #        field) -> exit 0 (the legitimate "no unbounded domains" claim,
  #        upstream reviewer-vetoable per B6 owned residue, gate accepts).
  #   AT3: a DISTILL projection entry carrying `declared-at: distill` for
  #        a domain id that does NOT appear in the DESIGN component
  #        manifest -> exit 1 (provenance check, DECISION D1 -- DISTILL
  #        projects, never authors).
  #
  # Layer 5 (WS @wiring_e2e): real stack, subprocess, real YAML parsing,
  # real on-disk artifact composition. Example-only, no PBT (Mandate 9/11).
  # Traditional assertions permitted at layer 4+ (Mandate 8). No
  # fixture-folding: the subject is the production CLI, the composition
  # stages real on-disk artifacts, the delivery form is the invocation
  # result.
  #
  # Driving port: `check_robustness_density` CLI invoked as a `python -m`
  # subprocess (slice-01 precedent, project Infrastructure Policy spine-gate
  # CLI row).
  #
  # DEPENDENCY: M slice-01 (`nWave/schemas/component-manifest.schema.json`)
  # is shipped; slice-02 consumes the schema's
  # `unbounded-input-domains-empty-rationale` field (AT2) and the
  # `declared-at: const "design"` provenance contract (AT3).

  @slice-02 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A declaration document silently missing the unbounded-input-domains block is refused when acceptance tests are in scope
    Given a declaration document that omits the unbounded-input-domains block while acceptance tests exist in the scope
    When the developer runs the robustness density gate against the declared scope
    Then the gate exit status indicates a missing declaration

  @slice-02 @walking-skeleton @wiring_e2e @driving_port @real-io @contract-shape:pure-function
  Scenario: An explicitly empty declaration that carries a one-line rationale is accepted as a legitimate no-unbounded-domains claim
    Given a declaration document that explicitly declares no unbounded input domains and carries a one-line rationale
    When the developer runs the robustness density gate against the declared scope
    Then the gate exit status indicates the explicit empty declaration was accepted

  @slice-02 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A distill-authored domain that has no matching entry in the design component manifest is refused at the provenance boundary
    Given a declaration document carrying a distill-authored unbounded input domain "tree-vs-commit-file-divergence" that the design component manifest never declared
    When the developer runs the robustness density gate against the declared scope
    Then the gate exit status indicates a provenance violation
