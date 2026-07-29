"""The runner-capability probe -- QW5, mikado.md:47.

Answers ONE narrow question: for a given target environment, which of the
runners the gates already know how to invoke (``runner_registry.
seed_runner_registry``'s built-in tokens) are ACTUALLY invocable here? "Which
gates can invoke" is a PROPERTY of the live environment (GDP-8) -- it must
never be inferred from installed documentation, a README, or a static
reference table. Every verdict below is the result of an executed probe.

Three states only, never two (mikado.md:47 -- "records supported,
unsupported, or indeterminate against the declared environment"):

* ``supported``     -- the binary was DISCOVERED (PATH or a known install
  location) AND actually ran its version probe successfully. A definite
  positive.
* ``unsupported``   -- the binary was absent from every discovery rung. A
  definite, declared-fact negative (never inferred) -- ``resolve_tool``'s
  "not-found" rung IS the fact.
* ``indeterminate`` -- the binary was discovered but the version probe could
  not confirm it runs (non-zero exit, timeout, or a spawn-level OSError). The
  tool's PRESENCE is not proof of its INVOCABILITY (GDP-8: decide on the
  property, never the designation) -- this is the third state GDP-8 requires
  to reach the aggregate, never silently folded into either definite verdict.

REUSE, not reinvention (owns: this module + its CLI + its gate-contract
only): pytest routes through ``des.runtime.interpreter.python_for`` --
already a probed, memoized, never-name-trusted capability check, so this
module does not re-implement it. Every other runner routes through the SAME
3-rung ``tool_discovery.resolve_tool`` (PATH / known-location / not-found)
and the SAME ``known_locations`` constants each language-adapter runner
module already exports and depends on for gate execution -- this module asks
the identical discovery question a gate asks, ahead of time and for every
declared runner at once, rather than one at a time when a gate needs it.

The version-probe subprocess is bounded and process-group-reaped via
``des.runtime.spawn.spawn`` (the shared spawn boundary -- every child gets an
explicit stdin and a bound), never a bare ``subprocess.run``.

stdlib + in-tree ``des.runtime``/``des.adapters.driven.runner`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from des.adapters.driven.runner.cargo_runner import (
    CARGO_INSTALL_HINT,
    CARGO_KNOWN_LOCATIONS,
)
from des.adapters.driven.runner.csharp_runner import (
    DOTNET_INSTALL_HINT,
    DOTNET_KNOWN_LOCATIONS,
)
from des.adapters.driven.runner.go_runner import GO_INSTALL_HINT, GO_KNOWN_LOCATIONS
from des.adapters.driven.runner.java_runner import (
    JAVA_KNOWN_LOCATIONS,
    MAVEN_INSTALL_HINT,
)
from des.adapters.driven.runner.kotlin_runner import (
    GRADLE_INSTALL_HINT,
    GRADLE_KNOWN_LOCATIONS,
)
from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.adapters.driven.runner.vitest_runner import (
    VITEST_INSTALL_HINT,
    VITEST_KNOWN_LOCATIONS,
)
from des.runtime.interpreter import InterpreterUnavailable, python_for
from des.runtime.spawn import SpawnTimeout, spawn


RunnerStatus = Literal["supported", "unsupported", "indeterminate"]

# Bounds the version-probe subprocess (rung 3 of the property check). Short
# and non-configurable -- a well-behaved toolchain's `--version` returns in
# well under a second; a candidate that cannot answer this quickly is exactly
# the "cannot confirm invocability" case `indeterminate` exists to name.
_VERSION_PROBE_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class RunnerCapability:
    """One runner's verdict against the declared (live, probed) environment.

    Exactly one of the three ``status`` values applies (never a fourth,
    never a blend). ``remediation`` is populated for ``unsupported`` and
    ``indeterminate`` -- the GDP-3 self-explaining-rejection contract; it is
    ``None`` only for ``supported``, where there is nothing to remediate.
    """

    runner: str
    status: RunnerStatus
    evidence: str
    remediation: str | None = None


@dataclass(frozen=True)
class _RunnerProbeSpec:
    """One runner's probe recipe: binary name, discovery locations, version argv.

    ``install_hint`` is threaded VERBATIM into ``resolve_tool``'s own
    ``install_hint`` parameter (GDP-3/GDP-4: the HOW must route to the
    REAL producer for THIS runner, never a generic template) -- it is the
    SAME constant each runner module's own gate-execution call site passes,
    imported here rather than duplicated, so this probe's "unsupported"
    verdict and a gate's own ``RunnerAdapterUnavailable`` reason are the
    IDENTICAL string by construction. Team-lead review 2026-07-29 found the
    root cause one layer down, in ``resolve_tool`` itself: its OLD default
    templated "install via rustup or `cargo install <name>`" for EVERY tool,
    correct only for cargo -- producing FALSE remediation (`cargo install
    go`, `cargo install vitest`, ...) for the other five. Fixed at the
    shared function (now a neutral, non-inventing default) plus a
    per-ecosystem hint at each of its six call sites, this probe's own
    module included.
    """

    runner: str
    binary: str
    known_locations: tuple[str, ...]
    version_args: tuple[str, ...]
    install_hint: str


# The declared environment this module probes: every non-pytest runner token
# `runner_registry.seed_runner_registry` registers as a built-in run-facet
# (`runner_registry.py:251-257`), paired with the SAME `*_KNOWN_LOCATIONS`
# constant its own gate-execution path already depends on -- so a "supported"
# verdict here and a gate's own discovery agree by construction, never by
# coincidence. pytest is deliberately absent: it is probed separately via
# `python_for`, the pre-existing interpreter-capability boundary (see
# `probe_all_runner_capabilities`).
_PROBE_TABLE: tuple[_RunnerProbeSpec, ...] = (
    _RunnerProbeSpec(
        "cargo-test",
        "cargo",
        CARGO_KNOWN_LOCATIONS,
        ("--version",),
        install_hint=CARGO_INSTALL_HINT,
    ),
    _RunnerProbeSpec(
        "go-test",
        "go",
        GO_KNOWN_LOCATIONS,
        ("version",),
        install_hint=GO_INSTALL_HINT,
    ),
    _RunnerProbeSpec(
        "vitest",
        "vitest",
        VITEST_KNOWN_LOCATIONS,
        ("--version",),
        install_hint=VITEST_INSTALL_HINT,
    ),
    _RunnerProbeSpec(
        "gradle-test",
        "gradlew",
        GRADLE_KNOWN_LOCATIONS,
        ("--version",),
        install_hint=GRADLE_INSTALL_HINT,
    ),
    _RunnerProbeSpec(
        "dotnet-test",
        "dotnet",
        DOTNET_KNOWN_LOCATIONS,
        ("--version",),
        install_hint=DOTNET_INSTALL_HINT,
    ),
    _RunnerProbeSpec(
        "maven-test",
        "mvn",
        JAVA_KNOWN_LOCATIONS,
        ("--version",),
        install_hint=MAVEN_INSTALL_HINT,
    ),
)


def _first_line(text: str) -> str:
    """The first non-empty line of ``text``, or the empty string."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _probe_binary_capability(
    spec: _RunnerProbeSpec, target_root: Path
) -> RunnerCapability:
    """Discover + version-probe one binary-based runner (GDP-8 property check).

    Discovery (``resolve_tool``) answers the DESIGNATION question ("is a file
    here"); the version-probe subprocess answers the PROPERTY question ("does
    it run"). A ``resolve_tool`` "not-found" is a definite declared fact
    (``unsupported``, never inferred); a discovered-but-non-running binary is
    the third state (``indeterminate``) -- absence of proof is not proof of
    absence.
    """
    resolution = resolve_tool(
        spec.binary,
        spec.known_locations,
        base_dir=target_root,
        install_hint=spec.install_hint,
    )
    if resolution.path is None:
        return RunnerCapability(
            runner=spec.runner,
            status="unsupported",
            evidence=f"'{spec.binary}' not found (rung: {resolution.rung})",
            remediation=resolution.remediation,
        )

    argv = [resolution.path, *spec.version_args]
    try:
        completed = spawn(
            argv,
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_SECONDS,
        )
    except (SpawnTimeout, OSError) as exc:
        return RunnerCapability(
            runner=spec.runner,
            status="indeterminate",
            evidence=(
                f"'{spec.binary}' found at {resolution.path} "
                f"(rung: {resolution.rung}) but the version probe raised {exc!r}"
            ),
            remediation=(
                f"verify manually: `{' '.join(argv)}`; the binary is present "
                "but its invocability could not be confirmed"
            ),
        )

    if completed.returncode != 0:
        return RunnerCapability(
            runner=spec.runner,
            status="indeterminate",
            evidence=(
                f"'{spec.binary}' found at {resolution.path} "
                f"(rung: {resolution.rung}) but `{' '.join(spec.version_args)}` "
                f"exited {completed.returncode}: {_first_line(completed.stderr or '')}"
            ),
            remediation=(
                f"verify manually: `{' '.join(argv)}`; the binary is present "
                "but its invocability could not be confirmed"
            ),
        )

    return RunnerCapability(
        runner=spec.runner,
        status="supported",
        evidence=(
            f"'{spec.binary}' at {resolution.path} (rung: {resolution.rung}) "
            f"-- {_first_line(completed.stdout or '')}"
        ),
    )


