"""Typed domain vocabulary for kotlin-test-runner-adapter slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists). These types are
TEST-LOCAL -- they never import production code; the ATs drive the SUT (the
Kotlin run-facet ``run_kotlin_scope`` + the AT-discovery facet
``discover_kotlin_ats`` + the routing registry ``resolve``) only through the
composition-root driving port (Mandate-13, Layer 3 subprocess: a child
interpreter imports the SUT and runs it over a REAL controlled filesystem + a
FAKE-``gradlew`` executable on a controlled PATH).

slice-01 surface (mirrors go-test-runner-adapter, ADR-RTR-001 C1): the Kotlin
``run_kotlin_scope`` run-facet resolves the target's ``gradlew`` binary via the
shared ``resolve_tool`` scale, shells the declared ``gradlew test`` command, and
maps the exit code to a verdict -- exactly like ``run_go_scope``. The
observables are the PASS/FAIL/INDETERMINATE verdict, the AT-discovery result
(``discover_kotlin_ats``, mirroring ``discover_pytest_ats`` /
``discover_cargo_ats``), and the resolve() registry token a build.gradle.kts
target routes to.
"""

from __future__ import annotations

from enum import Enum


class RunnerVerdict(Enum):
    """The port-exposed verdict the Kotlin run-facet maps a ``gradlew`` exit code to.

    - ``PASS``          -- the declared ``gradlew test`` command exited 0 (all
                           pass). ``RunVerdict(passed=True)``.
    - ``FAIL``          -- the command exited non-zero WITH tests executed (a
                           legit RED). ``RunVerdict(passed=False)`` -- PROPAGATED,
                           never swallowed into INDETERMINATE.
    - ``INDETERMINATE`` -- ``gradlew`` was unresolvable after the full discovery
                           scale. Carried distinctly from FAIL via the
                           ``RunnerAdapterUnavailable`` degrade-LOUD channel
                           (NEVER a silent pass).
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class GradleExitScenario(Enum):
    """Which controlled FAKE-``gradlew`` exit behaviour the fixture plants.

    A planted fake-``gradlew`` executable emits a controlled exit code so the
    exit-semantics are exercised DETERMINISTICALLY in CI -- no real Gradle/JDK
    toolchain required. The fake ``gradlew`` is a real chmod+x script on a
    controlled PATH that the run-facet resolves via the shared ``resolve_tool``
    scale and shells like any ``gradlew``.

    - ``GREEN`` -- the fake exits 0 (all tests passed)         -> PASS.
    - ``RED``   -- the fake exits 1 AFTER emitting test output
                   (a real failure with tests executed)        -> FAIL (propagated).
    """

    GREEN = "green"
    RED = "red"
