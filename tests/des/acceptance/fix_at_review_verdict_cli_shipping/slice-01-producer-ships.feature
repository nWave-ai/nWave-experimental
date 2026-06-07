@feature-fix-at-review-verdict-cli-shipping
Feature: The AT-review verdict recorder ships to an installed instance
  # fix-at-review-verdict-cli-shipping — DISTILL (Quinn), 2026-05-29.
  # DESIGN SSOT: docs/feature/fix-at-review-verdict-cli-shipping/design/architecture.md + ADR-001.
  #
  # An operator on an installed instance can only clear the carpaccio
  # DISTILL->DELIVER gate when the verdict-recorder is present on their
  # machine. The recorder is shipped by the install step that copies every
  # canonical recorder-module from the source tree the installer treats as
  # its single source of truth. Today the recorder lives outside that source
  # tree, so it is never copied. This slice relocates the recorder into the
  # source tree the installer copies from, and pins it into the frozen
  # ship-floor so it can never silently drop out again.
  #
  # Driving port (Mandate-13): the production install discovery surface
  # (`des_plugin._discover_shims` run against the real source tree — the
  # install plugin's own production helper, the same invocation the install
  # performs) for the shipped-set witness; the `des.cli` module subprocess
  # (`python -m des.cli.at_review_verdict`, Layer-3 subprocess) for the
  # import-clean witness. NO direct domain import; NO behavioral AT under
  # tests/des/unit/.
  #
  # Layer 3 (subprocess / install-surface acceptance) — example-only, no PBT
  # (Mandate 9/11). The shipped-set membership is a closed-world finite
  # invariant; the import-clean check is a single subprocess example.
  #
  # ADR-028 RED scaffold: these scenarios are UNSKIPPED and FAIL on current
  # master for the RIGHT reason — the recorder still lives outside the source
  # tree the installer copies from, so it is absent from the discovered ship
  # set and absent from the frozen ship-floor, and it cannot be imported from
  # the installed recorder namespace.

  @slice-01 @driving_port @walking_skeleton @contract-shape:unbounded-preservation
  Scenario: The shipped recorder set includes the AT-review verdict recorder
    Given the install discovers every canonical recorder from the source tree it ships from
    When the operator lists the recorders that will ship to an installed instance
    Then the AT-review verdict recorder is among the recorders that will ship
    And no other shipped recorder is dropped

  @slice-01 @driving_port @contract-shape:pure-function
  Scenario: The relocated recorder is importable from the installed recorder namespace
    Given an installed-shape runtime where the recorder lives in the canonical recorder namespace
    When the operator loads the AT-review verdict recorder from that namespace
    Then the recorder loads without error

  @slice-01 @driving_port @contract-shape:unbounded-preservation
  Scenario: The frozen ship-floor pins the AT-review verdict recorder against silent regression
    Given the frozen ship-floor that the install guarantees never to drop
    When the operator inspects the frozen ship-floor
    Then the AT-review verdict recorder is named in the frozen ship-floor
