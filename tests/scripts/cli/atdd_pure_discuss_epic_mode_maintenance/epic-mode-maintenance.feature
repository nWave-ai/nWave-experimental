@slice-05 @feature-discuss-epic-mode
Feature: The epic-delta tracks live feature progress through status flips and linkage

  A maintainer opening the epic-delta sees live progress. When a feature is picked
  up, its Feature Plan row flips `pending` -> `in-flight` AND gains its
  `docs/feature/{id}/` link -- one atomic edit. When the feature is finalized at
  feature-end, the row flips `in-flight` -> `shipped`. Status moves forward only.
  The maintainer decides the next pickup from the plan, not from memory.

  A status flip must NOT break the epic-delta's structural validity: the flipped
  document still clears the slice-01 keystone gate (`accepted`). Fractal JIT holds
  -- only the picked-up feature gets a `docs/feature/{id}/` workspace; a row still
  `pending` has none. An illegal status token (outside the `pending | in-flight |
  shipped` set) is rejected at the maintenance-procedure level -- the keystone gate
  does NOT validate Status cells, so the procedure owns that rejection.

  # DESIGN slice-02/04/05 text contracts (LSC-1..LSC-6). The slice's "code" is
  # SKILL / COMMAND text -- there is NO src/des surface. Driving ports: the flip
  # outcome (the reference producer is a golden-file analogue of the maintainer's
  # flip) + slice-01's already-shipped CLI `des.cli.validate_feature_delta.main`
  # for the keystone-gate-preservation leg + the filesystem feature-workspace tree
  # (LSC-3). Layer 3 (subprocess/FS acceptance), example-only -- no PBT (Mandate
  # 9/11): the LSC is a finite, enumerable closed contract over the 3-token status
  # set, so the falsifier-gate forbids PBT.
  #
  # Validator-today finding (verified 2026-06-11): the slice-01 validator does NOT
  # validate Status cells (DC-1) -- an in-flight/shipped mix validates `accepted`,
  # so the flip provably preserves validity (the gate-preservation leg is a real
  # mechanical witness); and an illegal token like `done` ALSO validates `accepted`,
  # so LSC-6's rejection lives at the procedure level, not the gate.
  #
  # NOT a presence-watcher: a prose-grep of SKILL.md for `in-flight` passes the
  # instant the literal is typed, testing no behaviour. Here the flip is a function
  # of the (current-status, action) pair -- a pick-up of a pending row yields an
  # in-flight row WITH its link (LSC-1), a finalize of an in-flight row yields a
  # shipped row (LSC-2), a backward flip is rejected (LSC-5). The scenarios
  # discriminate input -> output behaviour across the forward path, the
  # gate-preservation leg, the JIT invariant, and the rejection leg.
  #
  # Active-RED (atdd_pure): slice-05 has no net-new src/des maintenance seam;
  # active-RED lives at the behaviour layer. The linkage/status-flip procedure is
  # undefined today (the procedure is the slice-05 deliverable), so no flip is
  # applied and every observation fails with a semantic AssertionError -- missing
  # functionality, not a test bug. DELIVER makes them GREEN by authoring the
  # maintenance procedure (linkage + status flips + JIT rule + backlog-cites-epic).

  Background:
    Given an authored epic-delta whose feature rows are all pending

  @slice-05 @walking_skeleton @driving_port @contract-shape:bounded-change
  Scenario: Picking up a feature flips its row to in-flight, links its workspace, and preserves validity
    Given the maintainer picks up the feature design-wave-migration
    When the maintainer runs the maintenance on the epic-delta
    Then the picked-up row reads in-flight
    And the picked-up row carries its docs/feature link
    And the flipped epic-delta still clears the keystone gate

  @slice-05 @driving_port @contract-shape:bounded-change
  Scenario: Finalizing a feature flips its in-flight row to shipped and preserves validity
    Given the feature design-wave-migration is in-flight
    And the maintainer finalizes the feature design-wave-migration
    When the maintainer runs the maintenance on the epic-delta
    Then the finalized row reads shipped
    And the flipped epic-delta still clears the keystone gate

  @slice-05 @driving_port @error @contract-shape:bounded-change
  Scenario: Maintenance honours fractal JIT and rejects an illegal status token at the procedure level
    Given the maintainer picks up the feature design-wave-migration
    And the maintainer proposes the illegal status token done
    When the maintainer runs the maintenance on the epic-delta
    Then no pending feature has a workspace
    And the illegal status token is rejected by the maintenance procedure
