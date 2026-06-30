@feature-fix-subagent-stop-fenced-marker-false-block
Feature: SubagentStop ignores DES markers documented inside code fences

  A read-only return that merely DOCUMENTS a DES dispatch marker inside a code
  fence (or an inline backtick span) must not be mistaken for a real directive.
  The SubagentStop return-resolver strips fenced / inline-code regions before
  resolving the DES context, so a documented marker no longer false-blocks the
  run — while a real marker outside any fence still resolves the context as before.

  @slice-01 @contract-shape:bounded-change @driving_port @real-io
  Scenario: A marker documented inside a triple-backtick fence is ignored
    Given a read-only agent return that documents a DES marker inside a fenced block
    When the SubagentStop resolver resolves the DES context from the return
    Then no DES dispatch context is resolved from the documented marker

  @slice-01 @contract-shape:bounded-change @driving_port @real-io
  Scenario: A marker quoted in an inline code span is ignored
    Given a read-only agent return that quotes a DES marker in an inline code span
    When the SubagentStop resolver resolves the DES context from the return
    Then no DES dispatch context is resolved from the documented marker

  @slice-01 @contract-shape:unbounded-preservation @driving_port @real-io
  Scenario: A real marker outside any fence still resolves the context
    Given a read-only agent return carrying a real DES marker outside any fence
    When the SubagentStop resolver resolves the DES context from the return
    Then the DES dispatch context is resolved from the real marker

  @slice-01 @contract-shape:unbounded-preservation @driving_port @real-io
  Scenario: A return with no marker resolves no context
    Given a read-only agent return that carries no DES marker at all
    When the SubagentStop resolver resolves the DES context from the return
    Then no DES dispatch context is resolved from the documented marker
