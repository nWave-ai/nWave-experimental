@feature-fix-wave-marker-bypass-benign-passthrough @slice-02
Feature: The hook contract tests assert the hook's intrinsic decision, not the developer's working-tree floor
  As an nWave maintainer running the hook contract suite on a branch with a wave floor armed
  I want the contract-test harness to assert the hook's INTRINSIC decision against a clean
    injected floor
  So that the contract tests are green regardless of the developer's live working-tree floor and
    the env-coupling fragility (the 9 reds) is removed

  # slice-02 of fix-wave-marker-bypass-benign-passthrough -- the test-isolation
  # invariant (Fix-2, AT-7). The hook contract tests
  # (tests/bugs/des/task-to-agent-migration/acceptance/test_agent_tool_hook_processing.py)
  # invoke the production handle_pre_tool_use in-process via the claude_code_hook_stdin
  # fixture. At HEAD that fixture takes tmp_path but NEVER uses it: the production
  # PreToolUseService sources its wave floor off Path.cwd() (pre_tool_use_service.py:439,
  # WaveActiveReader.read(Path.cwd())), so the in-process handler reads the developer's
  # LIVE .nwave/wave-active/active.json. The hook decision is therefore COUPLED to the
  # working-tree floor: a discriminating partial-context dispatch is BLOCKED under a live
  # floor and ALLOWED with none -- the test passes or fails by accident of the developer's
  # tree, not by the hook's intrinsic logic.
  #
  # AT-7 is the falsifiable witness of isolation. It drives the SAME production driving
  # port the contract tests use (handle_pre_tool_use, Layer-3 composition, real FS floor)
  # and asserts the harness decision is a function ONLY of the floor INJECTED into the
  # fixture's clean tmp_path root, INDEPENDENT of whatever floor is armed in the live
  # working tree. To make this un-gameable the witness ARMS a real, NON-clean floor in the
  # working tree (a different wave than the injected one) and proves the decision tracks
  # the INJECTED floor, never the live one.
  #
  # Discriminating probe: a PARTIAL-context dispatch (DES-PROJECT-ID + DES-STEP-ID, no
  # DES-VALIDATION) -> carries_partial_wave_context == True -> BLOCK iff a floor is armed,
  # ALLOW under a clean root. Its decision FLIPS on floor identity, so it witnesses which
  # floor the harness actually read (a fully-markerless prompt cannot witness isolation --
  # it ALLOWs under every floor).
  #
  # HEAD verdict (active-RED): the fixture ignores tmp_path -> the harness decision is
  # coupled to the live working-tree floor -> AT-7's "intrinsic / injected-floor-only"
  # assertions fail for the right reason (semantic AssertionError). slice-02 wires
  # tmp_path as the handler's CWD/store-root -> the harness reads the injected clean floor
  # -> GREEN.
  #
  # Driving port: the production handle_pre_tool_use hook adapter (Layer-3 composition),
  # exercised through the SAME claude_code_hook_stdin fixture path the contract tests use.
  # Observable: the hook decision (exit 0 allow / exit 2 block) -- the exact surface a
  # Claude Code hook emits. @real-io: real filesystem floor under tmp_path + the live tree.

  @slice-02 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: The contract-test harness asserts the intrinsic ALLOW against a clean injected floor while a non-clean floor is armed live
    Given a non-clean wave floor is armed in the developer's live working tree
    And the contract-test harness injects a clean isolated floor root
    When the harness validates a partial-context dispatch through the hook
    Then the hook decision reflects the injected clean floor, not the live working-tree floor
    And the harness decision is ALLOW

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The contract-test harness asserts the intrinsic BLOCK against an injected armed floor while the live working tree is clean
    Given the developer's live working tree has no wave floor armed
    And the contract-test harness injects an armed "design" floor
    When the harness validates a partial-context dispatch through the hook
    Then the hook decision reflects the injected armed floor, not the live working-tree floor
    And the harness decision is BLOCK
