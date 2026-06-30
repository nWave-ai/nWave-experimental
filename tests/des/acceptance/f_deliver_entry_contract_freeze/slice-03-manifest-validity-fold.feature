@feature-f-deliver-entry-contract-freeze
Feature: The code-design manifest validity fold at DELIVER gate-IN

  DESIGN is optional (ADR-FLOW-002 D2): a feature MAY ship a
  code-design.manifest.yaml. When it does, the manifest's VALIDITY (schema-valid
  AND every `sut:` symbol grep-findable) is FOLDED into the DELIVER-entry
  structural-completeness check (ADR-FLOW-004 DDD-1 step 3 / DDD-5). A valid
  manifest CONTRIBUTES to PASS; an invalid manifest (stale `sut:` symbol or bad
  schema) FAILs the freeze; an absent manifest does NOT re-block (a consciously
  skipped optional wave is never refused over absence).

  # Driving port (Mandate-13, Layer 3 subprocess): the REAL
  # `des verify-deliver-entry-contract` gate over a real temp repo whose
  # otherwise-structurally-complete contract ships a `code-design.manifest.yaml`
  # in the armed validity state. The manifest validator lives under scripts/cli/**,
  # so the gate invokes it as a SUBPROCESS (F-D-09), never `from scripts.* import`.
  # Observable: the §17 verdict the fold projects (valid/absent -> PASS, invalid ->
  # FAIL naming the manifest defect).

  @slice-03 @driving_port @contract-shape:bounded-change @CT-4
  Scenario Outline: A shipped manifest's validity is folded into the freeze, and an absent manifest never re-blocks
    Given a structurally-complete contract that ships a <manifest> code-design manifest
    When the contract-freeze gate folds the manifest at the first DELIVER gate-IN
    Then the manifest-fold gate returns a <verdict> verdict

    Examples: the manifest-validity fold (DESIGN optional, ADR-FLOW-004 DDD-5)
      | manifest | verdict |
      | valid    | pass    |
      | invalid  | fail    |
      | absent   | pass    |
