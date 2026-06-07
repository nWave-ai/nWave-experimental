@feature-fix-design-component-manifest
Feature: A feature's manifest readiness resolves to one of four known states

  When a feature reaches delivery, the downstream gates need a single, shared
  verdict on its component manifest: is it ready, honestly empty, missing, or
  broken. This slice delivers that shared classifier -- the one resolver both
  downstream gate features import rather than each writing its own.

  The classifier answers shape only -- present, well-formed, declared. It never
  silently passes a missing manifest: an absent manifest with no explicit waiver
  resolves to the missing state and the caller refuses. A feature whose design
  genuinely has no unbounded input may carry a reviewer-vetoable waiver, and an
  architect who has looked and found nothing may declare an honest empty list --
  both resolve to the same accepted state without ever silently skipping.

  Read in sequence after slice-02: slice-01 and slice-02 judged one manifest in
  isolation; this slice classifies a whole feature's manifest readiness into the
  four states the gate family is built around.

  # Driving port: the resolve_manifest_state() shared resolver.
  # Layer 3 (FS acceptance) -- example-only outline (Mandate 9/11). The
  # four-state shape universe is enumerated as Scenario Outline rows, not a
  # Hypothesis @given. The resolver classifies SHAPE ONLY -- symbol grounding
  # is the caller's separate validate tool call (residuality F6).

  Background:
    Given a feature whose design directory has been prepared

  @slice-03 @driving_port @contract-shape:pure-function
  Scenario: A feature with a present manifest declaring input domains is ready
    Given the architect has written a well-formed component manifest
    When the manifest readiness is resolved
    Then the manifest readiness is valid with declared input domains

  @slice-03 @driving_port @contract-shape:pure-function
  Scenario: A feature whose architect declared an honest empty list is accepted
    Given the architect has declared an honestly empty component manifest
    When the manifest readiness is resolved
    Then the manifest readiness is honestly empty

  @slice-03 @error @driving_port @contract-shape:pure-function
  Scenario Outline: A feature is classified by the state of its component manifest
    Given the feature's component manifest is <situation>
    When the manifest readiness is resolved
    Then the manifest readiness is <state>

    Examples:
      | situation                                            | state                            |
      | absent with no waiver                                | absent                           |
      | absent with a not-applicable waiver and a reason     | honestly empty                   |
      | present but malformed                                | malformed                        |
