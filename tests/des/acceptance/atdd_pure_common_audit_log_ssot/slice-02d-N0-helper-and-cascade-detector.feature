@feature-fix-atdd-pure-common-audit-log-ssot
Feature: The shared seeding helper gains a forward feature_id kwarg without breaking unmigrated callers
  As an nWave framework operator preparing the 11-caller migration cascade
  I want the `seed_required_feature_end_records` helper to accept an optional `feature_id=` kw-only parameter
  And I want a cascade-detector arch test that mechanically catches any unmigrated `AtCompletionLedger(...)` caller
  So that the per-caller carpaccio sub-slices (slice-02c-N1..N11) can ship one-by-one
    without M34-class fixture-helper coupling regressions,
    and the F-RECURSIVE-MIGRATION-CASCADE-REGRESSION recurrence vector closes mechanically
    rather than via memory rules.

  # carpaccio sub-slice slice-02d-N0: ships FIRST in the slice-02d coordinated
  # fixture migration. Two deliverables:
  #
  # 1. The shared helper `tests/des/_helpers/feature_end_seeding.py` gains a
  #    new `feature_id: str | None = None` kw-only parameter. When `None`
  #    (default), the 6 writer wrappers invoke the ledger writers in their
  #    legacy ledger-bound-feature_id shape (backward-compat for the 5 existing
  #    fixture caller sites that do NOT pass feature_id). When a non-None
  #    string is passed, every writer wrapper forwards it to
  #    `ledger.append_*(feature_id=...)` under the singleton-shape construction
  #    (forward-pin for the post-migration fixture sites).
  #
  # 2. A new arch test at `tests/des/unit/test_caller_migration_cascade_detector.py`
  #    asserts STRUCTURAL invariants (regex grep over `src/des/**/*.py` +
  #    `scripts/**/*.py`): every `AtCompletionLedger(...)` instantiation
  #    pairs with explicit `feature_id=` forwarding on subsequent `.append_*`
  #    / `.read_records` / `.verified_slices` / `.feature_end_events` /
  #    `.environmental_e2e_events` / `.walking_skeleton_events` /
  #    `.coverage_map_touchpoint_events` calls. The arch test is parametrized
  #    over the live caller list (grep-derived, NOT enumerated) so newly
  #    introduced callers join the gate automatically. Pre-slice-02d-N1..N11:
  #    each unmigrated caller row XFAIL strict=False (allows in-flight
  #    progress); post-N11: parametrize is collapsed and the gate hard-fails
  #    on any future legacy-shape regression.
  #
  # Mandate-13 compliance (HARD): the arch test asserts STRUCTURAL invariants
  # (grep over filesystem) — NOT behavior. It does NOT import production
  # modules and does NOT invoke production functions. Per
  # `feedback_no_direct_domain_testing_in_ats_2026_05_25`, arch tests at
  # `tests/des/unit/test_*_cascade_detector.py` ROOT path are ALLOWED because
  # they are layer-1 structural-invariant assertions, not behavioral tests of
  # a domain or CLI module. Precedent:
  # `tests/des/unit/test_required_record_writer_registry.py`.
  #
  # Layer 3 (subprocess / FS acceptance against real production code):
  # AT-N0a and AT-N0b drive the helper via subprocess stubs (Mandate-13
  # boundary preserved via M32-amendment pattern: the adapter import lives
  # only in the spawned subprocess script string, not in composition.py).
  # Example-only per Mandate 9/11 — no PBT at layer 3.
  #
  # Driving ports exercised by this sub-slice:
  # - the production `seed_required_feature_end_records` helper invoked via
  #   subprocess stub from a tmp_path-scoped fresh project repository.
  # - the production substrate observations: existence of per-feature ledger
  #   files (legacy path) vs the common audit log file (singleton path), and
  #   the explicit `feature_id` field on records emitted by the helper.

  # AT-N0a: regression-pin (backward-compat preservation). The 5 existing
  # fixture caller sites today call the helper WITHOUT passing feature_id.
  # After slice-02d-N0 ships the new `feature_id=None` default kwarg, those
  # 5 sites must continue to produce BYTE-IDENTICAL writes: 6 records
  # emitted under the LEGACY per-feature ledger substrate, each record
  # carrying the ledger-bound feature_id field "fix-example" sourced from
  # the legacy positional-shape constructor's feature_id parameter. No
  # records under the common audit log path. This pins the dual-shape
  # contract: a future refactor that drops the legacy default branch reds
  # this AT immediately.
  #
  # AT-N0a / AT-N0b shape distinction (port-exposed observables):
  #
  #   - File location is the primary discriminator: AT-N0a observes the
  #     per-feature ledger path; AT-N0b observes the common audit log path.
  #     (Mandate 8 universe: filesystem substrate presence.)
  #
  #   - feature_id field presence is observed POSITIVELY in both ATs (each
  #     record carries the field). Production's `_append_record`
  #     unconditionally serializes feature_id into every record; the legacy
  #     positional-shape ledger resolves feature_id from `self._feature_id`
  #     (construction-time), while the singleton-shape ledger resolves it
  #     from the per-call kwarg forwarded by the helper. Both shapes WRITE
  #     the field, so the field-presence assertion is symmetric. The
  #     PROVENANCE of feature_id (constructor vs kwarg) is non-port-
  #     observable, but the legacy default branch in the helper is the
  #     code path that triggers the constructor-sourced resolution. A
  #     refactor that drops the legacy default branch would either fail
  #     to construct a legacy ledger or surface a None feature_id (
  #     because the singleton-shape `_resolve_feature_id` raises TypeError
  #     when feature_id is None), so the positive assertion remains a
  #     refactoring-hostile signal.
  #
  # M47 amendment (2026-05-25, post M45 escalation AT_INSUFFICIENT_FOR_GREEN):
  # the original Then-clause "no seeded record carries an explicit
  # feature_id field" contradicted production reality (every record from
  # `_append_record` carries feature_id regardless of shape) and the AT's
  # own "BYTE-IDENTICAL writes" framing (legacy fixture sites have always
  # written records WITH feature_id). Replaced with the positive
  # symmetric assertion above; the file-location pair (AT-N0a per-feature
  # vs AT-N0b common log) remains the discriminative observable.
  @slice-02d-N0 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The fixture helper without a feature_id kwarg preserves legacy ledger-bound writes
    Given a fresh project repository with no atdd_pure audit log yet
    When the fixture helper seeds required feature-end records on a legacy-shape ledger for feature "fix-example"
    Then the per-feature ledger file for feature "fix-example" exists under the project repository
    And the common audit log file is not created
    And exactly 6 records are seeded under the per-feature ledger
    And every seeded record carries the ledger-bound feature_id field "fix-example"

  # AT-N0b: forward-pin (singleton-shape forwarding). When a fixture site
  # passes `feature_id="fix-example"` kw-only to the helper, every one of
  # the 6 `_RECORD_WRITERS` entries must forward the value to its
  # `ledger.append_*(feature_id=...)` writer call under the singleton-shape
  # constructor. The observable contract: 6 records appear under the
  # common audit log path, each carrying an explicit `feature_id` field
  # equal to "fix-example". No records under the per-feature ledger path.
  # This pins the forward path the slice-02c-N1..N11 callers will exploit
  # once their production drivers migrate to singleton-shape.
  @slice-02d-N0 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The fixture helper forwards an explicit feature_id to every singleton-shape writer
    Given a fresh project repository with no atdd_pure audit log yet
    When the fixture helper seeds required feature-end records on a singleton-shape ledger for feature "fix-example" with feature_id forwarded
    Then the common audit log file exists under the project repository
    And the per-feature ledger file for feature "fix-example" was not created
    And exactly 6 records are seeded under the common audit log
    And every seeded record carries an explicit feature_id field "fix-example"
