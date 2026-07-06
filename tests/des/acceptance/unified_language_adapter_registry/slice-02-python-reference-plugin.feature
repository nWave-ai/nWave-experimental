@feature-unified-language-adapter-registry
Feature: The Python reference plugin wires real adapters through the unified registry seam

  Priya maintains nWave's Python support. Slice-01 already installed the
  unified registry's 3 new slots and 3 sprout-and-fall-through seams in the
  gate CLIs, but every one of them is provably unreachable: no plugin
  registers a contract-gate, environmental-e2e, or robustness-density adapter
  yet, so every gate still runs its old hardcoded Python logic. Priya ships
  `nwave_lang_python`, the Python reference plugin, so that ONE
  `register_adapters` call wires real adapters into all three slots and the
  contract gate starts routing through them instead of falling through.

  # DISCUSS Slice Plan (slice-02 / DESIGN slice-05a): "A contributor
  # supporting Python sees nwave_lang_python register 3 real contract-port
  # adapters THROUGH the slice-01 seam." DESIGN component IDs C8-C11.
  #
  # Driving port (Architecture-of-Reference): the REAL installed contract-gate
  # entry `des.cli.run_contract_gate.main(argv)`, driven as a genuine child
  # interpreter (subprocess-e2e, Mandate-13 Layer-3) — reserved here because
  # this IS the walking-skeleton scenario proving the installed artifact is
  # wired (Scenario 1). Scenario 2/3 also drive through a child interpreter
  # (the plugin + registry are net-new production modules absent at HEAD;
  # importing them in THIS test process would be a collection ImportError —
  # BROKEN, not active-RED — so every drive happens across a subprocess
  # boundary, mirroring the shipped `rust_test_runner_adapter` precedent).
  #
  # active-RED mechanism: at HEAD `scripts/install/plugins/nwave_lang_python.py`
  # does not exist. Every child program below imports it; the import raises
  # ModuleNotFoundError INSIDE the child (never in this process's collection),
  # so the child exits non-zero with no success marker on its stdout. Each
  # Then turns that captured absence into a named semantic AssertionError.
  # Collection is clean: this feature's step modules import NOTHING from
  # `scripts.install.plugins.nwave_lang_python` or `des.adapters.driven.{
  # contract_gate,e2e,robustness}` at module top.
  #
  # Layer 3 subprocess, example-only (Mandate 9/11 — no PBT at this layer):
  # each scenario pins one closed observable. Sad path (module absent at HEAD)
  # is the active-RED state itself, not a separately-authored scenario.
  #
  # DISTILL-pinned open question (feature-delta `[REF] Open questions`,
  # slice-05a): `ContractGatePort.run_suite(repo) -> ContractVerdict` mirrors
  # `RunVerdict` (`test_runner_port.py`) exactly — `passed: bool`, `runner:
  # str`. The seam (`_maybe_route_through_registered_contract_gate`), on a
  # successful routed call, MUST emit the SAME `ContractGateResult` JSON event
  # shape the fallback path already emits (`passed`, `pytest_exit_code`,
  # `gate_scope_digest`), PLUS one new boolean field
  # `routed_via_registered_adapter: true` — additive, back-compatible with
  # every existing consumer of that event (DISCUSS row 4: no breaking change).
  # This is the observable Scenario 1/2 assert on.
  #
  # Induction-gap note (see DISTILL report): the slice's own value statement
  # ("...so `des doctor --target-language python` starts moving toward
  # `shape: ready`") is NOT asserted here. `src/des/cli/doctor.py` hardcodes
  # `shape: "gaps"` / `covered_ports: []` regardless of plugin registration
  # (verified by reading the file) and DESIGN explicitly leaves it untouched
  # this feature — that flip belongs to a DIFFERENT feature's future slice.

  @slice-02 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change @covers-R1
  Scenario: The contract gate routes a Python codebase through its registered adapter once the Python plugin is wired
    Given the maintainer has a Python codebase with a passing test suite
    And the Python language plugin has wired its contract-gate adapter into the registry
    When the maintainer runs the contract gate against the codebase
    Then the contract gate reports it ran through the registered Python adapter
    And the contract gate reports the codebase as passing
    And the maintainer's codebase is left unchanged by the contract-gate run

  @slice-02 @real-io @contract-shape:bounded-change @covers-R2
  Scenario: The registered Python adapter preserves the pre-existing pass or fail verdict
    Given the maintainer has a Python codebase with a failing test suite
    When the contract gate runs against the codebase with the Python adapter registered
    And the contract gate runs again against the same codebase with no adapter registered
    Then both runs report the identical pytest verdict
    And only the adapter-registered run reports routing through the registered adapter

  @slice-02 @in-memory @contract-shape:pure-function @covers-R3
  Scenario: The Python plugin wires all three new adapter slots in one call
    Given a fresh unified language-adapter registry
    When the Python plugin wires its adapters into the registry
    Then the registry resolves a contract-gate adapter for the plugin's runner
    And the registry resolves an environmental-e2e adapter for the plugin's runner
    And the registry resolves a robustness-density adapter for the plugin's runner
