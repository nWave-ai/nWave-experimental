@feature-nwave-flow-v2-enforcement @slice-04
Feature: Running /nw-discuss deterministically arms the active wave
  As an nWave user starting a wave
  I want the harness to recognise the literal /nw-discuss command itself
    -- before any model turn, independent of any skill load --
  So that the wave's gates have a deterministic wave-active signal to scope to,
    and a wave I started is recognised even if the LLM never reloads its skill

  # slice-04 of nwave-flow-v2-enforcement -- THE ENFORCEMENT WALKING SKELETON
  # (DISCUSS Walking-Skeleton Strategy A + DESIGN slice-04 code-design). The
  # thinnest honest end-to-end vertical that proves the deterministic wave-active
  # anchor: the literal /nw-discuss arriving as raw prompt text -> the real
  # prompt-submission hook -> a COMMAND-provenance record written to the
  # wave-active floor. This is the seam EVERY later gate (slice-06/07 + the
  # follow-on wave migrations) hangs on.
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 4 wiring_e2e): the REAL
  # prompt-submission hook process, invoked as a subprocess
  # (`python -m des.adapters.drivers.hooks.user_prompt_submit_handler`) with the
  # runtime's stdin JSON carrying the raw prompt. The WaveActiveAnchorPort /
  # WaveActiveWriter are NEVER imported-and-called at the step boundary (that
  # would collapse the e2e proof into a unit test). The observable surface is the
  # wave-active FLOOR FILE the hook writes under project_root -- read back through
  # the production WaveActiveReader (the floor is the driven-internal port; the
  # read-back observes the effect, it is not the SUT).
  #
  # DORMANT-SEAM RECONCILIATION (D11 / S3): the DESIGN driving-surface declares
  # the prompt-submission anchor (on_prompt_submitted) + the WaveActiveWriter.arm
  # write reached from the real submission hook as net-new load-bearing seams.
  # THIS walking skeleton names THAT exact seam (the submission hook arming the
  # floor) as the port it drives, drives it through the real hook entry point, and
  # asserts the observable effect (a COMMAND record on the floor). The seam is
  # therefore witnessed end-to-end, not shipped dormant.
  #
  # DETERMINISM (K4 cross-runtime crux): the /nw-discuss literal arrives as plain
  # prompt text on every runtime; the anchor is regex/parse over that text, NON-
  # LLM. The arm happens whether or not a model turn or skill load ever occurs --
  # this scenario asserts the floor is armed from the submission alone.
  #
  # RED-for-right-reason (ADR-025 + ADR-028, pre-DELIVER fail-for-right-reason):
  # `user_prompt_submit_handler.handle_user_prompt_submit` is a RED scaffold that
  # raises AssertionError, so the subprocess writes NO floor file. The Then-steps
  # read the absent floor through WaveActiveReader and fail with a semantic
  # AssertionError (no record armed / wrong wave / wrong provenance) -- never a
  # collection / import / setup error in the test process (the step module imports
  # only test-local types). The ATs PASS once DELIVER ships the anchor port + the
  # writer adapter + the handler wiring + the router `user-prompt-submit` command.

  @slice-04 @walking_skeleton @driving_port @wiring_e2e @real-io @contract-shape:bounded-change
  Scenario: Typing the discuss command arms the discuss wave deterministically
    Given a clean project where no wave is active
    When the user submits the prompt that starts the discuss wave
    Then the discuss wave is recorded as active in the project
    And the wave was armed deterministically from the command, not self-reported
    And no other wave is recorded as active
