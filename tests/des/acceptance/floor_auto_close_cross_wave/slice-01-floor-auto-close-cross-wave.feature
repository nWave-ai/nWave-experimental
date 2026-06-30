@feature-fix-floor-auto-close-cross-wave
Feature: The wave-active floor auto-closes on the wave owner's terminal return

  A spine driver running a multi-wave flow hits a stale wave-active floor at each
  cross-wave transition: the previous wave's floor was never closed, so the NEXT
  wave's dispatch is falsely blocked as an in-wave bypass, and the driver must
  manually `des wave-clear` (tsunami Q-10, observed 4x+). Option A (ratified Ale
  2026-06-23): chain the floor close off the EXISTING attested SubagentStop
  gate-OUT PASS, firing ONLY when the returning subagent is the ACTIVE wave's
  OWNER (its terminal return), never on any attested return or any in-wave
  sub-dispatch. Invariant-safe: in-wave sub-dispatches are PreToolUse events that
  never reach the gate-OUT, so in-wave persistence is preserved by construction
  (I3/I4 untouched).

  # --- AC-1 cross-wave-close: the NEW behavior (ACTIVE-RED at HEAD) -------------

  @slice-01 @driving_port @contract-shape:bounded-change @AC-1
  Scenario Outline: The wave owner's terminal attested gate-OUT PASS closes the floor
    Given an active wave floor owned by "<owner>"
    When the wave owner returns through the attested gate-OUT
    Then the return is allowed
    And the wave-active floor is cleared

    Examples: wave owners whose terminal return closes their wave floor
      | owner               |
      | nw-product-owner     |
      | nw-acceptance-designer |

  # --- AC-2 in-wave-persist: in-wave sub-dispatch never closes (live-green) -----

  @slice-01 @driving_port @contract-shape:unbounded-preservation @AC-2
  Scenario: An in-wave sub-dispatch leaves the floor armed (persistence preserved)
    Given an active wave floor owned by "nw-acceptance-designer"
    When the in-wave sub-dispatch is evaluated
    Then the wave-active floor stays armed

  # --- AC-3 non-terminal-no-close: a non-owner return does not close (guard) ----

  @slice-01 @driving_port @contract-shape:unbounded-preservation @AC-3
  Scenario Outline: A non-owner attested return leaves the floor armed
    Given an active wave floor for a "<owner>" wave with a non-owner return
    When the non-owner returns through the attested gate-OUT
    Then the wave-active floor stays armed

    Examples: a non-owner reviewer return under each owner's active wave floor
      | owner               |
      | nw-product-owner     |
      | nw-acceptance-designer |

  # --- AC-4 gate-OUT-veto-unchanged: a review veto blocks + no close (guard) ----

  @slice-01 @driving_port @contract-shape:unbounded-preservation @AC-4
  Scenario: A gate-OUT review veto blocks the return and does not clear the floor
    Given an active wave floor owned by "nw-solution-architect"
    When the wave owner returns with a review-verdict veto
    Then the return is blocked
    And the wave-active floor stays armed
