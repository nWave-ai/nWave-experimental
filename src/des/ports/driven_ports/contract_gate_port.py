"""ContractGatePort -- driven port: a per-language contract-gate facet (C2).

Feature `unified-language-adapter-registry`, slice-01 prefactoring (ADR-ULAR-001).
Structural (``typing.Protocol``), matching the EXISTING ``RunFacet``/``ListFacet``
Protocol shape in ``runner_registry.py`` (DDD-U3/technology-choices: consistency,
zero new dependency). A concrete adapter (e.g. the slice-02 ``PythonContractGateAdapter``)
WRAPS the existing hardcoded ``_collect_scope_uncached``/``_run_contract_suite``
bodies in ``run_contract_gate.py`` verbatim -- this port only fixes the boundary
shape, never the pytest-invocation internals (architecture owns WHAT, not HOW).

Registered into ``LanguageAdapterRegistry.register_contract_gate(name, facet)``
under the RESOLVED TOOL-NAME (``RunnerAdapter.name``, e.g. ``"pytest"``), the
SAME key ``GLOBAL_REGISTRY.lookup()`` already uses (DDD-U5) -- never
``target_language``.

Stdlib-only at import time (``__future__`` + ``typing`` + ``pathlib``), per F-D-09
(no ``scripts.*`` import from ``src/des/**``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ContractVerdict:
    """The observable outcome of a registered contract-gate facet's suite run.

    Mirrors ``RunVerdict`` (``des.ports.test_runner_port``): ``passed`` is the
    only behavioral observable; ``runner`` names which resolved tool-name
    produced it. HOW the verdict was earned (the concrete subprocess argv,
    the exit-code mapping) is the per-language adapter's concern, never the
    port's.
    """

    passed: bool
    runner: str


class ContractGatePort(Protocol):
    """Driven port: a per-language contract-gate facet.

    ``collect_scope`` enumerates the target's node-id scope (the digest-mode
    counterpart); ``run_suite`` runs the whole-tree contract suite and reports
    the outcome (the run-mode counterpart).
    """

    def collect_scope(self, repo: Path) -> list[str]:
        """Enumerate the target's contract-gate node-id scope."""
        ...

    def run_suite(
        self, repo: Path, *, junit_xml_path: Path | None = None
    ) -> ContractVerdict:
        """Run the target's contract suite; return the observable verdict.

        ``junit_xml_path`` (fix-feature-end-refusal-names-failing-tests),
        when given, asks the facet to persist a JUnit XML report of THIS run
        at that filesystem path -- a facet that cannot honor it may ignore
        the kwarg; the pytest facet honors it.
        """
        ...


__all__ = ["ContractGatePort", "ContractVerdict"]
