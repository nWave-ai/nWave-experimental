# Feature: Backup Retention Policy — Walking Skeleton
# Source of truth: docs/feature/backup-retention-policy/discuss/scope.md
# Persona: Marco — solo developer on laptop (D5)
# Strategy: C (Real local) — real filesystem on tmp_path, real BackupManager,
#   real ~/.nwave/global-config.json reads via HOME/CLAUDE_CONFIG_DIR isolation.

Feature: Backup retention prevents silent disk consumption on repeat installs
  As Marco, a solo developer iterating on nWave from my laptop
  I want repeated installs to keep at most a sane number of backups
  So that my laptop SSD does not silently fill while I iterate

  Background:
    Given Marco has a clean Claude config home at the test sandbox

  @walking_skeleton @real-io @driving_adapter @adapter-integration @S3
  Scenario: Eleventh install prunes the oldest backup so disk usage stays bounded
    Given Marco has 10 backup directories from prior installs:
      | nwave-install-20260101-100000 |
      | nwave-install-20260102-100000 |
      | nwave-install-20260103-100000 |
      | nwave-install-20260104-100000 |
      | nwave-install-20260105-100000 |
      | nwave-install-20260106-100000 |
      | nwave-install-20260107-100000 |
      | nwave-install-20260108-100000 |
      | nwave-install-20260109-100000 |
      | nwave-install-20260110-100000 |
    And no override exists for the maximum backup count
    And a new backup directory "nwave-install-20260111-100000" has just been created by the install
    When Marco lets the install apply its retention policy
    Then the oldest backup "nwave-install-20260101-100000" is removed from disk
    And exactly 10 backup directories remain on disk
    And the surviving backups are the 10 most recent ones

  @walking_skeleton @real-io @driving_adapter @adapter-integration @S5
  Scenario: After retention prunes, restore still finds Marco's most recent backup
    Given Marco has 11 backup directories from prior installs spanning several days
    And the maximum backup count is the default of 10
    And the install has just applied retention, removing the oldest backup
    When Marco asks the installer to restore from the most recent backup
    Then the restore picks the most recent surviving backup
    And the restored agents and commands match the contents of that backup

  @walking_skeleton @real-io @driving_adapter @adapter-integration @S3 @outer_seam_wiring
  Scenario: Eleventh install through the installer entry point prunes the oldest backup
    # DWD-10: outer-seam wiring proof — drives NWaveInstaller.create_backup()
    # (the seam main() invokes), not BackupManager.apply_retention() directly.
    # Without this scenario, retention can be unwired from the install flow and
    # the inner-seam tests still pass (D1 BLOCKER from post-DELIVER review).
    Given Marco has 10 prior install backups spanning the first ten days of January 2026
    And Marco has an existing nWave install with agents and commands on disk
    And no override exists for the maximum backup count
    When Marco runs the installer's create-backup phase through the installer entry point
    Then exactly 10 backup directories matching "nwave-*" remain on disk
    And the oldest backup "nwave-install-20260101-100000" is removed from disk
    And the new install backup created by the installer is still on disk
