"""Typed domain vocabulary for f-rust-test-runner-adapter slice-03 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists). These types are
TEST-LOCAL -- they never import production code; the ATs drive the SUT only
through the composition-root driving port (Mandate-13, Layer 3 subprocess: the
operator-facing ``python -m des.cli.run_contract_gate --feature-id`` entry, the
SAME subprocess ``verify_slice_commit_completeness._run_contract_gate`` composes,
run over a REAL controlled filesystem + a FAKE-cargo executable on a controlled
PATH).

slice-03 surface (feature-delta §V.A / Acceptance AT-8..10): the E2-routing
short-circuit in ``run_contract_gate._mode_feature_scoped`` -- on a Rust target
it must (1) seed the registry + RESOLVE the runner FIRST (before the pytest-bound
collection), (2) DERIVE ``binary(/<snake_feature_id>/)`` from the feature-id by
CONVENTION (kebab -> snake), (3) read an OPTIONAL ``runner.json`` override, and
(4) run the cargo run-facet feature-scoped, mapping its verdict -- NEVER reaching
the pytest worker, NEVER a whole-crate run.

The observable is the JSON verdict the contract gate EMITS on stdout: a green
cargo run CLEARS the feature scope (``FeatureScopeCleared``); a Rust target must
NEVER produce the pytest-collection failure (``FeatureScopeMalformed`` /
``zero-collected``) that HEAD emits because the pytest worker collects zero tests
on a crate.
"""

from __future__ import annotations

from enum import Enum


class GateOutcome(Enum):
    """The port-exposed verdict the E2 contract gate emits for a Rust target.

    The AT asserts ON this observable (the gate's emitted JSON ``event``), never
    on an internal field or call-graph. The contract-relevant distinction is
    CLEARED (the cargo path ran and the feature scope cleared) vs the HEAD bug
    (PYTEST_ZERO_COLLECTED -- the pytest worker collected zero tests on a crate
    and the gate degraded to a vacuous-scope malformed verdict, which slice-03
    must make impossible on a Rust target):

    - ``CLEARED``               -- ``event == "FeatureScopeCleared"``: the cargo
                                   run-facet ran feature-scoped and PASSED; the
                                   slice is verifiable through the FULL spine.
    - ``PYTEST_ZERO_COLLECTED`` -- ``event == "FeatureScopeMalformed"`` with
                                   ``reason == "zero-collected"``: the pytest
                                   worker collected zero tests (the HEAD bug on a
                                   Rust target). slice-03 must NEVER produce this
                                   on a Cargo.toml target -- the runner resolves
                                   to cargo and short-circuits BEFORE the pytest
                                   collection.
    - ``RUNNER_INDETERMINATE``  -- a loud INDETERMINATE runner-resolution verdict
                                   (e.g. cargo unresolvable) -- NOT a pytest
                                   collection failure, NOT a silent pass.
    """

    CLEARED = "cleared"
    PYTEST_ZERO_COLLECTED = "pytest-zero-collected"
    RUNNER_INDETERMINATE = "runner-indeterminate"


class RunnerJsonPresence(Enum):
    """Whether the Rust target ships the OPTIONAL ``runner.json`` override.

    D7 v3 ⑥ / §V.B: ``runner.json`` is an OPTIONAL override only. Its ABSENCE is
    the NORMAL zero-config case (the convention-derived ``binary()`` selector
    applies); it is NEVER an INDETERMINATE and NEVER a whole-crate fall-back.

    - ``ABSENT``   -- no ``runner.json``; the gate DERIVES
                      ``binary(/<snake_feature_id>/)`` from the feature-id by
                      convention. The zero-config common case (AT-8, AT-9-absent).
    - ``OVERRIDE`` -- a ``runner.json`` ships a ``test_command`` that OVERRIDES
                      the derived selector (a convention-breaking target opting
                      in). The gate runs the OVERRIDE command (AT-9-override).
    """

    ABSENT = "absent"
    OVERRIDE = "override"
