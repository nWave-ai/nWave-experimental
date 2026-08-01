@feature-unified-event-store
Feature: A broken telemetry filesystem must refuse loudly, never write into the void

  Charter: docs/product/expectations/unified-event-store/
           as-a-store-operator-i-get-a-loud-startup-refusal-instead-of-a-silent-wrong-write-when-the.md

  A store operator needs the unified event store's startup probe to tell the
  truth about the telemetry substrate: exit 0 only when it genuinely can
  write, and refuse LOUD -- naming WHAT failed, WHY it matters, and HOW to
  fix it -- when it cannot. A store that reports success from an unreadable
  substrate is the exact silent-wrong-write this slice exists to prevent
  (DD-14).

  # Driving port (Mandate 13): Layer 1 walking-skeleton (subprocess, real
  # `des event-store-probe` CLI, terminal-wiring facet) for the ONE feature
  # WS; every other scenario drives IN-PROCESS via
  # des.cli.event_store_probe.main(argv, output=CapturingOutput()) --
  # Layer 2, content facet (nw-distill-port-treatment-policy "CLI = e2e by
  # construction is DISSOLVED").
  #
  # Contract shape (Mandate 14): bounded-change -- the probe's canary
  # write/flock/read/delete is a BOUNDED filesystem operation, never an
  # unbounded read.
  #
  # RED at HEAD (unified-event-store slice-02): UnifiedEventStoreAdapter /
  # StoreAvailabilityProbe are DISTILL-authored scaffolds whose methods
  # raise a bare AssertionError. Every scenario below fails for that reason
  # today -- a semantic AssertionError, never a collection/import error.

  @slice-02 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change @covers-R15
  Scenario: Store operator confirms the probe command is wired end-to-end against a healthy substrate
    Given the store operator has a real repo with a healthy telemetry substrate
    When the store operator runs the real des event-store-probe command against it
    Then the probe command is discoverable through des --help
    And the probe reports success with exit code zero

  @slice-02 @real-io @contract-shape:bounded-change
  Scenario Outline: Store operator gets a loud, precise refusal when the telemetry substrate cannot honor its contract
    Given the store operator's telemetry substrate <fault>
    When the store operator runs the event store probe in-process against the real des CLI entry
    Then the probe refuses with a non-zero exit code
    And the refusal names WHAT failed, WHY it matters, and HOW to fix it
    And the refusal names a path inside the store operator's own sandbox
    And nothing is written under the sandbox's telemetry root

    Examples:
      | fault                       |
      | is missing entirely         |
      | denies permission           |
      | is a file, not a directory  |

  @slice-02 @real-io @contract-shape:bounded-change
  Scenario: A healthy probe leaves no residue behind
    Given the store operator has a real repo with a healthy telemetry substrate
    When the store operator runs the event store probe in-process against the real des CLI entry
    Then the probe reports success with exit code zero
    And the sandbox's telemetry root is left with the same entries it started with
