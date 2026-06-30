@slice-02 @feature-discuss-epic-mode
Feature: The --epic authoring produces a validated epic-delta

  When a maintainer's request is bigger than one feature, they run
  `/nw-discuss --epic <id>` and the tool guides them to a validated epic-delta
  -- the `docs/epic/{id}/epic-delta.md` document carrying an epic-JTBD section, a
  five-column Feature Plan mirroring the carpaccio Slice Plan, exactly one
  keystone feature, and a backward-only dependency order -- instead of cutting
  features by hand in conversation.

  The epic-delta is AUTHORED by the Product Owner during a discuss session: that
  authoring is a prompt-surface act, not mechanically testable. What these
  scenarios pin is the EDC contract DESIGN declared for the PRODUCED artifact:
  the structural shape the run must produce, that the produced epic-delta clears
  the keystone gate (slice-01's real validator), and that the run honours
  fractal JIT -- producing only the plan, never feature workspaces upfront.

  # DESIGN slice-02/04/05 text contracts (EDC-1..EDC-9). The slice's "code" is
  # SKILL / COMMAND text -- there is NO src/des surface. Driving ports: the
  # produced epic-delta artifact (filesystem/document observation, the
  # DESIGN-named port for slice-02 ATs) + slice-01's already-shipped CLI
  # `des.cli.validate_feature_delta.main` for the gate-OUT leg (EDC-8). Layer 3
  # (subprocess/FS acceptance), example-only -- no PBT (Mandate 9/11): the EDC is
  # a finite, enumerable closed contract set, so the falsifier-gate forbids PBT.
  #
  # Active-RED (atdd_pure): slice-02 has no net-new src/des validator seam;
  # active-RED lives at the artifact layer. The EDC-conformant epic-delta the
  # --epic procedure must produce does not exist at its production path on the
  # current tip (the authoring procedure is the slice-02 deliverable), so every
  # observation fails with a semantic AssertionError -- missing functionality,
  # not a test bug. DELIVER makes them GREEN by authoring the procedure and
  # producing a conformant epic-delta.
  #
  # Discoverability ("skill Tier-1 surfaces --epic") stays prompt-surface
  # deliberately: a prose-grep AT is the presence-watcher anti-pattern + Fixture
  # Theater. Discoverability is reviewed in the landed skill text by Sentinel and
  # lives mechanically in the slice-04 escalation contract (ESC-3), not here.

  Background:
    Given a maintainer with a request bigger than one feature

  @slice-02 @walking_skeleton @driving_port @contract-shape:unbounded-preservation
  Scenario: The --epic run produces a structurally well-formed epic-delta
    Given the maintainer runs the epic-mode authoring on the epic
    When the produced epic-delta is observed against the EDC structural shape
    Then the produced epic-delta carries the EDC structural shape
    And the --epic run created no feature workspaces

  @slice-02 @driving_port @contract-shape:pure-function
  Scenario: The produced epic-delta clears the keystone gate
    Given the maintainer runs the epic-mode authoring on the epic
    When the produced epic-delta is validated by the keystone gate
    Then the keystone gate accepts the produced epic-delta

  @slice-02 @driving_port @error @contract-shape:bounded-change
  Scenario: The --epic run honours fractal JIT and produces only the plan
    Given the maintainer runs the epic-mode authoring on the epic
    When the produced epic-mode workspace is observed for fractal JIT
    Then the --epic run created no feature workspaces
    And the only artifact produced is the epic-delta
