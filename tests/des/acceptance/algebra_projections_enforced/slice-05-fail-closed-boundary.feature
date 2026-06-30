@feature-algebra-projections-enforced
Feature: The registry-section check fails closed at the wave/registry boundary

  Maya runs the registry-section check naming a wave. Until now the check's
  boundary was a silent precursor: when the registry it must read was unreadable,
  the slice-01 shell printed a plain-text error to stderr and returned exit 1
  WITHOUT a structured verdict — degrade-by-exit, but not degrade-by-verdict, so a
  caller reading the JSON token saw nothing and had to guess. This LAST slice
  closes the boundary into TWO typed, closed-set verdicts that can never be a
  silent green and never a crash:

    * a wave the registry never declared (a non-canonical wave name) -> the check
      REJECTS with `unknown-wave` — a deterministic refusal, not a guess;
    * a known wave whose registry file is garbled or missing -> the check refuses
      to decide and degrades LOUD to `indeterminate` — a missing/garbled registry
      is NEVER a silent green.

  The happy path is preserved byte-stable: a known wave with a readable registry
  and an all-declared delta is still ACCEPTED. The boundary verdicts are
  un-gameable — never `accepted`, never a stacktrace.

  # DISCUSS slice-05 Slice Plan + DoD ("Unknown-wave -> REJECT; unreadable registry
  # -> INDETERMINATE (degrade-LOUD, never silent green)"). DESIGN DA-5 / DD-A5 (b):
  # unknown-wave -> REJECT, unreadable -> INDETERMINATE; mirrors
  # verify_wave_contract_coherence._indeterminate. Promotes the slice-01 degrade-LOUD
  # precursor (return 1 without a typed verdict) to closed §17-set verdicts
  # (`indeterminate` already a GateVerdict token; `unknown-wave` the additive REJECT).
  # Driving port: validate-feature-delta --require-registry-sections <wave>
  # [--waves-dir <dir>] --format=json (DESIGN Driving Ports). Layer 3 (subprocess/FS
  # acceptance) — example-only, no PBT (Mandate 9/11): the boundary is a finite,
  # enumerable closed set (unknown-wave / garbled / absent / known-readable); sad
  # paths are enumerated explicitly (Mandate 11), never PBT-generated.
  # @contract-shape:unbounded-preservation — the boundary's promise is a PRESERVED
  # invariant across every registry perturbation (never accepted, never crash), not
  # a single pure return value.

  @slice-05 @walking_skeleton @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A check naming a wave the registry never declared is rejected as unknown
    Given the maintainer checks a feature-delta against a wave the registry never declared
    When the maintainer runs the registry-section boundary check
    Then the registry-section boundary check rejects the check for an unknown wave
    And the boundary check never reports the feature-delta as accepted
    And the boundary check degrades without crashing
    And the boundary check leaves the feature-delta unchanged

  @slice-05 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A check against a known wave whose registry file is garbled degrades to indeterminate
    Given the maintainer checks a feature-delta against a known wave whose registry file is garbled
    When the maintainer runs the registry-section boundary check
    Then the registry-section boundary check refuses to decide and degrades to indeterminate
    And the boundary check never reports the feature-delta as accepted
    And the boundary check degrades without crashing
    And the boundary check leaves the feature-delta unchanged

  @slice-05 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A check against a known wave whose registry file is missing degrades to indeterminate
    Given the maintainer checks a feature-delta against a known wave whose registry file is missing
    When the maintainer runs the registry-section boundary check
    Then the registry-section boundary check refuses to decide and degrades to indeterminate
    And the boundary check never reports the feature-delta as accepted
    And the boundary check degrades without crashing
    And the boundary check leaves the feature-delta unchanged

  @slice-05 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A check against a known wave with a readable registry still accepts a declared delta
    Given the maintainer checks a feature-delta against a known wave with a readable registry
    When the maintainer runs the registry-section boundary check
    Then the registry-section boundary check accepts the feature-delta
    And the boundary check degrades without crashing
    And the boundary check leaves the feature-delta unchanged
