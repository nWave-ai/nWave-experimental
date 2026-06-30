"""Typed domain vocabulary for f-rust-test-runner-adapter slice-02 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists). These types are
TEST-LOCAL -- they never import production code; the ATs drive the SUT (the cargo
run-facet + the runner registry + the ``nwave-lang-rust`` plugin) only through
the composition-root driving port (Mandate-13, Layer 3 subprocess: a child
interpreter imports the SUT and runs it over a REAL controlled filesystem + a
FAKE-cargo executable on a controlled PATH).

slice-02 surface (feature-delta C1/C2/C3 / Acceptance AT-4..7): the cargo
``RunnerAdapter.run`` run-facet (``run_cargo_scope``), the plugin-populated
``RunnerRegistry`` (``GLOBAL_REGISTRY`` + ``seed_runner_registry``), and the
``nwave-lang-rust`` ``LanguageAdapterPlugin``. The observables are the
PASS/FAIL/INDETERMINATE verdict the run-facet maps each cargo exit code to, and
the registry resolution of the ``"cargo-test"`` token AFTER the plugin's
``register_adapters`` has run (the unification).
"""

from __future__ import annotations

from enum import Enum


class RunnerVerdict(Enum):
    """The port-exposed verdict the cargo run-facet maps a cargo exit code to.

    The §C1 exit-semantics contract (each row pinned by an AT). The AT asserts ON
    this verdict (the run-facet's observable outcome), never on the raw exit code
    or an internal field:

    - ``PASS``          -- the declared ``test_command`` exited 0 (all pass).
                           ``RunVerdict(passed=True)``.
    - ``FAIL``          -- the command exited non-zero WITH tests executed (a
                           legit RED). ``RunVerdict(passed=False)`` -- PROPAGATED,
                           never swallowed into INDETERMINATE.
    - ``INDETERMINATE`` -- the command ran zero tests (cargo exit 4 -> empty-scope)
                           OR cargo was unresolvable after the full discovery
                           scale. Carried distinctly from FAIL via the
                           ``RunnerAdapterUnavailable`` degrade-LOUD channel
                           (NEVER a vacuous pass).
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class CargoExitScenario(Enum):
    """Which controlled FAKE-cargo exit behaviour the fixture plants.

    A planted fake-cargo executable emits a controlled exit code + output so the
    §C1 exit-semantics are exercised DETERMINISTICALLY in CI -- no real Rust
    toolchain required (the WSL2 GOTCHA #1 / real-cargo absence is a CI fact). The
    fake-cargo is a real chmod+x script on a controlled PATH that the run-facet
    resolves via the slice-01 ``resolve_tool`` scale and shells like any cargo.

    - ``GREEN``       -- the fake exits 0 (all tests passed)         -> PASS.
    - ``RED``         -- the fake exits 1 AFTER emitting test output
                         (a real failure with tests executed)        -> FAIL.
    - ``NO_MATCH``    -- the fake exits 4 (cargo's "no test matched"
                         / zero tests run)                           -> INDETERMINATE.
    """

    GREEN = "green"
    RED = "red"
    NO_MATCH = "no-match"
