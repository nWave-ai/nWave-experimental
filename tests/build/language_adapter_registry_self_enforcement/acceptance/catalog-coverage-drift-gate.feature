# slice-02 — the catalog coverage-drift cross-check (language-adapter-registry-self-
# enforcement). The hand-authored catalog (language-adapter-ports.yaml) is cross-checked
# against the DISCOVERED plugins' actual coverage: the catalog's declared
# `supported-languages` set vs the registered plugins' `target_language` set, plus the
# constraint that no discovered covered port falls outside the catalog. Hand-drift ->
# RED. The "remember to maintain the catalog" hazard becomes a mechanical RED.
#
# slice-02 tests the PURE cross-check (C4) over INJECTED frozensets for the recall +
# frozen-precision corpora, and over a LIGHT live discovery for the precision-live corpus
# (the real catalog YAML declared coverage vs the registered plugins' target_language).
# The LIGHT discovery reads only target_language / port_coverage keys — NOT the C2
# capability resolve-and-probe of slice-03.
#
# Recall/precision golden-fixture shape (mirroring slice-01):
#
#   * RECALL (scenario 1) — drives the cross-check against the FROZEN declared-over-
#     discovered snapshot that PERMANENTLY carries a declared-but-undiscovered language.
#     Asserts FLAGGED + the named drifted language. Green forever once the cross-check
#     exists — proves the coverage-drift gate CAN bite.
#   * PRECISION on a frozen matched snapshot (scenario 2) — drives the cross-check against
#     the FROZEN matched-coverage snapshot (declared == discovered, no out-of-catalog
#     port). Asserts CONFORMANT — proves the gate does NOT over-fire (the fail-closed
#     precision bar, the clean golden complement).
#   * PRECISION-LIVE (scenario 3) — drives the cross-check against the real catalog YAML
#     declared coverage vs a LIGHT live target_language discovery. At HEAD the catalog
#     declares python/typescript/go while the only registered plugin's target_language is
#     `_conformance_fixture` — a REAL drift. Asserts FLAGGED. The witness that flips
#     RED->GREEN EXACTLY when A_GREEN implements the C4 cross-check (reverting C4 re-REDs
#     it). NOT an assertion about per-plugin capability conformance (that is slice-01).
#
# Honest tagging: an in-process introspection of the testarch substrate + a light registry
# read — @component (auto-unit under tests/build/), NEVER @wiring_e2e/@subprocess. No
# spawn, no real I/O beyond the in-process catalog read + entry-point discovery.

@feature-language-adapter-registry-self-enforcement @slice-02 @component
Feature: The methodology maintainer sees the hand-authored catalog flagged when its declared coverage drifts from the discovered plugins

  As the methodology maintainer
  I want the hand-authored catalog flagged when its declared language coverage drifts
  from the registered plugins' actual coverage, while both a frozen matched snapshot and
  the registry-conformant case are reported as no-drift
  So that catalog-to-registry coverage drift becomes red-at-gate-time and no one must
  remember to keep the catalog in lock-step with the registered plugins

  Background:
    Given the catalog coverage-drift cross-check

  @slice-02 @coupled @contract-shape:unbounded-preservation @in-memory
  Scenario: A frozen catalog declaring a language the registry does not provide is flagged
    When the maintainer checks the frozen snapshot where the catalog over-declares a language
    Then the cross-check flags a coverage drift in the snapshot
    And the cross-check names the declared language the registry does not provide

  @slice-02 @coupled @contract-shape:unbounded-preservation @in-memory
  Scenario: A frozen catalog whose discovered coverage includes a port outside the catalog is flagged
    When the maintainer checks the frozen snapshot where a discovered port falls outside the catalog
    Then the cross-check flags a coverage drift in the snapshot
    And the cross-check names the discovered port that falls outside the catalog

  @slice-02 @coupled @contract-shape:unbounded-preservation @in-memory
  Scenario: A frozen catalog whose declared coverage matches the discovered coverage is cleared
    When the maintainer checks the frozen snapshot where declared coverage matches discovered coverage
    Then the cross-check reports the catalog coverage as matching the discovered coverage

  @slice-02 @coupled @contract-shape:unbounded-preservation @real-io
  Scenario: The real catalog over-declaring against the registered plugins is flagged
    When the maintainer checks the real catalog against the discovered plugins
    Then the cross-check flags a coverage drift in the real catalog
