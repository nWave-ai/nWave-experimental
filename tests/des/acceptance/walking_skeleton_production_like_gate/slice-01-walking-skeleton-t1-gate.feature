@feature-walking-skeleton-production-like-gate
Feature: A delivered feature is proven against the artifact a consumer installs
  As an nWave framework developer finishing a feature
  I want feature-end to run the walking-skeleton test against the delivered
    artifact installed into a clean prefix
  So that "feature done" means the installed artifact works, not just the
    dev tree

  # carpaccio slice-01 (DESIGN slice-01). THE walking skeleton: the thinnest
  # end-to-end vertical, and the gate run against the gate's OWN installed
  # artifact (DESIGN slice plan). Implements RCA root-cause A.
  #
  # This slice's @walking-skeleton AT is genuinely end-to-end (DESIGN D6):
  # it builds the real artifact via build_dist.py, installs it with a real
  # `pip install --target` into a fresh prefix, and runs the gate as a
  # `des walking-skeleton-gate` subprocess against that prefix.
  # No fixture-folding: the subject is the production gate, the composition is
  # the real build+install transform, the delivery form is the .whl.
  #
  # RM-1 self-probe: the walking skeleton additionally triggers a real
  # SubagentStop and asserts the WalkingSkeletonGateRan heartbeat appeared --
  # a probe that the probe is wired (Earned-Trust self-application).
  #
  # Layer 5 (WS @wiring_e2e): real stack, subprocess. Example-only, no PBT
  # (Mandate 9/11). Traditional assertions permitted at layer 4+ (Mandate 8).
  #
  # Driving port: `des.cli.walking_skeleton_gate` (python -m subprocess) +
  # the DES feature-end SubagentStop hook branch.

  @slice-01 @walking-skeleton @wiring_e2e @driving_port @contract-shape:bounded-change
  Scenario: A delivered feature's walking skeleton passes against its installed artifact
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    When the feature-end gate verifies the walking skeleton against the delivered artifact
    Then the walking-skeleton gate reports PASS at tier of record T1
    And the gate records a positive walking-skeleton verification for the feature
    And the feature-end gate run emitted a walking-skeleton heartbeat before the verdict

  @slice-01 @walking-skeleton @wiring_e2e @driving_port @error @contract-shape:bounded-change
  Scenario: A delivered feature whose installed CLI is missing blocks feature-end
    Given a feature that ships a script-mode CLI with a walking-skeleton acceptance test
    And the script-mode CLI is absent from the installer distribution whitelist
    When the feature-end gate verifies the walking skeleton against the delivered artifact
    Then the walking-skeleton gate reports FAIL at tier of record T1
    And the gate diagnostic names the entry point absent from the installed tree
    And the feature is not marked done

  @slice-01 @wiring_e2e @driving_port @contract-shape:unbounded-preservation
  Scenario: Evaluating the gate leaves the developer's repository untouched
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    When the feature-end gate verifies the walking skeleton against the delivered artifact
    Then the walking-skeleton gate reports PASS at tier of record T1
    And the developer's repository working tree is unchanged
    And no file under the developer's source tree was written during the gate run
