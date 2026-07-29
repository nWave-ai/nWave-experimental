"""Typed domain vocabulary for cpp-test-runner-adapter slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists). These types are
TEST-LOCAL -- they never import production code; the ATs drive the SUT (the C++
run-facet ``run_cpp_scope`` + the AT-discovery facet ``discover_cpp_ats``) only
through the composition-root driving port (Mandate-13, Layer 3 subprocess: a
child interpreter imports the SUT and runs it over a REAL controlled filesystem +
a FAKE-``make`` executable on a controlled PATH, or over the REAL polyglot pilot
fixture files for AT-discovery).

slice-01 surface (mirrors go-test-runner-adapter, ADR-RTR-001 C1, plus kotlin/
csharp-test-runner-adapter's AT-discovery facet pair): the C++ ``run_cpp_scope``
run-facet resolves the target's ``make`` binary via the shared ``resolve_tool``
scale, shells the declared ``make test`` command, and maps the exit code to a
verdict -- exactly like ``run_go_scope`` / ``run_csharp_scope``. The observables
are the PASS/FAIL/INDETERMINATE verdict and the AT-discovery result
(``discover_cpp_ats``, mirroring ``discover_kotlin_ats`` / ``discover_csharp_ats``).

CPP-vs-cargo: GNU ``make`` wraps a failing recipe line's exit code into its OWN
non-zero exit (verified empirically during DISTILL: a real fake-Makefile probe
showed ``make: *** [Makefile:N: test] Error N`` -> ``make`` itself exits with a
generic non-zero code, e.g. 2) -- there is NO cargo-style exit-4 NO_MATCH
empty-scope row. So this enum has ONLY GREEN (exit 0) and RED (non-zero);
INDETERMINATE for C++ is reached ONLY via an unresolvable ``make`` (AC-3), never
via an exit code.
"""

from __future__ import annotations

from enum import Enum


class RunnerVerdict(Enum):
    """The port-exposed verdict the C++ run-facet maps a ``make`` exit code to.

    The exit-semantics contract (each row pinned by an AT). The AT asserts ON this
    verdict (the run-facet's observable outcome), never on the raw exit code or an
    internal field:

    - ``PASS``          -- the declared ``make test`` command exited 0 (all pass).
                           ``RunVerdict(passed=True)``.
    - ``FAIL``          -- the command exited non-zero WITH tests executed (a
                           legit RED). ``RunVerdict(passed=False)`` -- PROPAGATED,
                           never swallowed into INDETERMINATE.
    - ``INDETERMINATE`` -- ``make`` was unresolvable after the full discovery
                           scale. Carried distinctly from FAIL via the
                           ``RunnerAdapterUnavailable`` degrade-LOUD channel
                           (NEVER a silent pass). Unlike cargo there is no exit-4
                           empty-scope row for make.
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class MakeExitScenario(Enum):
    """Which controlled FAKE-``make`` exit behaviour the fixture plants.

    A planted fake-``make`` executable emits a controlled exit code + output so
    the exit-semantics are exercised DETERMINISTICALLY in CI -- no real g++/make
    toolchain build required for these rows. The fake ``make`` is a real chmod+x
    script on a controlled PATH that the run-facet resolves via the shared
    ``resolve_tool`` scale and shells like any ``make``.

    Only TWO rows (no cargo-style NO_MATCH / exit-4): a failing recipe line's
    exit is wrapped into make's OWN non-zero exit, so empty-scope is
    OUT-OF-SCOPE (exit-0-is-PASS / any-non-zero-is-FAIL).

    - ``GREEN`` -- the fake exits 0 (all tests passed)         -> PASS.
    - ``RED``   -- the fake exits 2 AFTER emitting test output
                   (a real failure with tests executed)        -> FAIL (propagated).
    """

    GREEN = "green"
    RED = "red"
