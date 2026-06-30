@slice-07 @feature-discuss-epic-mode
Feature: The discuss surfaces carry the caveman reasoning mandate and the new epic-mode text is caveman-native

  Agents executing the discuss wave receive the caveman reasoning mandate --
  verdict-first, tables over prose, depth from the rigor profile, zero narrative.
  And ALL new epic-mode text (the sections slices 02/04/05/06 landed) is authored
  caveman-native. Retroactive compression of the mature discuss skill is SUPERSEDED
  (Ale 2026-06-10, pilot ceiling 8-10%): the mandate ADDS, it never shrinks existing
  content.

  The mandate prose and the section wording are LLM-authored: their tone is a
  prompt-surface judgment, reviewed by Sentinel. What these scenarios pin is the
  STRUCTURAL contract over the REAL nWave/ files (read-only, Layer 3 FS acceptance):
  the mandate's three load-bearing clauses present on the execution surfaces, the
  new epic-mode sections carrying tables with no narrative padding, and a
  pre-existing section preserved across the mandate insertion.

  # D-caveman clauses (a')+(b), re-scoped 2026-06-10. The slice's "code" is
  # SKILL / AGENT text -- there is NO src/des surface (mandate-only re-scope; the
  # deliverable is prose). Driving port: read-only document observation of the real
  # nWave/ discuss surfaces (the slice-06 dogfood read-only model, one wave-surface
  # up). Example-only, no PBT (Mandate 9/11): the audit is a finite closed contract
  # over the discuss surfaces + the closed set of new epic-mode section headings.
  #
  # NOT a presence-watcher: the mandate clause discriminates ABSENT (today) vs
  # PRESENT (GREEN) -- a behaviour, not a literal grep that passes on first keystroke.
  # The native-style clause discriminates a tabular padding-free section from a
  # prose-bloated one. The compression clause is the state-delta inverse (existing
  # content preserved), not a wording check.
  #
  # Honest RED/WITNESS split (slice-03 WITNESS_GREEN precedent):
  #   AT-1 mandate presence -> ACTIVE-RED (grep verified 2026-06-11: zero mandate
  #        hits in any discuss surface today). DELIVER authors the mandate.
  #   AT-2 native-style audit -> WITNESS (the slice-02/04/05/06 sections were
  #        authored caveman-native by instruction; the honest verdict is judged in
  #        the fail-for-the-right-reason gate, not assumed).
  #   AT-3 zero-compression -> WITNESS (the pre-existing section exists today and
  #        must STAY -- the inverse pin guards the re-scope).

  @slice-07 @driving_port @contract-shape:bounded-change
  Scenario: The discuss execution surfaces carry the caveman reasoning mandate
    Given the discuss execution surfaces on the real nWave files
    When the maintainer audits the discuss surfaces for the caveman reasoning mandate
    Then the discuss skill surface carries the caveman reasoning mandate
    And the discuss-wave agent surface carries the caveman reasoning mandate

  @slice-07 @driving_port @contract-shape:pure-function
  Scenario: The new epic-mode text is authored caveman-native
    Given the discuss execution surfaces on the real nWave files
    When the maintainer audits the new epic-mode sections for caveman-native style
    Then every new epic-mode section is authored caveman-native

  @slice-07 @driving_port @error @contract-shape:bounded-change
  Scenario: The mandate insertion preserves the pre-existing discuss skill content
    Given the discuss execution surfaces on the real nWave files
    When the maintainer audits the mandate insertion for retroactive compression
    Then the pre-existing discuss skill section is preserved
