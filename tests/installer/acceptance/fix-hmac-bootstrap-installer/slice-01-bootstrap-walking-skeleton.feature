@feature-fix-hmac-bootstrap-installer @slice-01
Feature: A fresh nWave install gives the operator a usable HMAC reviewer signing surface

  An operator running the nWave installer on a fresh laptop must be able to
  dispatch the spine end-to-end without first knowing about the HMAC reviewer
  signing key environment variable. The installer auto-provisions a per-project
  reviewer signing key file; the provisioning is idempotent across re-installs;
  and the operator can still override the key source via the
  NWAVE_REVIEWER_SIGNING_KEY environment variable.

  This walking-skeleton slice proves the end-to-end seam between the install
  pipeline and the operator-observable HMAC surface. Subsequent slices add
  key rotation, multi-user keychain, and operator monitoring.

  # Driving port: scripts/install/install_nwave.py install pipeline (driving
  # subprocess); the reviewer_signing_plugin is the in-process production
  # composition exercised against a tmp_path target. Layer 3 (subprocess /
  # FS acceptance) — example-only walking skeleton (Mandate 11).

  @slice-01 @walking-skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A fresh install auto-provisions an HMAC reviewer signing key
    Given the operator has a fresh target directory with no nWave installation
    And no signing key environment variable is set in the operator environment
    When the operator runs the nWave install pipeline against the target
    Then the target carries a reviewer signing key file with 64 hex characters of randomness
    And the install verification reports the reviewer signing key as present at its path
    And on POSIX the reviewer signing key file mode is restricted to the operator

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: Re-running the installer leaves the existing signing key untouched
    Given the operator has a target with a previously provisioned reviewer signing key
    And no signing key environment variable is set in the operator environment
    When the operator re-runs the nWave install pipeline against the target
    Then the reviewer signing key file is byte-identical to the previously provisioned key
    And the reviewer signing key file mode bits are unchanged

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Operator override via the signing key environment variable suppresses provisioning
    Given the operator has a fresh target directory with no nWave installation
    And the operator has set the signing key environment variable to an override value
    When the operator runs the nWave install pipeline against the target
    Then the target carries no reviewer signing key file
    And the install verification names the signing key environment variable as the key source
