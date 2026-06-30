@slice-04 @feature-discuss-epic-mode
Feature: Phase 1.5 detection escalates an oversized request to epic-mode

  A user who has never heard of epic-mode discovers it exactly at the moment of
  need. When a maintainer's request fires 2+ of the EXISTING Phase 1.5 oversized
  signals, the detection EXPLAINS which signals fired (named, not generic),
  proposes epic-mode -- naming the literal `--epic` flag -- and ASKS confirmation.
  It NEVER auto-switches: the tool proposes, the human decides (D-shape: explicit
  + escalated, never auto). A silent giant plan can no longer happen -- the
  escalation is the only legal path past the detection.

  The escalation is EMITTED by the Product Owner during a discuss session: that
  emission is a prompt-surface act, not mechanically testable. What these
  scenarios pin is the ESC contract (ESC-1..ESC-6) DESIGN declared for the Phase
  1.5 escalation message: the trigger, the named signals, the `--epic` proposal,
  the confirmation ask, the decline path, and the right-sized guardrail.

  # DESIGN slice-02/04/05 text contracts (ESC-1..ESC-6). The slice's "code" is
  # SKILL / COMMAND text -- there is NO src/des surface, and (unlike slice-02) not
  # even a slice-01 gate-OUT leg: Phase 1.5 detection is prose, with no validator /
  # gate / structured detection config on the tip (verified 2026-06-11). Driving
  # port: the escalation outcome (the reference producer is a golden-file analogue
  # of the LLM-mediated emission) + the decline-branch filesystem observation (zero
  # epic artifacts on a real tmp_path). Layer 3 (FS acceptance), example-only -- no
  # PBT (Mandate 9/11): the ESC is a finite, enumerable closed contract over the
  # 5-signal closed list, so the falsifier-gate forbids PBT.
  #
  # NOT a presence-watcher: a prose-grep of SKILL.md for `--epic` passes the instant
  # the literal is typed, testing no behaviour. Here the escalation is a function of
  # the fired-signal SET -- which signals are named depends on which fired (ESC-2),
  # and a right-sized input produces NO escalation (ESC-6). The scenarios
  # discriminate input -> output behaviour with oversized vs right-sized inputs and
  # a decline branch.
  #
  # Active-RED (atdd_pure): slice-04 has no net-new src/des detection seam;
  # active-RED lives at the behaviour layer. The Phase 1.5 escalation contract is
  # undefined today (the escalation message TEMPLATE is the slice-04 deliverable),
  # so the detection produces ESCALATION_ABSENT and every observation fails with a
  # semantic AssertionError -- missing functionality, not a test bug. DELIVER makes
  # them GREEN by authoring the escalation contract (and REMOVING the stale
  # "propose splitting"/"slices" Phase 1.5 wording).

  Background:
    Given a maintainer running discuss on a request

  @slice-04 @walking_skeleton @driving_port @contract-shape:pure-function
  Scenario: An oversized request is escalated with named signals and the --epic proposal
    Given the request fires the oversized signals more than 3 bounded contexts or modules, estimated effort over 2 weeks, and multiple independent user outcomes that could ship separately
    When the maintainer runs the oversized-detection on the request
    Then the detection escalates the request to epic-mode
    And the escalation names each fired signal
    And the escalation proposes epic-mode naming the --epic flag
    And the escalation asks the maintainer to confirm without auto-switching

  @slice-04 @driving_port @error @contract-shape:bounded-change
  Scenario: Declining the escalation continues feature-level discuss with no epic artifacts
    Given the request fires the oversized signals more than 3 bounded contexts or modules, estimated effort over 2 weeks, and multiple independent user outcomes that could ship separately
    And the maintainer will choose continue feature-level
    When the maintainer runs the oversized-detection on the request
    And the maintainer answers the confirmation ask
    Then standard feature-level discuss continues
    And the run created no epic workspaces

  @slice-04 @driving_port @error @contract-shape:pure-function
  Scenario: A right-sized request is never escalated
    Given the request fires the oversized signals estimated effort over 2 weeks
    When the maintainer runs the oversized-detection on the request
    Then the detection raises no escalation
    And the maintainer sees no new prompts
