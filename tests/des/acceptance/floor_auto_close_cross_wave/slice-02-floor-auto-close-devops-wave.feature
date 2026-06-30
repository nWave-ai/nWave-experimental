@feature-fix-floor-auto-close-cross-wave
Feature: The dual-owning platform-architect's floor auto-closes from DEVOPS too

  The platform-architect OWNS BOTH design AND devops (the dual-ownership the
  shipped wave_dispatch_guard_policy._PLATFORM_ARCHITECT_WAVES =
  frozenset({"design","devops"}) already encodes for the dispatch guard). The
  cross-wave floor auto-close (slice-01) gates the close on the SINGLE-valued
  WAVE_OWNERS.get(subagent_type) == active_wave, and WAVE_OWNERS maps
  nw-platform-architect -> "design" only. So when the platform-architect returns
  terminally from the DEVOPS wave, WAVE_OWNERS.get(...) == "design" != "devops"
  and the devops floor does NOT close -- the next wave's dispatch is falsely
  blocked as a stale-floor in-wave bypass, and the driver must manually
  `des wave-clear`. slice-02 (M6 dual-aware completion) closes that gap by wiring
  the dual-aware predicate into the close, so the dual-owner closes EITHER of its
  waves, the design close stays preserved (a superset, never narrowed), and no
  other agent over-closes a devops floor.

  # --- AC-5 devops-close: the NEW behavior (ACTIVE-RED at HEAD) ----------------

  @slice-02 @driving_port @contract-shape:bounded-change @AC-5
  Scenario: The platform-architect's terminal DEVOPS gate-OUT PASS closes the devops floor
    Given an active devops wave floor with the platform-architect as the dual owner
    When the dual-owning platform-architect returns terminally from its wave
    Then the dual-owner return is allowed
    And the dual-owned wave floor is cleared

  # --- AC-6 design-close-preserved: the slice-01 superset (live-green) ----------

  @slice-02 @driving_port @contract-shape:unbounded-preservation @AC-6
  Scenario: The platform-architect still closes its design floor (slice-01 preserved)
    Given an active design wave floor with the platform-architect as the dual owner
    When the dual-owning platform-architect returns terminally from its wave
    Then the dual-owner return is allowed
    And the dual-owned wave floor is cleared

  # --- AC-7 non-owner-devops-no-close: no over-close (live-green) ---------------

  @slice-02 @driving_port @contract-shape:unbounded-preservation @AC-7
  Scenario: A non-dual-owner return leaves the devops floor armed (no over-close)
    Given an active devops wave floor with a non-dual-owner return
    When the non-dual-owner returns terminally from the devops wave
    Then the dual-owned wave floor stays armed
