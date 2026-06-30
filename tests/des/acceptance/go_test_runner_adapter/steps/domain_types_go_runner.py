"""Typed domain vocabulary for go-test-runner-adapter slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists). These types are
TEST-LOCAL -- they never import production code; the ATs drive the SUT (the Go
run-facet ``run_go_scope``) only through the composition-root driving port
(Mandate-13, Layer 3 subprocess: a child interpreter imports the SUT and runs it
over a REAL controlled filesystem + a FAKE-``go`` executable on a controlled PATH).

slice-01 surface (feature-delta AC-1..4): the Go ``run_go_scope`` run-facet
(mirror of ``run_cargo_scope``, ADR-RTR-001 C1) -- resolves the target's ``go``
binary via the shared ``resolve_tool`` scale, shells the declared ``go test``
command at ``cwd=target_root``, and maps the exit code to a verdict. The
observables are the PASS/FAIL/INDETERMINATE verdict the run-facet maps each ``go``
exit code to, and (AC-4) the argv + cwd the run-facet shelled the fake ``go`` with.

GO-vs-cargo difference: ``go test`` exits 0 even with NO tests (it prints "no test
files") -- there is NO cargo-style exit-4 NO_MATCH empty-scope. So this enum has
ONLY GREEN (exit 0) and RED (non-zero); the empty-scope-INDETERMINATE case does
NOT exist for Go (it is OUT-OF-SCOPE per the feature-delta; exit-0-is-PASS is the
honest cheapest start). INDETERMINATE for Go is reached ONLY via an unresolvable
``go`` (AC-3), never via an exit code.
"""

from __future__ import annotations

from enum import Enum


class RunnerVerdict(Enum):
    """The port-exposed verdict the Go run-facet maps a ``go`` exit code to.

    The exit-semantics contract (each row pinned by an AT). The AT asserts ON this
    verdict (the run-facet's observable outcome), never on the raw exit code or an
    internal field:

    - ``PASS``          -- the declared ``go test`` command exited 0 (all pass).
                           ``RunVerdict(passed=True)``.
    - ``FAIL``          -- the command exited non-zero WITH tests executed (a
                           legit RED). ``RunVerdict(passed=False)`` -- PROPAGATED,
                           never swallowed into INDETERMINATE.
    - ``INDETERMINATE`` -- ``go`` was unresolvable after the full discovery scale.
                           Carried distinctly from FAIL via the
                           ``RunnerAdapterUnavailable`` degrade-LOUD channel
                           (NEVER a silent pass). Unlike cargo there is no exit-4
                           empty-scope row for Go.
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class GoExitScenario(Enum):
    """Which controlled FAKE-``go`` exit behaviour the fixture plants.

    A planted fake-``go`` executable emits a controlled exit code + output so the
    exit-semantics are exercised DETERMINISTICALLY in CI -- no real Go toolchain
    required. The fake-``go`` is a real chmod+x script on a controlled PATH that
    the run-facet resolves via the shared ``resolve_tool`` scale and shells like
    any ``go``.

    Only TWO rows (no cargo-style NO_MATCH / exit-4): ``go test`` exits 0 even with
    zero test files, so empty-scope is OUT-OF-SCOPE (exit-0-is-PASS).

    - ``GREEN`` -- the fake exits 0 (all tests passed)         -> PASS.
    - ``RED``   -- the fake exits 1 AFTER emitting test output
                   (a real failure with tests executed)        -> FAIL (propagated).
    """

    GREEN = "green"
    RED = "red"
