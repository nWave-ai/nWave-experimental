@feature-fix-design-reuse-first-gate-cli @slice-05
Feature: The nw-design skill instructs architects to declare methodology-component reuse

  slice-03 shipped the methodology file-component DETECTOR: the reuse-first
  check now FAILs a feature that adds a data SSOT under nWave/data, a skill
  under nWave/skills, or a gate under scripts/cli without a Reuse Analysis row.
  But an architect only adds such a row if the upstream artifact-producing
  skill tells them to. Today the nw-design skill's Reuse-first DESIGN exit-gate
  prose scopes only NEW classes under src/, and its lenient-match note has only
  the class-name form -- so the gate's methodology unit has no row to match and
  degrades to a vacuous no-op.

  slice-05 closes the seam at the producing end. It extends the skill so the
  architect is instructed to declare methodology components -- new data SSOT
  under nWave/data, new skills under nWave/skills, new gates under scripts/cli
  -- not only src/ classes, and the lenient-match note gains the file-component
  path and stem form. Guidance and enforcement become one shape: the loop from
  skill guidance to architect-authored row to a passing gate closes end-to-end.

  # DDD-12 (skill scope extension). AT1 + AT2 are cross-artifact structural
  # assertions on the shipped nw-design/SKILL.md content (the skill-propagation
  # pattern, mirroring the sibling fix-design-reuse-first-gate slice-03
  # precedent: skill template heading/columns == a normative constant). The
  # coherence binding is that the prose names the EXACT methodology-path
  # defaults the production gate detects. AT3 is the recursive dogfood: the real
  # check_reuse_first_design.py gate (driving port, main(argv)) is run over a
  # self-contained fixture feature-delta that adds a methodology file under a
  # skill-named path -- it PASSes when the architect names it in the Reuse
  # Analysis, FAILs when omitted, proving the end-to-end loop closes.
  #
  # Layer 3. AT1/AT2 read the real skill file's bytes (example-only, no PBT --
  # single structural-content assertions over a shipped asset). AT3 drives the
  # real gate over a real tmp_path git repository (real-io, example-based, no
  # PBT per Mandate 9 v2 OR-reduction). Read-only over both assets (Mandate 8).

  @slice-05 @walking_skeleton @driving_port @contract-shape:pure-function
  Scenario: The skill's reuse-first exit gate instructs declaring methodology components
    Given the nw-design skill and the gate's methodology-path defaults
    When the architect reads the skill's reuse-first exit-gate guidance
    Then the exit-gate guidance names every methodology-path the gate detects
    And reading the skill leaves it unchanged

  @slice-05 @driving_port @contract-shape:pure-function
  Scenario: The skill's lenient-match note documents the file-component path and stem forms
    Given the nw-design skill and the gate's methodology-path defaults
    When the architect reads the skill's lenient-match note
    Then the lenient-match note documents the methodology file-component path form
    And the lenient-match note documents the methodology file-component stem form
    And reading the skill leaves it unchanged

  @slice-05 @error @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: A feature adding a skill-declared methodology file is judged by whether the architect named it
    Given the nw-design skill instructs the architect to declare methodology components
    And a feature whose commits add a NEW methodology file under "<methodology_path>"
    And the feature <naming> that NEW methodology file in its Reuse Analysis section
    When the architect runs the reuse-first gate on the feature's commit range with methodology detection
    Then the methodology-aware commit range reaches the <naming> verdict
    And running the reuse-first gate leaves the feature repository unchanged

    Examples:
      | methodology_path | naming |
      | nWave/data       | names  |
      | nWave/data       | omits  |
