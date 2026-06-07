@feature-copilot-cli-integration @slice-02
Feature: An operator's Copilot session actually fires the nWave DES hook end to end

  slice-01 proved the INSTALL behaviour: the production installer writes the
  nWave DES hook config into the Copilot hooks directory in the shape Copilot
  honors. This slice proves the next, decisive thing: that the installed hook
  ACTUALLY FIRES inside the real Copilot binary when an operator runs a session —
  the end-to-end firing proof Copilot integration ultimately rests on.

  The empirical spike against @github/copilot v1.0.54
  (docs/analysis/copilot-cli-prereq-spike-2026-05-28.md) established that the
  sessionStart event fires reliably on every non-interactive run, whereas the
  preToolUse event could not be triggered within the session-bootstrap timeout.
  This slice therefore pins the firing proof to sessionStart.

  # Driving port: the REAL `copilot` binary invoked as a subprocess against a
  # local mock OpenAI SSE server (BYOK offline mode: COPILOT_OFFLINE=true +
  # COPILOT_PROVIDER_BASE_URL), so the binary runs a full session without a
  # GitHub account or a real model. The observable outcome is a marker file the
  # installed hook writes when it fires — a real filesystem side-effect of the
  # real binary running the real hook. Layer 4+ (real-binary e2e): example-only
  # (Mandate 11); traditional assertions (Mandate 8 universe guard is layers 1-3).
  #
  # Mandate-13: the SUT is driven exclusively through the real `copilot`
  # subprocess; the only observation is the filesystem marker. Zero direct
  # production import of the hook logic.
  #
  # Tmp-isolation: a fake HOME and a tmp COPILOT_HOME are exported into every
  # subprocess; the real ~/.copilot/ is NEVER touched.
  #
  # Binary-availability: the bindings carry skipif(copilot binary absent) so this
  # e2e SKIPS gracefully (never fails) on CI runners / customer machines without
  # the binary. Absence != failure — the e2e proves the integration WHERE the
  # binary exists.
  #
  # CRUX FINDING (at-scaffold-notes-slice-02.md): slice-01's production
  # copilot_des_plugin installs the DES hook ONLY on preToolUse (a non-firing
  # event). The walking-skeleton scenario below is RED for the right reason
  # against slice-01 — slice-02 DELIVER MUST add a sessionStart hook entry for
  # the firing to be demonstrable.

  @walking_skeleton @driving_port @real-io @e2e @e2e_smoke @slice-02 @contract-shape:bounded-change
  Scenario: An operator who installs nWave sees their Copilot session fire the DES hook
    Given an operator whose Copilot runtime is present
    And the operator has installed nWave for their Copilot runtime
    When the operator runs a Copilot session
    Then the installed nWave hook fires during the Copilot session
    And the production install registered a hook on an event that actually fires

  @driving_port @real-io @e2e @e2e_smoke @slice-02 @contract-shape:bounded-change
  Scenario: A Copilot session-start hook fires reliably in the real binary
    Given an operator whose Copilot runtime is present
    And an nWave hook is wired to write a marker when a Copilot session starts
    When the operator runs a Copilot session
    Then the marker proves the hook fired during the Copilot session
    And the marker carries the content the hook was wired to write
