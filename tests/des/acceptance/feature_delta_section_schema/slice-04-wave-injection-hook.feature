@feature-feature-delta-section-schema @slice-04
Feature: Wave-injection is fired from the hooks-only OSS surface
  As an nWave maintainer on the OSS (hooks-only) tier
  I want the wave-injection projection fired from the hook surface, injecting the
    consumed-by-matched section rows into the dispatched wave's prompt
  So that each wave receives exactly its sections using Python and the filesystem only

  # slice-04 of feature-delta-section-schema -- ADR-FLOW-007 §S.6 (OSS hooks-only).
  # DRIVING PORT (Mandate-13, Layer 3 subprocess): `des feature-delta-schema inject
  # --wave <w>` -- the same pure projection a PreToolUse hook composes in-process
  # (Invariant 4: NO sequencer, NO engine; Python + filesystem only). The observable
  # is the projected rows on stdout + exit 0.
  # Active-RED: at HEAD the scaffold raises, so inject exits non-zero.

  @slice-04 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: Wave-injection fires from the hook surface for a consuming wave
    When the schema injects sections for the design wave
    Then the projected rows include the section the design wave consumes

  @slice-04 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The injection surface is hooks-only and Python-only
    When the schema injects sections for the design wave
    Then the injection runs with Python and the filesystem only

  @slice-04 @driving_port @real-io @property @error @contract-shape:pure-function
  Scenario: Injection is a pure filter empty for a wave that consumes nothing
    When the schema injects sections for the discover wave
    Then the projection for a non-consuming wave is empty
