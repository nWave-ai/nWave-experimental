Feature: Hook Protocol Conformance
  As a developer using nWave hooks
  I want hooks to follow Claude Code's protocol for allow and block decisions
  So that allowing a tool invocation never triggers a "hook error" in the terminal

  Claude Code treats any stdout from a PreToolUse hook on exit 0 as a protocol
  error. The correct allow behavior is: exit 0 with empty stdout. Block behavior
  is: exit 2 (PreToolUse, PreWrite) or exit 0 with JSON (SubagentStop).
  This feature validates the contract between DES hooks and Claude Code for all
  four handler types: PreToolUse (Agent validation), SubagentStop (step
  completion), PreWrite (session guard for Write/Edit), and PostToolUse
  (failure notification injection).

  # Exit code difference: PreToolUse and PreWrite use exit code 2 to block because
  # Claude Code's PreToolUse protocol reads stdout ONLY on exit 2 and ignores it
  # on exit 0. SubagentStop uses exit 0 with JSON because Claude Code's SubagentStop
  # protocol reads stdout on exit 0 (exit 2 causes stdout to be ignored entirely).

  # ---------------------------------------------------------------------------
  # PreToolUse scenarios
  # ---------------------------------------------------------------------------

  @e2e @hook-protocol @allow-path
  Scenario: PreToolUse allow produces no stdout
    Given a non-DES agent invocation with no step markers
    When the PreToolUse hook processes the invocation
    Then the hook exits with code 0
    And stdout is completely empty

  @e2e @hook-protocol
  Scenario: PreToolUse block produces structured JSON on stdout
    Given an agent invocation referencing step "01-01" without DES markers
    When the PreToolUse hook processes the invocation
    Then the hook exits with code 2
    And stdout contains a block decision with a reason

  # ---------------------------------------------------------------------------
  # SubagentStop scenarios
  # ---------------------------------------------------------------------------

  @e2e @hook-protocol @allow-path
  Scenario: SubagentStop allow produces no stdout
    Given a completed non-DES agent with no step markers in its transcript
    When the SubagentStop hook processes the completion
    Then the hook exits with code 0
    And stdout is completely empty

  @e2e @hook-protocol
  Scenario: SubagentStop block produces structured JSON on stdout
    Given a completed DES agent whose step validation fails
    When the SubagentStop hook processes the completion
    Then the hook exits with code 0
    And stdout contains a block decision with a reason

  # ---------------------------------------------------------------------------
  # PreWrite scenarios
  # ---------------------------------------------------------------------------

  @e2e @hook-protocol @allow-path
  Scenario: PreWrite allow produces no stdout for non-protected files
    Given a write to a non-protected file "docs/feature/my-feature/notes.md"
    When the PreWrite hook processes the write request
    Then the hook exits with code 0
    And stdout is completely empty

  @e2e @hook-protocol
  Scenario: PreWrite block produces structured JSON for execution log writes
    Given a write to the execution log "docs/feature/my-feature/deliver/execution-log.json"
    When the PreWrite hook processes the write request
    Then the hook exits with code 2
    And stdout contains a block decision with a reason

  # ---------------------------------------------------------------------------
  # PostToolUse scenarios
  # ---------------------------------------------------------------------------

  @e2e @hook-protocol
  Scenario: PostToolUse passthrough produces empty JSON on stdout
    Given a non-DES tool completion event
    When the PostToolUse hook processes the completion
    Then the hook exits with code 0
    And stdout contains only an empty JSON object

  @e2e @hook-protocol
  Scenario: PostToolUse with failure notification produces additional context
    Given a DES tool completion event with a prior failure in the audit log
    When the PostToolUse hook processes the completion
    Then the hook exits with code 0
    And stdout contains additional context for the orchestrator

  # ---------------------------------------------------------------------------
  # Error handling scenarios
  # ---------------------------------------------------------------------------

  @e2e @hook-protocol @error-path
  Scenario: Hook handles malformed JSON on stdin gracefully
    Given malformed JSON data on stdin for the PreToolUse hook
    When the PreToolUse hook processes the invocation
    Then the hook exits with a non-zero error code
    And stdout contains an error response

  @e2e @hook-protocol @error-path
  Scenario: Hook handles empty stdin gracefully
    Given completely empty stdin for the PreToolUse hook
    When the PreToolUse hook processes the invocation
    Then the hook exits with code 0
    And stdout is completely empty

  @e2e @hook-protocol @error-path
  Scenario: Hook handles missing tool name field gracefully
    Given a JSON payload without the required tool_name field for PreToolUse
    When the PreToolUse hook processes the invocation
    Then the hook exits with code 0
    And the hook does not crash
