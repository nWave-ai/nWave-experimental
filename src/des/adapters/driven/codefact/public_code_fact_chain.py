"""The public code-fact composition, staged as ``code_fact_chain.py`` in wheels.

Only bundled, dependency-free providers participate. The source checkout's
optional indexed provider is composed separately; it is not a wheel asset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
from des.adapters.driven.codefact.text_search_code_fact_adapter import TextSearchAdapter
from des.ports.code_fact_port import (
    Answered,
    resolve_through_fold,
    verify_composition_coverage,
)


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.code_fact_port import (
        CapabilityDescriptor,
        CodeFactResult,
        Resolution,
    )


class CodeFactChain:
    """Resolve through the structural adapter and the textual floor."""

    optional_index_dir: str | None = None

    def __init__(self, root: Path | str) -> None:
        self._providers = (AstAdapter(root=root), TextSearchAdapter(root=root))
        verify_composition_coverage(self._providers)

    def scoped(self, root: Path | str) -> CodeFactChain:
        """Scope a new chain to a file under this tree."""
        return CodeFactChain(root)

    def resolve(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> Resolution:
        """Return the winning answer and honest per-provider trace."""
        return resolve_through_fold(descriptor, request, self._providers)

    def query(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult | None:
        """Thin result-only edge over the same fold."""
        resolution = self.resolve(descriptor, request)
        return resolution.payload if isinstance(resolution, Answered) else None
