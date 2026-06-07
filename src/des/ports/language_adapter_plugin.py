"""LanguageAdapterPlugin ABC + ProbeResult dataclass.

F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE slice-02 substrate.

Per M44 Option (a) (architect amendment APPROVED composite 9.1) this ABC
is INTENTIONALLY DECOUPLED from :class:`scripts.install.plugins.base.InstallationPlugin`.
The M42 attempt embedded a ``from scripts.install.plugins.base import InstallationPlugin``
in this module which violated:

* friction #38 ``test_des_no_dev_root_imports`` build gate -- shipped
  ``src/des/**`` MUST NOT import ``scripts.*`` (dev-root absent on target machine)
* friction #41 ``F-D-09`` forbidden-import-roots architect-side principle
  (mechanical rejection regex ``^from scripts\\.`` for ABCs under ``src/des/ports/``)

The M44 refactor moves the dual-base concrete fixture out of ``src/des/ports/``
into ``scripts/install/plugins/_conformance_fixture_language_adapter.py`` where
the dual-inheritance is legal (scripts.* can freely cross-import to des.* ports).
This module ships a PURE ABC with stdlib + abc only -- the
:class:`scripts.install.plugins.base.InstallationPlugin` contract is mixed-in
exclusively at the concrete fixture site (MRO-validated linearization
``[ConformanceFixture, InstallationPlugin, LanguageAdapterPlugin, ABC, object]``).

Every per-language plugin (slice-05a Python, slice-07 TypeScript, future Go /
Rust / Java) inherits BOTH this ABC AND ``InstallationPlugin`` at its concrete
site (NOT through this ABC). The four mandatory contract members declared
here are all abstract -- a subclass that omits any of them cannot be
instantiated:

* ``target_language`` -- the kebab-case language identifier (``"python"``,
  ``"typescript"``, ...). slice-03's doctor CLI uses this to build
  per-target lookups.
* ``register_adapters(registry)`` -- per-port adapter wiring entry point;
  takes the composition-root adapter registry as argument. slice-05a /
  slice-07 plugins implement the language-specific wiring.
* ``probe()`` -- Earned-Trust (principle 13) environment probe contract;
  returns :class:`ProbeResult`. slice-05a ships the first concrete probe
  + Python lies catalog (slice-05b non-vacuity gate).
* ``port_coverage`` -- per-port coverage matrix; doctor CLI cross-products
  with the SSOT catalog to compute the GAPS report.

PyPI entry-points discovery substrate: every per-language plugin is
registered in the ``nwave.lang.adapter`` entry-point group (ADR-031
Option C). The doctor CLI and conformance check use
``importlib.metadata.entry_points(group='nwave.lang.adapter')`` to discover
registered classes; each MUST be-a :class:`LanguageAdapterPlugin` subclass.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Any


@dataclass(frozen=True)
class ProbeResult:
    """The verdict of one Earned-Trust environment probe.

    Frozen: an Earned-Trust observation is immutable once taken.

    Fields:
        ok: ``True`` when every probed port resolved its real-environment
            preconditions (toolchain present, version sane, lies-catalog
            clear). ``False`` when at least one port failed its probe.
        missing_ports: the list of port-ids whose probe failed (empty when
            ``ok=True``). The doctor CLI surfaces this list in the gap
            report; slice-05a's Python plugin populates it from the Python
            lies-catalog.
        probed_at: when the probe ran. Slice-04 surfaces this in the
            doctor JSON envelope for operator-visible freshness.
    """

    ok: bool
    missing_ports: list[str]
    probed_at: datetime


class LanguageAdapterPlugin(ABC):
    """Abstract base class every per-language plugin MUST subclass.

    PURE ABC (M44 Option a): does NOT subclass
    :class:`scripts.install.plugins.base.InstallationPlugin` -- the
    install-pipeline contract is mixed-in at concrete plugin sites under
    ``scripts/install/plugins/`` where dev-root imports are legal. Every
    concrete per-language plugin inherits BOTH this ABC AND
    ``InstallationPlugin`` (MRO-validated dual inheritance per M44 H2).

    The four contract members declared below are abstract -- a subclass
    that omits any of them cannot be instantiated. The ABC is intentionally
    minimal: it pins the contract surface every successor (slice-05a Python,
    slice-07 TypeScript, future Go / Rust / Java) must satisfy without
    prescribing implementation.
    """

    @property
    @abstractmethod
    def target_language(self) -> str:
        """The kebab-case language identifier this plugin targets.

        Examples: ``"python"``, ``"typescript"``, ``"go"``. slice-03's
        doctor CLI uses this string to build per-target lookups against
        the SSOT port catalog.
        """

    @property
    @abstractmethod
    def port_coverage(self) -> dict[str, bool]:
        """Per-port coverage matrix for this language.

        Keys are port-ids from the SSOT language-adapter port catalog;
        values are ``True`` when this plugin provides a real adapter for
        the port and ``False`` when the port is uncovered. The doctor CLI
        cross-products this with the catalog to compute the GAPS report.
        """

    @abstractmethod
    def register_adapters(self, registry: Any) -> None:
        """Wire this plugin's per-port adapters into the composition-root registry.

        Args:
            registry: the composition-root adapter registry that the install
                pipeline passes during wiring. Subclasses register their
                concrete adapters (e.g., Python's pytest gate adapter,
                TypeScript's vitest gate adapter) by writing into the
                registry's per-port slots.
        """

    @abstractmethod
    def probe(self) -> ProbeResult:
        """Run the Earned-Trust environment probe for this language.

        Returns:
            ProbeResult: the verdict of the probe. ``ok=True`` when every
                probed port resolved its real-environment preconditions;
                ``ok=False`` with ``missing_ports`` populated when at least
                one port failed (e.g., toolchain absent, version mismatch).
        """
