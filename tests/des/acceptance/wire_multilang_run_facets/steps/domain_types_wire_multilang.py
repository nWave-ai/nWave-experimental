"""Typed domain vocabulary for wire-multilang-run-facets slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin names is
expressed once here as a typed enum, so the composition methods consume typed parameters
(no raw ``str`` where an enum exists). These types are TEST-LOCAL -- they never import
production code; the ATs drive the SUT (the PRODUCTION REGISTRY DISPATCH:
``seed_runner_registry()`` + ``RunnerAdapter(token).run(...)``) only through the
composition-root driving port (Mandate-13, Layer 3 subprocess: a child interpreter seeds
the registry and runs the production dispatch over a REAL controlled filesystem + a FAKE
runner executable on a controlled PATH).

slice-01 surface (feature-delta AC-1..3): the registry WIRING. The observable is whether
the PRODUCTION dispatch ``RunnerAdapter(token).run(target, command)`` REACHES the run-facet
(returning a ``RunVerdict``) -- the WIRED outcome -- or fails with ``RunnerAdapterUnavailable``
because the token is NOT registered in ``seed_runner_registry`` (the UNWIRED outcome, RED at
HEAD). The distinction WIRED-vs-UNWIRED is the load-bearing observable: it is exactly what
separates "the dispatch reached the run-facet" (GREEN, post-DELIVER) from
"RunnerAdapterUnavailable because the run-facet was never registered" (RED, at HEAD).
"""

from __future__ import annotations

from enum import Enum


class DispatchOutcome(Enum):
    """The port-exposed outcome of the PRODUCTION registry dispatch for a runner token.

    The AT asserts ON this outcome (the observable of ``RunnerAdapter(token).run(...)`` over
    the production registry), never on an internal field or a direct run-facet import:

    - ``WIRED``   -- ``seed_runner_registry()`` registered the token, so
                     ``GLOBAL_REGISTRY.lookup(token)`` resolves to the run-facet AND
                     ``RunnerAdapter(token).run(...)`` REACHED it, returning a ``RunVerdict``.
                     This is the GREEN outcome the feature delivers.
    - ``UNWIRED`` -- the token is NOT registered (``seed_runner_registry`` registers only
                     pytest + cargo-test at HEAD), so ``lookup`` returns None and the
                     dispatch raises ``RunnerAdapterUnavailable`` -- the run-facet was never
                     reached. This is the RED outcome at HEAD (the registration-missing
                     reason), carried DISTINCTLY from a run-facet FAIL.
    """

    WIRED = "wired"
    UNWIRED = "unwired"


class RunnerToken(Enum):
    """The runner token ``TestRunnerPort.resolve`` returns for a target's lockfile.

    The registry key under which a run-facet is (or is not) registered. ``resolve`` already
    maps these (test_runner_port.py _REGISTRY:149-151, UNCHANGED): go.mod -> ``go-test``,
    package.json(vitest) -> ``vitest``, Cargo.toml -> ``cargo-test``, pyproject.toml ->
    ``pytest``. The wiring this feature adds is the ``seed_runner_registry`` REGISTRATION of
    the go-test / vitest tokens (the cargo-test / pytest tokens are already registered).
    """

    GO_TEST = "go-test"
    VITEST = "vitest"
    CARGO_TEST = "cargo-test"
    PYTEST = "pytest"


class TargetLanguage(Enum):
    """Which hermetic target tree + FAKE runner binary the fixture plants.

    A planted fake runner is a REAL chmod+x script on a controlled PATH that the run-facet
    resolves via the shared ``resolve_tool`` scale and shells like the real tool, exiting 0
    (so a WIRED dispatch maps it to a PASS ``RunVerdict``). The target tree carries the
    lockfile ``resolve`` keys off (go.mod / package.json+vitest), so the production dispatch
    resolves the correct token end-to-end.

    - ``GO``     -- a go.mod target + a fake ``go`` on PATH (token ``go-test``).
    - ``VITEST`` -- a package.json declaring vitest + a fake ``vitest`` on PATH
                    (token ``vitest``).
    """

    GO = "go"
    VITEST = "vitest"
