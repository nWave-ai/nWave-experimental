"""Typed domain vocabulary for vitest-test-runner-adapter slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists). These types are
TEST-LOCAL -- they never import production code; the ATs drive the SUT (the JS/TS
run-facet ``run_vitest_scope``) only through the composition-root driving port
(Mandate-13, Layer 3 subprocess: a child interpreter imports the SUT and runs it
over a REAL controlled filesystem + a FAKE-``vitest`` executable on a controlled
PATH).

slice-01 surface (feature-delta AC-1..4): the JS/TS ``run_vitest_scope`` run-facet
(mirror of ``run_go_scope`` / ``run_cargo_scope``, ADR-RTR-001 C1) -- resolves the
target's ``vitest`` binary via the shared ``resolve_tool`` scale, shells the
declared ``vitest run`` command at ``cwd=target_root``, and maps the exit code to
a verdict. The observables are the PASS/FAIL/INDETERMINATE verdict the run-facet
maps each ``vitest`` exit code to, and (AC-4) the argv + cwd the run-facet shelled
the fake ``vitest`` with.

VITEST-vs-cargo difference (like go): there is NO cargo-style exit-4 NO_MATCH
empty-scope row for vitest. So this enum has ONLY GREEN (exit 0) and RED
(non-zero); the empty-scope-INDETERMINATE case does NOT exist (it is OUT-OF-SCOPE
per the feature-delta; exit-0-is-PASS is the honest cheapest start). INDETERMINATE
for vitest is reached ONLY via an unresolvable ``vitest`` (AC-3), never via an exit
code.
"""

from __future__ import annotations

from enum import Enum


class RunnerVerdict(Enum):
    """The port-exposed verdict the vitest run-facet maps a ``vitest`` exit code to.

    The exit-semantics contract (each row pinned by an AT). The AT asserts ON this
    verdict (the run-facet's observable outcome), never on the raw exit code or an
    internal field:

    - ``PASS``          -- the declared ``vitest run`` command exited 0 (all pass).
                           ``RunVerdict(passed=True)``.
    - ``FAIL``          -- the command exited non-zero WITH tests executed (a
                           legit RED). ``RunVerdict(passed=False)`` -- PROPAGATED,
                           never swallowed into INDETERMINATE.
    - ``INDETERMINATE`` -- ``vitest`` was unresolvable after the full discovery
                           scale. Carried distinctly from FAIL via the
                           ``RunnerAdapterUnavailable`` degrade-LOUD channel
                           (NEVER a silent pass). Unlike cargo there is no exit-4
                           empty-scope row for vitest.
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class VitestExitScenario(Enum):
    """Which controlled FAKE-``vitest`` exit behaviour the fixture plants.

    A planted fake-``vitest`` executable emits a controlled exit code + output so
    the exit-semantics are exercised DETERMINISTICALLY in CI -- no real Node /
    vitest toolchain required. The fake-``vitest`` is a real chmod+x script on a
    controlled PATH that the run-facet resolves via the shared ``resolve_tool``
    scale and shells like any ``vitest``.

    Only TWO rows (no cargo-style NO_MATCH / exit-4): like go, vitest has no
    empty-scope exit-4 row, so empty-scope is OUT-OF-SCOPE (exit-0-is-PASS).

    - ``GREEN`` -- the fake exits 0 (all tests passed)         -> PASS.
    - ``RED``   -- the fake exits 1 AFTER emitting test output
                   (a real failure with tests executed)        -> FAIL (propagated).
    """

    GREEN = "green"
    RED = "red"
