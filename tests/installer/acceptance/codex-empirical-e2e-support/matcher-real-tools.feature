# Feature: Matcher targets only Codex-real tool names
# Story: US-3 (slice-04)
# FM closed: FM-3 (matcher contained "Task" which Codex never emits in PreToolUse)
# Whitelist source: tool names observed on the running Codex host.

Feature: Codex hook matcher lists only observed Codex tool names
  As a developer using nwave-ai with --platform codex
  I want the matcher to reference only tools Codex actually emits in PreToolUse events
  So that DES coverage corresponds to real protection, not fictional symmetry with Claude Code

  Background:
    Given a clean Codex environment with no prior nWave hooks

  @us-3 @slice-04 @driving_port @real-io
  Scenario: Installed matcher contains no reference to the Claude-Code-only Task tool
    When the nwave-ai installer is run with --platform codex
    Then the PreToolUse matcher regex contains zero occurrences of the literal "Task"
    And the matcher does not match a tool named "Task"

  @us-3 @slice-04 @driving_port @real-io @property
  Scenario: Every alternation in the matcher belongs to the observed Codex tool whitelist
    When the nwave-ai installer is run with --platform codex
    Then every alternation in the PreToolUse matcher regex is a member of the vetted Codex tool whitelist
    And the whitelist is sourced from an observation of the running host

  @us-3 @slice-04 @driving_port @real-io
  Scenario: Installed matcher matches the tool name the running host emits
    When the nwave-ai installer is run with --platform codex
    Then the matcher regex matches the tool name "exec_command"

  @us-3 @slice-04 @infrastructure-failure @error
  Scenario: Matcher rejects unregistered tool names
    When the nwave-ai installer is run with --platform codex
    Then the matcher regex does not match a fabricated tool name "FictionalTool"
    And the matcher regex does not match the empty string

  @us-3 @slice-04 @infrastructure-failure @error
  Scenario: Matcher does not match Claude-Code-only tool names
    When the nwave-ai installer is run with --platform codex
    Then the matcher regex does not match the tool name "Task"
    And the matcher regex does not match the tool name "Read"
    And the matcher regex does not match the tool name "Edit"
    And the matcher regex does not match the tool name "Bash"
    And the matcher regex does not match the tool name "apply_patch"
