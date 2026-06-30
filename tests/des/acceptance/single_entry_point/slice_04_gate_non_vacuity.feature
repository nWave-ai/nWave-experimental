@feature-single-entry-point @slice-04
Feature: slice-04 — the rescoped migration gate still bites (non-vacuity control)

  Earned-Trust probe for the slice-04 AT-07/08 rescope. The rescope makes a
  module-form invocation a violation only when it is concrete (P1), names a
  registered subcommand (P2), and carries no sanction sentinel (P3) — which
  legitimately excludes the no-subcommand modules and the sanctioned-SUT
  callsites. AT-10 is the negative control: it proves the rescoped predicate is
  NOT vacuously green. An unmarked, concrete, registered-subcommand module-form
  invocation in a non-test authoring file MUST still be reported. Without this
  control, a future over-broad exclusion would silently pass and the whole gate
  would rot into a no-op.

  Background:
    Given the nwave runtime is installed

  @slice-04 @contract-shape:pure-function @driving_port @real-io @adapter-integration @negative-control
  Scenario: The rescoped migration scan still flags an unmarked registered-subcommand module-form invocation
    Given a non-test authoring file carries an unmarked module-form invocation of a registered subcommand
    When the rescoped migration scan inspects that authoring file
    Then the rescoped migration scan reports the unmarked registered-subcommand invocation as a violation
