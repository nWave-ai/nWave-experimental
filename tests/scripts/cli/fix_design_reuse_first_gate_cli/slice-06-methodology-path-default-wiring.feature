@feature-fix-design-reuse-first-gate-cli @slice-06
Feature: The reuse-first CLI detects methodology file-components BY DEFAULT

  slice-03 added file-component detection; slice-05 extended the nw-design skill
  prose to promise the architect that the CLI DEFAULTS to the published-language
  methodology paths -- nWave/data, nWave/skills, scripts/cli. But the impl wires
  --methodology-path with default=None, so file-component detection is
  default-OFF: a caller who omits the flag (CI, the post-DESIGN gate wiring)
  gets a vacuous PASS where a NEW methodology SSOT artifact ships unchallenged.
  The skill's published-language is literally false until the default is wired.

  slice-06 closes that drift: an added methodology file under a published-
  language path, absent from the Reuse Analysis, is rejected EVEN WHEN the
  architect omits --methodology-path. The default-on behaviour is the contract
  -- the blind-spot slice-03/05 close does not silently re-open for the no-flag
  caller.

  # DDD-9 default set / DDD-11 union verdict. Driving port:
  # scripts/cli/check_reuse_first_design.py invoked via main(argv) (Mandate-13:
  # the CLI argv entry, never a domain-function call). Driven ports (real I/O):
  # a real feature repository under tmp_path (a real commit adding a methodology
  # file) plus the feature-delta on the real filesystem. The detector reads the
  # feature's real commit-range name-status (added paths) -- file-component mode
  # keys methodology paths WITHOUT reading their bytes (DDD-11). This scenario
  # exercises the NO-FLAG path: no --methodology-path is passed, so the
  # published-language default set must be active. The existing slice-03 ATs all
  # pass the flag explicitly -- the no-flag default-on behaviour was never
  # pinned, which is WHY the default-off deviation shipped silently.
  # Layer 3 (FS + subprocess acceptance) with a real driven adapter -> @real-io,
  # example-based, assert_state_delta (Mandate 9 v2 OR-reduction: at least one
  # real driven adapter -> example-based, no PBT). Finite verdict set
  # (FAIL / preservation) -> example scenario, no @given.

  Background:
    Given a feature whose methodology source tree is tracked in a default-wired repository

  @slice-06 @error @driving_port @real-io @contract-shape:bounded-change
  Scenario: A committed methodology file absent from the Reuse Analysis is rejected without the methodology-path flag
    Given the feature's commits add a NEW methodology file under "nWave/data" to the default-wired repository
    And the default-wired feature does not name that NEW methodology file in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature's commit range without the methodology-path flag
    Then the default-wired commit range is rejected by the reuse-first check
    And the default-wired reuse-first check reports one NEW component
    And the reuse-first check without the methodology-path flag leaves the feature repository unchanged
