@attribution-activation-coupling @upgrade-migration
Feature: Upgrading cleans up the retired Claude-settings credit safely
  The old release wrote the credit into the Claude settings file. On upgrade the
  retired block is cleaned up — but a value the developer authored themselves is
  never stomped. Install cleans legacy settings safely and preserves the runtime
  preference; it does not register a second hook.

  # AB-4 — upgrade removes a previously nWave-written credit; preference preserved.
  @ab-4 @driving_port @contract-shape:bounded-change
  Scenario: Upgrade removes the legacy nWave-managed credit and preserves preference
    Given a active repo
    And an nWave-managed legacy attribution credit in the Claude settings
    And attribution preference is on
    When the operator installs nWave
    Then the legacy attribution credit is removed from the Claude settings
    And the attribution preference is preserved

  # AB-5 — upgrade preserves a user-modified credit (classifier baseline).
  @ab-5 @driving_port @error @contract-shape:bounded-change
  Scenario: Upgrade preserves a user-modified credit without changes
    Given a active repo
    And a user-modified legacy attribution credit in the Claude settings
    And attribution preference is on
    When the operator installs nWave
    Then the user-authored attribution credit is preserved unchanged

  # AB-4 sibling — a fresh install preserves preference without writing settings credit.
  @ab-4 @driving_port @contract-shape:bounded-change
  Scenario: A clean install preserves preference without writing the settings credit
    Given a active repo
    And no legacy attribution credit in the Claude settings
    And attribution preference is unset
    When the operator installs nWave
    Then no managed attribution credit is written to the Claude settings

  # AB-11 — migration over absent settings is fail-open (warn+skip, no raise).
  @ab-11 @error @contract-shape:unbounded-preservation
  Scenario: Install over an absent Claude settings file fails open
    Given a active repo
    And the Claude settings file is absent
    When the operator installs nWave
    Then the operation completes without error

  # AB-11 — migration over corrupt settings is fail-open (never stomps).
  @ab-11 @error @contract-shape:unbounded-preservation
  Scenario: Install over a corrupt Claude settings file leaves it untouched
    Given a active repo
    And the Claude settings file is corrupt
    When the operator installs nWave
    Then the operation completes without error
    And the Claude settings are left untouched
