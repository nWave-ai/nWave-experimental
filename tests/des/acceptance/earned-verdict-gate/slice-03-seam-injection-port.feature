@feature-oss-earned-verdict-gate
Feature: The seam-injection port breaks a named dependency or abstains
  As the earned-verdict gate that proves a green is honest by breaking what the
    test depends on
  I want a per-language injection port that, given a seam name, swaps the named
    dependency in a generated test scaffold for a fault implementation -- and
    refuses (fail-safe) when the seam name cannot be resolved
  So that the perturbation that a verdict rests on actually took effect, and a
    seam that cannot be named never silently leaves the real dependency in place
    while reporting a perturbation that never happened

  # carpaccio slice-03 (DISCUSS [REF] Slice Plan). The perturbation arm of the
  # gate: slice-01 rules a verdict over a baseline + perturbed run; slice-02
  # produces those runs; THIS slice actually PERTURBS the dependency the
  # perturbed run rests on. Exactly THREE ATs (carpaccio_slice_max=3): AT-1 a
  # nameable seam -> the named dependency is swapped for the fault impl (the swap
  # took effect); AT-2 the perturbation is observable as a CHANGE (the real impl
  # is no longer resolved at the seam -- proving the swap is real, not a no-op
  # that still reports success); AT-3 a seam that cannot be named -> fail-safe
  # ABSTAIN reason=no-nameable-seam, never a silent no-op.
  #
  # Driving port (Mandate-13): the seam-injection CLI invoked as a
  # `python -m des.cli.inject_seam` subprocess (Layer 3 subprocess + JSON
  # assertion). The port reads `NWAVE_PERTURB=<seam-id>` and acts on a generated
  # AT scaffold staged on a tmp path; it reports which implementation the seam
  # resolves to AFTER injection. ZERO direct domain import; example-only, no PBT
  # machinery (Mandate 9/11). The post-injection seam resolution + the
  # abstain signal are the port-exposed universe (Mandate 8).
  #
  # SWAP MECHANISM (DESIGN GAP -- FLAGGED, see feature-delta + report): the
  # feature-delta specifies the BEHAVIOUR ("swaps the named dependency at the
  # seam") but NOT the mechanism (monkeypatch / factory-lookup-by-name /
  # DI-registry override / conftest fixture override). These ATs assert the
  # mechanism-INDEPENDENT observable contract: given seam S and NWAVE_PERTURB=S,
  # after the port acts the dependency resolved at S is the fault impl, not the
  # real impl; given an unresolvable seam name, the port abstains. DELIVER picks
  # the concrete swap mechanism once DESIGN confirms it -- no production scaffold
  # presupposing a mechanism is created here.
  #
  # NWAVE_PERTURB CONTRACT: the seam id is passed via the `NWAVE_PERTURB`
  # environment variable (feature-delta line 40). The composition sets it on the
  # subprocess env; the port reads it. An unset/empty NWAVE_PERTURB is out of
  # scope for this slice (the gate always names a seam before invoking the port).

  # AT-1 -- a nameable seam is perturbed: the swap takes effect.
  @driving_port @real-io @slice-03 @contract-shape:bounded-change
  Scenario: A nameable seam has its dependency swapped for the fault implementation
    Given a generated scaffold exposing a nameable seam
    When the seam-injection port perturbs that seam
    Then the perturbation outcome is "perturbed"
    And the seam now resolves to the fault implementation

  # AT-2 -- the perturbation is observable as a real CHANGE: the real impl is no
  # longer resolved at the seam. This is the proof the swap is not a no-op that
  # merely reports success -- the dependency the scaffold rests on is genuinely
  # broken after injection.
  @driving_port @real-io @slice-03 @contract-shape:bounded-change
  Scenario: A perturbed seam no longer resolves to the real dependency
    Given a generated scaffold exposing a nameable seam
    And the seam initially resolves to the real implementation
    When the seam-injection port perturbs that seam
    Then the seam no longer resolves to the real implementation

  # AT-3 -- fail-safe ABSTAIN (reason no-nameable-seam): the seam name cannot be
  # resolved in the scaffold. The port MUST NOT report a perturbation that never
  # happened; it abstains so the gate never trusts a perturbation that left the
  # real dependency in place.
  @driving_port @real-io @slice-03 @error @contract-shape:bounded-change
  Scenario: A seam that cannot be named yields a fail-safe abstain
    Given a generated scaffold with no seam matching the requested name
    When the seam-injection port perturbs that seam
    Then the perturbation outcome is "abstain"
    And the injection abstain reason is "no-nameable-seam"
    And the real dependency is left untouched
