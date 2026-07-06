@feature-unified-language-adapter-registry
Feature: The TypeScript plugin mirrors the Python reference plugin for the TS toolchain

  Priya's Python reference plugin (slice-02) already proved the unified
  registry seam end-to-end for one language. Devon maintains nWave's
  TypeScript support and ships `nwave_lang_typescript`, the SECOND concrete
  `LanguageAdapterPlugin` to wire the 3 new slots -- with ZERO edit to the
  slice-01 seam or to any slice-02 file. This is the seam's language-neutrality
  proof: the SAME `_maybe_route_through_registered_contract_gate` seam, the
  SAME `LanguageAdapterRegistry` slot pair, a DIFFERENT resolved tool-name
  (`"vitest"` instead of `"pytest"`), purely additive (DESIGN component IDs
  C12-C13).

  # DISCUSS Slice Plan (slice-03 / DESIGN slice-07): "A contributor supporting
  # TypeScript sees nwave_lang_typescript mirror slice-02 for the TS
  # toolchain." Prefactoring: NONE needed -- the slice-01 seam is
  # language-neutral by construction (feature-delta `## Prefactoring
  # slice-07`).
  #
  # Driving port (Architecture-of-Reference): the REAL installed contract-gate
  # entry `des.cli.run_contract_gate.main(argv)`, driven as a genuine child
  # interpreter (subprocess-e2e, Mandate-13 Layer-3) -- reserved here because
  # Scenario 1 IS the walking-skeleton scenario proving the installed artifact
  # is wired for a SECOND language. Scenario 2 also drives through a child
  # interpreter (the TS plugin + adapters are net-new production modules
  # absent at HEAD; importing them in THIS test process would be a collection
  # ImportError -- BROKEN, not active-RED -- so every drive happens across a
  # subprocess boundary, mirroring slice-02's `Slice02Composition` and the
  # shipped `vitest_test_runner_adapter` precedent).
  #
  # FAKE-vitest determinism (mirrors the shipped `vitest_test_runner_adapter`
  # slice-01 fixture): a real chmod+x fake `vitest` binary is planted on a
  # controlled PATH so this AT never depends on a real Node/vitest toolchain
  # being installed on the target machine (target-machine agnosticism,
  # CLAUDE.md architectural constraint) -- the fixture's `package.json`
  # declares a genuine `vitest` devDependency so the REAL `resolve_runner`
  # resolves the target's tool-name to `"vitest"`.
  #
  # active-RED mechanism: at HEAD `scripts/install/plugins/nwave_lang_typescript.py`
  # does not exist. Every child program below imports it; the import raises
  # ModuleNotFoundError INSIDE the child (never in this process's
  # collection), so the child exits non-zero with no success marker on its
  # stdout. Each Then turns that captured absence into a named semantic
  # AssertionError. Collection is clean: this feature's step modules import
  # NOTHING from `scripts.install.plugins.nwave_lang_typescript` or
  # `des.adapters.driven.{contract_gate,e2e,robustness}` at module top.
  #
  # Layer 3 subprocess, example-only (Mandate 9/11 -- no PBT at this layer):
  # each scenario pins one closed observable. Sad path (module absent at
  # HEAD) is the active-RED state itself, not a separately-authored scenario.
  #
  # Induction-gap note (see DISTILL report): as in slice-02, the slice's own
  # value statement does not extend to `des doctor --target-language
  # typescript` moving toward `shape: ready` -- `src/des/cli/doctor.py` is
  # explicitly left untouched by this feature (DESIGN, [REF] Open questions)
  # and is out of scope for both slice-02 and slice-03.

  @slice-03 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change @covers-R4
  Scenario: The contract gate routes a TypeScript codebase through its registered vitest adapter once the TypeScript plugin is wired
    Given the maintainer has a TypeScript codebase with a passing vitest suite
    And the TypeScript language plugin has wired its contract-gate adapter into the registry
    When the maintainer runs the contract gate against the codebase
    Then the contract gate reports it ran through the registered TypeScript adapter
    And the contract gate reports the codebase as passing
    And the maintainer's codebase is left unchanged by the contract-gate run

  @slice-03 @in-memory @contract-shape:pure-function @covers-R5
  Scenario: The TypeScript plugin wires all three new adapter slots in one call
    Given a fresh unified language-adapter registry
    When the TypeScript plugin wires its adapters into the registry
    Then the registry resolves a contract-gate adapter for the plugin's runner
    And the registry resolves an environmental-e2e adapter for the plugin's runner
    And the registry resolves a robustness-density adapter for the plugin's runner
