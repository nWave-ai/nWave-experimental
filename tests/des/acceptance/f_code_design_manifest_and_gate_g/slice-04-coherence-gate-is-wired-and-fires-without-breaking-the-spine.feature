@feature-f-code-design-manifest-and-gate-g @slice-04 @driving_port
Feature: The coherence gate is wired as a real catalogued hook-fired gate without breaking the spine
  The coherence gate is built and returns a correct general verdict (slices 01-03), but it is
  authored-but-unwired: no operator subcommand, no catalogued firing surface. So a maintainer of
  the gate catalog cannot see it firing and the catalog-to-hook-wiring coherence check cannot pass
  for it. This slice WIRES it: a real des subcommand the dispatcher recognizes, a catalog mirror
  entry kept one-to-one with the registry, and a LIVE entry in the DISTILL gate-out stack the spine
  actually resolves - so the gate that defends every other gate is itself no longer authored-but-
  unwired, closing the unwired class for it.

  Because wiring the coherence gate onto the DISTILL gate-out means it fires on EVERY DISTILL
  return, the wiring must not break the dogfood spine: a feature that ships NEITHER a design
  manifest NOR a prose design contract has nothing for the gate to diff, so the gate degrades to a
  not-applicable verdict that never vetoes the return. A not-applicable verdict is no objection,
  never an authorizing go.

  Contract-shape is bounded-change: the wiring is a bounded mutation of the shipped registry +
  catalog + gate-out-stack surfaces (a renamed, catalogued, live-resolved subcommand), observed
  through the real dispatcher, the real catalog artifact, and the real spine resolver
  (@contract-shape:bounded-change). The scenarios drive the REAL wired seams - the production des
  dispatcher (subprocess), the shipped catalog data, and the spine gate-stack resolver - not a
  test-fabricated stand-in (@driving_port).

  Witnesses: CT-8 (the coherence gate is invocable as a real subcommand the dispatcher recognizes
  and mirrored one-to-one in the catalog) + CT-9 / AT-A1 (the gate is LIVE-resolved in the DISTILL
  gate-out stack the spine reads from the canonical registry, and a neither-contract feature
  degrades to not-applicable so the spine is never broken). Together they make the coherence gate a
  real, catalogued, hook-fired gate that fires on every DISTILL return without blocking a return
  that ships no design contract.

  @slice-04 @real-io @contract-shape:bounded-change @row:coherence-gate-is-a-recognized-catalogued-subcommand
  Scenario: The coherence gate is invocable as a real subcommand and mirrored in the gate catalog
    Given the coherence gate is wired into the operator subcommand registry surface
    When the wiring surface is inspected
    Then the operator dispatcher recognizes the coherence gate subcommand
    And the coherence gate appears in the gate catalog surface

  @slice-04 @real-io @contract-shape:bounded-change @row:coherence-gate-fires-live-on-the-distill-return
  Scenario: The coherence gate is live-resolved in the DISTILL gate-out stack the spine reads
    Given the coherence gate is wired into the live DISTILL gate-out stack surface
    When the wiring surface is inspected
    Then the coherence gate is live-resolved in the DISTILL gate-out stack

  @slice-04 @real-io @contract-shape:bounded-change @row:coherence-gate-degrades-to-not-applicable-without-a-design-contract
  Scenario: The wired coherence gate degrades to not-applicable for a return shipping no design contract
    Given a feature whose DISTILL return ships no design contract
    When the wired coherence gate fires on the feature that ships no design contract
    Then the coherence gate returns a not-applicable verdict that does not block the return
