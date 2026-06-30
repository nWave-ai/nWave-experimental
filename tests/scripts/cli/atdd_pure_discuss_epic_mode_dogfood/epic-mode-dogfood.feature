@slice-06 @feature-discuss-epic-mode
Feature: The flow-v2 wave-migrations epic-delta is the first real epic-mode run

  The flow-v2 wave-migrations follow-on list lives today only in conversation and
  in the flow-design change-set master. The maintainer wants that list to become a
  validated, repeatable epic-delta -- the first REAL epic-mode run -- instead of a
  list that exists only while the maintainer is in the loop.

  The deliverable is the REAL artifact at the production path
  `docs/epic/flow-v2-wave-migrations/epic-delta.md`. It is AUTHORED by the Product
  Owner following the epic-mode procedure (the authoring prose, the escalation, the
  maintenance contract -- all exercised against this single real run). The artifact
  is the deliverable; a reference producer cannot stand in for it.

  These scenarios OBSERVE the real repository path, read-only -- they never write
  it. What they pin is the dogfood contract DESIGN declared: the produced artifact
  exists and clears the keystone gate; it designates exactly one keystone feature
  and orders its features backward-only (the keystone / dependency-order checks
  DESIGN deferred to this slice); and its Feature Plan faithfully represents every
  category of the change-set follow-on list.

  # DESIGN slice-06 dogfood completeness contract + the EDC-5/EDC-6 deferral
  # (DC-2) + EDC-8 gate-OUT. The slice's "code" is the produced ARTIFACT + the
  # epic-mode authoring PROSE -- there is NO src/des surface. Driving ports: the
  # REAL produced epic-delta artifact (read-only filesystem/document observation) +
  # slice-01's already-shipped CLI `des.cli.validate_feature_delta.main` for the
  # gate-OUT leg (EDC-8). Layer 3 (subprocess/FS acceptance), example-only -- no PBT
  # (Mandate 9/11): the EDC and the closed 7-item change-set coverage universe are
  # finite, enumerable closed contract sets, so the falsifier-gate forbids PBT.
  #
  # Active-RED (atdd_pure): slice-06 has no net-new src/des seam; active-RED lives
  # at the artifact layer at the REAL production path. The dogfood run has not
  # happened on the current tip, so `docs/epic/flow-v2-wave-migrations/
  # epic-delta.md` does not exist -- every observation fails with a semantic
  # AssertionError (missing functionality, not a test bug). DELIVER makes them GREEN
  # by running the epic-mode authoring procedure to produce the conformant artifact.
  #
  # Faithfulness (the dogfood's honesty): the change-set follow-on list is pinned as
  # a CLOSED 7-item coverage universe (the four wave migrations + declarative
  # gate-composition extraction + the manifest / gate-G track + the self-attest
  # verdict layer). The completeness scenario asserts every item maps to a Feature
  # Plan row OR a documented exclusion -- a closed-set semantic assertion, never a
  # brittle byte-pin of the source prose.

  Background:
    Given the flow-v2 wave-migrations epic is decomposed by the first real epic-mode run

  @slice-06 @walking_skeleton @driving_port @contract-shape:unbounded-preservation
  Scenario: The first real epic-mode run produces a validated flow-v2 epic-delta
    When the flow-v2 epic-delta is validated by the keystone gate
    Then the keystone gate accepts the flow-v2 epic-delta
    And the flow-v2 epic-delta carries the dogfood structural shape

  @slice-06 @driving_port @contract-shape:pure-function
  Scenario: The flow-v2 epic-delta designates one keystone and orders features backward-only
    When the flow-v2 epic-delta is observed for keystone and dependency order
    Then the flow-v2 epic-delta designates exactly one keystone feature
    And the flow-v2 epic-delta orders its features backward-only

  @slice-06 @driving_port @error @contract-shape:bounded-change
  Scenario: The flow-v2 epic-delta represents every change-set follow-on item
    When the flow-v2 epic-delta is observed for change-set follow-on coverage
    Then every change-set follow-on item maps to a feature row or a documented exclusion
