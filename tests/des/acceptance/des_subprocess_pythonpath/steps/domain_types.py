"""Domain types for fix-des-subprocess-pythonpath slice-01 (Mandate-12 criterion 1).

Every domain noun used in the Gherkin is expressed ONCE here as a typed enum /
dataclass / NewType. Step bodies and the composition service consume these typed
parameters -- no raw ``str`` where a domain enum exists (criterion 1 + 2).

The feature CENTRALIZES every ``des``-module subprocess spawn behind a single
``des_spawn(capability, *module_args, **kw)`` helper in ``des.runtime.interpreter``
that applies ``python_for(capability)`` + ``des_subprocess_env()`` BY
CONSTRUCTION, so a spawned ``des.cli`` child never loses ``des`` from its import
path. At HEAD ~18 inline spawn sites bypass the helper (AC-1 RED) and the helper
itself does not exist (AC-2/AC-3 RED).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SpawnCapability(Enum):
    """The interpreter capability a des-module spawn requests.

    ``NONE`` maps to ``python_for(None)`` -- the running interpreter, for a
    ``-m des.cli.*`` spawn that needs only *a* Python with ``des`` visible.
    ``PYTEST`` maps to ``python_for("pytest")`` -- the probed ladder, for a
    spawn that must import pytest in the child.
    """

    NONE = "none"
    PYTEST = "pytest"


class ChildImportOutcome(Enum):
    """The observable outcome of a spawned ``des.cli`` child importing ``des``.

    Port-exposed via the child process exit code: a child that imported ``des``
    and ran ``--help`` exits ``IMPORTED`` (0); a child that could not find
    ``des`` exits ``MODULE_NOT_FOUND`` (non-zero, ``ModuleNotFoundError: des``).
    """

    IMPORTED = "imported"
    MODULE_NOT_FOUND = "module-not-found"


@dataclass(frozen=True)
class ArchBanViolation:
    """One inline des-module spawn that bypasses ``des_spawn`` (AC-1).

    A ``src/des/**`` source location where a raw ``subprocess.*`` spawner's
    argv[0] is a ``python_for(...)`` call done INLINE rather than routed through
    the sanctioned ``des_spawn`` helper. The arch-walk over the REAL tree
    collects these; an empty collection is the GREEN target.
    """

    location: str  # "<relative-path>:<lineno>"
    detail: str


@dataclass(frozen=True)
class SanctionedDesModuleSubcommand:
    """A real, read-only ``des.cli`` subcommand safe to spawn in an AT (AC-2).

    ``des.cli.health_check --help`` is verified read-only (verb ``--help`` prints
    usage, mutates nothing) and exits 0 only if the child imported ``des``.
    """

    module: str  # e.g. "des.cli.health_check"
    readonly_arg: str  # e.g. "--help"


@dataclass
class SpiedSpawnCall:
    """The observable record of ONE ``subprocess.run`` invocation made by the
    real ``des_spawn`` helper (AC-3, AC-4 -- spy/monkeypatch boundary).

    These fields ARE the Universe of port-exposed observables for the
    by-construction and kwargs-forwarding assertions: what argv the helper
    composed, what env it applied, and which caller kwargs it forwarded -- all
    WITHOUT the caller passing the interpreter or the env.
    """

    argv: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    kwargs: dict[str, object] = field(default_factory=dict)

    @property
    def argv0(self) -> str:
        """The interpreter path the helper put at argv[0]."""
        return self.argv[0] if self.argv else ""

    @property
    def pythonpath(self) -> str:
        """The PYTHONPATH the helper applied to the child env ("" if absent)."""
        return self.env.get("PYTHONPATH", "")
