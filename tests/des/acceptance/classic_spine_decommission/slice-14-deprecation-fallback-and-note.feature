@feature-classic-spine-decommission
Feature: The deprecated classic spine still works as a fallback floor
  As an nWave framework developer completing release N of the staged cutover
  I want a deprecated classic dispatch to still run to completion, delete no
    classic artifact, and ship a customer migration note
  So that classic remains a safe one-config-flip fallback until the N+1 removal

  # slice-14 of classic-spine-decommission. The deprecated-but-present
  # guarantees: a classic dispatch still runs to completion as a fallback; NO
  # classic artifact is deleted in release N; a customer migration note is
  # shipped (M8). The DELETE sweep is the N+1 sibling epic.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only (Mandate 11).
  # state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: the `workflow.mode` resolver invoked by a DELIVER dispatch.

  # --- The fallback floor still works after deprecation ------------------------

  @slice-14 @driving_port @contract-shape:bounded-change
  Scenario: A classic dispatch still runs to completion as a deprecated fallback
    Given a project configured for the classic spine
    When a DELIVER dispatch runs
    Then the classic dispatch still runs to completion as a fallback
    And a classic-spine deprecation advisory is emitted

  # --- Release N deletes no classic artifact -----------------------------------

  @slice-14 @driving_port @contract-shape:unbounded-preservation
  Scenario Outline: Marking classic deprecated deletes no classic artifact
    Given a project configured for the classic spine
    When a DELIVER dispatch runs
    Then the classic artifact "<artifact>" is still present

    Examples: classic artifacts that survive release N untouched
      | artifact                       |
      | src/des/cli/roadmap.py          |
      | src/des/domain/roadmap_schema.py|
      | nWave/skills/nw-roadmap         |
      | nWave/tasks/nw/roadmap.md       |

  # --- M8 customer migration note ----------------------------------------------

  @slice-14 @driving_port @contract-shape:bounded-change
  Scenario: A customer migration note is shipped with the deprecation
    Given a project configured for the classic spine
    When a DELIVER dispatch runs
    Then a customer migration note is shipped
