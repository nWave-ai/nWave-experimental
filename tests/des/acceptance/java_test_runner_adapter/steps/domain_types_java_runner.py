"""Typed domain vocabulary for java-test-runner-adapter slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists). These types are
TEST-LOCAL -- they never import production code; the ATs drive the SUT (the
Java run-facet ``run_java_scope`` + the AT-discovery facet
``discover_java_ats``) only through the composition-root driving port
(Mandate-13, Layer 3 subprocess: a child interpreter imports the SUT and runs
it over a REAL controlled filesystem + a FAKE-``mvn`` executable on a
controlled PATH).

slice-01 surface (feature-delta AC-1..6): the Java ``run_java_scope`` run-facet
(mirror of ``run_go_scope``/``run_cargo_scope``) -- resolves the target's
``mvn`` binary via the shared ``resolve_tool`` scale, shells the declared
``mvn test`` command at ``cwd=target_root``, and maps the exit code to a
verdict -- plus the ``discover_java_ats`` AT-discovery facet (mirror of
``discover_pytest_ats``/``discover_cargo_ats``) -- scans a regression file's
raw bytes for ``@Test``-attributed method names and returns them alongside a
sha256 content seal.

JAVA-vs-cargo difference: ``mvn test`` exits 0 even with NO test files (like
``go test``) -- there is NO cargo-style exit-4 NO_MATCH empty-scope. So this
enum has ONLY GREEN (exit 0) and RED (non-zero); the empty-scope-INDETERMINATE
case does NOT exist for Java (it is OUT-OF-SCOPE per the feature-delta;
exit-0-is-PASS is the honest cheapest start). INDETERMINATE for Java is
reached ONLY via an unresolvable ``mvn`` (AC-3), never via an exit code.
"""

from __future__ import annotations

from enum import Enum


class RunnerVerdict(Enum):
    """The port-exposed verdict the Java run-facet maps an ``mvn`` exit code to.

    The exit-semantics contract (each row pinned by an AT). The AT asserts ON
    this verdict (the run-facet's observable outcome), never on the raw exit
    code or an internal field:

    - ``PASS``          -- the declared ``mvn test`` command exited 0 (all
                           pass). ``RunVerdict(passed=True)``.
    - ``FAIL``          -- the command exited non-zero WITH tests executed (a
                           legit RED, Maven's BUILD FAILURE).
                           ``RunVerdict(passed=False)`` -- PROPAGATED, never
                           swallowed into INDETERMINATE.
    - ``INDETERMINATE`` -- ``mvn`` was unresolvable after the full discovery
                           scale. Carried distinctly from FAIL via the
                           ``RunnerAdapterUnavailable`` degrade-LOUD channel
                           (NEVER a silent pass). Unlike cargo there is no
                           exit-4 empty-scope row for Java/Maven.
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class MavenExitScenario(Enum):
    """Which controlled FAKE-``mvn`` exit behaviour the fixture plants.

    A planted fake-``mvn`` executable emits a controlled exit code + output so
    the exit-semantics are exercised DETERMINISTICALLY in CI -- no real
    Maven/JDK toolchain required. The fake-``mvn`` is a real chmod+x script on
    a controlled PATH that the run-facet resolves via the shared
    ``resolve_tool`` scale and shells like any ``mvn``.

    Only TWO rows (no cargo-style NO_MATCH / exit-4): ``mvn test`` exits 0
    even with zero test files, so empty-scope is OUT-OF-SCOPE
    (exit-0-is-PASS).

    - ``GREEN`` -- the fake exits 0 (all tests passed)         -> PASS.
    - ``RED``   -- the fake exits 1 AFTER emitting test output
                   (a real failure with tests executed)        -> FAIL (propagated).
    """

    GREEN = "green"
    RED = "red"