def _probe_pytest_capability(target_root: Path) -> RunnerCapability:
    """Probe pytest through the EXISTING interpreter-capability boundary.

    Deliberately does not duplicate ``tool_discovery``/``spawn`` for pytest:
    ``python_for`` already IS the probed, never-name-trusted capability check
    every ``des`` pytest gate resolves through (``interpreter.py`` module
    docstring). Reusing it means a "supported" verdict here and a gate's own
    interpreter resolution can never disagree.
    """
    try:
        interpreter = python_for("pytest", repo_root=target_root)
    except InterpreterUnavailable as exc:
        return RunnerCapability(
            runner="pytest",
            status="unsupported",
            evidence="no interpreter on the fallback ladder can import pytest",
            remediation=str(exc),
        )
    return RunnerCapability(
        runner="pytest",
        status="supported",
        evidence=f"resolved interpreter: {interpreter}",
    )


def probe_all_runner_capabilities(
    target_root: Path | None = None,
) -> tuple[RunnerCapability, ...]:
    """Probe every declared runner against ``target_root`` (default: cwd).

    Returns one ``RunnerCapability`` per declared runner (pytest plus every
    ``_PROBE_TABLE`` entry), in declaration order. Never raises on an
    individual runner's absence or failure to invoke -- that is exactly the
    ``unsupported``/``indeterminate`` verdict, not an exception (GDP-6:
    degrade LOUD via a returned, typed record, never a silent pass and never
    an uncaught traceback).
    """
    root = target_root if target_root is not None else Path.cwd()
    return (
        _probe_pytest_capability(root),
        *(_probe_binary_capability(spec, root) for spec in _PROBE_TABLE),
    )


__all__ = [
    "RunnerCapability",
    "RunnerStatus",
    "probe_all_runner_capabilities",
]
