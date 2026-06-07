# Scenario SSOT for slice-01 of crafter-design-adherence-enforcement (#63 INPUT-b).
# Executable mirror: test_slice01_design_context_content_gate.py (plain-pytest,
# matching the established atdd_pure_dispatch_lifecycle sibling convention —
# docstring-Gherkin + parametrize, Layer-3 composition through the PreToolUse
# driving port). This .feature is the human-readable scenario contract.

@feature-crafter-design-adherence-enforcement
Feature: Crafter dispatch carries the architecture it must follow
  As the operator running the spine
  I want a crafter dispatch refused when its DESIGN_CONTEXT carries no architecture
  So the codebase does not drift or duplicate because the crafter never saw the design

  @slice-01 @walking-skeleton @driving_port @in-memory @contract-shape:pure-function
  Scenario Outline: A dispatch whose DESIGN_CONTEXT carries no architecture is refused
    Given a crafter dispatch whose DESIGN_CONTEXT body is "<citation_free_body>"
    When the dispatch is validated through the PreToolUse driving port
    Then the dispatch is refused
    And the refusal names the missing DESIGN_CONTEXT content

    Examples:
      | citation_free_body          |
      | empty                       |
      | whitespace only             |
      | the template placeholder    |
      | the no-design-artifacts text|
      | citation-free prose         |

  @slice-01 @driving_port @in-memory @contract-shape:pure-function
  Scenario Outline: A dispatch whose DESIGN_CONTEXT cites real architecture passes
    Given a crafter dispatch whose DESIGN_CONTEXT body cites "<architecture_citation>"
    When the dispatch is validated through the PreToolUse driving port
    Then the dispatch is allowed

    Examples:
      | architecture_citation                 |
      | a DDD decision id                     |
      | an ADR id                             |
      | a SYS contract id                     |
      | a feature-delta.md DESIGN path        |
      | the brief.md component inventory      |

  @slice-01 @driving_port @in-memory @contract-shape:pure-function
  Scenario: A DESIGN_CONTEXT heading with an empty body is refused
    Given a crafter dispatch that carries the DESIGN_CONTEXT heading but leaves its body empty
    When the dispatch is validated through the PreToolUse driving port
    Then the dispatch is refused
    And the refusal names the missing DESIGN_CONTEXT content
