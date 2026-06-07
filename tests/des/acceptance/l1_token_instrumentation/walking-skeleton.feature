Feature: L1 Token Instrumentation — Walking Skeleton
  As an nWave operator running DES-instrumented agents
  I want each Claude assistant message's token usage captured in the audit log
  So that I have a baseline data point for cost projection and cache analytics

  The instrumentation is additive: the existing DES marker walk in
  subagent_stop_handler keeps emitting its events, and a parallel walk
  of the same transcript emits one AGENT_USAGE_OBSERVED event per
  assistant message that carries a valid `message.usage` block.

  Per D4 (fail-open), assistant messages missing a usage block are
  skipped silently. The hook MUST NOT fail because of token
  instrumentation.

  # ---------------------------------------------------------------------------
  # Walking Skeleton: real hook + real JsonlAuditLogWriter + real fixture
  # Drives S1 (capture), S2 (missing usage skipped), S3 (cache fields),
  # S5 (empty transcript). S4 (no DES regression) is enforced by running
  # the existing DES marker unit tests in the same suite.
  # ---------------------------------------------------------------------------

  @walking_skeleton @real-io @driving_adapter @adapter-integration
  Scenario: Token usage events are emitted for valid assistant messages
    Given a Claude transcript with four assistant messages
    And three of the four assistant messages carry a valid usage block
    And the audit writer points at a temporary log directory
    When the SubagentStop hook processes the transcript via the real adapter
    Then the audit log contains exactly 3 AGENT_USAGE_OBSERVED events
    And each event records input, cache_creation, cache_read, and output tokens
    And the assistant message without a usage block produces no event

  @real-io @driving_adapter @adapter-integration
  Scenario: Empty transcript produces no token usage events and no exception
    Given an empty Claude transcript
    And the audit writer points at a temporary log directory
    When the SubagentStop hook processes the transcript via the real adapter
    Then the audit log contains exactly 0 AGENT_USAGE_OBSERVED events
    And the hook exits without raising an exception
