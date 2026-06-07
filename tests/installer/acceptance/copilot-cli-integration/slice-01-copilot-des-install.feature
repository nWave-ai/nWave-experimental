@feature-copilot-cli-integration @slice-01
Feature: An operator who uses Copilot CLI gets nWave DES enforcement wired in on install

  An operator who runs GitHub Copilot CLI must be able to install nWave and have
  the DES enforcement hook wired into their Copilot runtime, so that the same
  TDD enforcement that protects Claude Code and Codex sessions also protects
  Copilot sessions — without the operator hand-editing any config file.

  The empirical spike against @github/copilot v1.0.54 established two binding
  constraints the install MUST honor:
    - FM-1: an inline hooks block in settings.json does NOT fire; the hook config
      MUST live as a file in the hooks directory.
    - FS-1: each hook entry MUST be double-nested ({matcher, hooks:[{type, bash}]}),
      not flat.

  This slice proves the install-time contract only: detect Copilot, write the
  hook config to the right place in the right shape, and uninstall it cleanly
  while preserving any hook the operator authored themselves. It does NOT drive
  the live Copilot binary — hook-firing was validated separately by the spike and
  is the scope of later slices.

  # Driving port: the production install pipeline invoked as a real Python
  # subprocess (`python -m nwave_ai.cli install/uninstall --target <tmp>`) with
  # Copilot detected via a tmp COPILOT_HOME. Layer 3 (subprocess / FS acceptance)
  # — example-only (Mandate 11). The only driven ports are the real filesystem
  # (tmp COPILOT_HOME tree) and the COPILOT_HOME environment variable.
  # Mandate-13: ATs drive via subprocess + filesystem assertions only; zero
  # direct production import; zero live `copilot` binary invocation.

  @walking_skeleton @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: Installing nWave for a Copilot operator wires the DES hook into the Copilot hooks directory
    Given an operator whose Copilot runtime is present but carries no nWave hook
    When the operator installs nWave for their Copilot runtime
    Then the Copilot hooks directory carries an nWave DES hook config file
    And the nWave DES hook config invokes the shared DES adapter
    And no inline hook block is written into the Copilot settings file

  @driving_port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: The written DES hook config has the double-nested shape Copilot honors
    Given an operator whose Copilot runtime is present but carries no nWave hook
    And the operator has installed nWave for their Copilot runtime
    When the operator inspects the installed nWave DES hook config
    Then each hook entry groups its handlers under a nested handler list
    And each handler names its kind and the command Copilot runs
    And the hook config is not written in the flat single-handler shape

  @driving_port @real-io @slice-01 @contract-shape:unbounded-preservation
  Scenario: Uninstalling nWave removes its Copilot hook and leaves the operator's own hook intact
    Given an operator whose Copilot runtime already carries a hook they authored themselves
    And the operator has installed nWave for their Copilot runtime
    When the operator uninstalls nWave from their Copilot runtime
    Then the nWave DES hook config is gone from the Copilot hooks directory
    And no orphan nWave hook artifact is left behind
    And the operator's own Copilot hook is preserved unchanged
