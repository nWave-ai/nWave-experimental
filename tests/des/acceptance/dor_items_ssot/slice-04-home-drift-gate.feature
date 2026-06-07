@feature-dor-items-ssot @dor-items-ssot @slice-04
Feature: A maintainer editing a DoR home is mechanically stopped when it diverges from the authoritative set
  As a maintainer who edits a Definition-of-Ready home
  I want to be mechanically stopped when a home's item-list diverges from the one authoritative set
  So that a future drift between the homes and the canonical set cannot reach a reviewer

  @slice-04 @real-io @driving_port @contract-shape:bounded-change
  Scenario: The drift check stops a maintainer whose home lists a different number of items than the authoritative set
    Given a Definition-of-Ready home that lists eight readiness items while the authoritative set carries nine
    When the maintainer runs the Definition-of-Ready drift check over that home
    Then the drift check refuses the home and names it as diverged from the authoritative set

  @slice-04 @real-io @driving_port @contract-shape:bounded-change
  Scenario: The drift check passes the reconciled homes after examining every canonical home
    When the maintainer runs the Definition-of-Ready drift check over the reconciled homes
    Then the drift check accepts every home as agreeing with the authoritative set
     And the drift check confirms it examined every canonical Definition-of-Ready home

  @slice-04 @real-io @driving_port @contract-shape:bounded-change
  Scenario: The drift check reports its verdict and the diverged homes in a structured shape
    Given a Definition-of-Ready home that lists eight readiness items while the authoritative set carries nine
    When the maintainer runs the Definition-of-Ready drift check over that home
    Then the drift check reports a refusing verdict, the diverged home, and the authoritative item count
