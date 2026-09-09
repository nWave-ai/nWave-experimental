"""Immutable, validated routes through packaged workflow-shape transitions.

The catalog owns graph topology only.  Each ``WorkflowMigrationMap`` remains
the authority for transforming one edge of a route.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.workflow_format_migration import WorkflowMigrationMap


__all__ = ["WorkflowTransitionCatalog", "WorkflowTransitionCatalogError"]


class WorkflowTransitionCatalogError(Exception):
    """A packaged transition graph cannot safely determine one migration route."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            "WHAT: the packaged workflow-transition catalog is invalid. "
            f"WHY: {reason}. "
            "HOW: publish one well-formed acyclic catalog with a single "
            "terminal and exactly one outgoing transition per source."
        )


@dataclass(frozen=True)
class WorkflowTransitionCatalog:
    """Pure topology over immutable per-edge workflow migration maps."""

    transitions: tuple[WorkflowMigrationMap, ...]
    malformed_reason: str | None = None

    def route_from(self, tag: object) -> tuple[WorkflowMigrationMap, ...]:
        """Return the sole ordered route from ``tag`` to the catalog terminal."""
        by_source, terminal = self._validated_graph()
        if not isinstance(tag, str) or (tag not in by_source and tag != terminal):
            raise WorkflowTransitionCatalogError(
                f"unknown source tag {tag!r} has no route to terminal {terminal!r}"
            )
        route: list[WorkflowMigrationMap] = []
        current = tag
        while current != terminal:
            transition = by_source[current]
            route.append(transition)
            current = transition.to_tag
        return tuple(route)

    def _validated_graph(
        self,
    ) -> tuple[dict[str, WorkflowMigrationMap], str]:
        if self.malformed_reason is not None:
            raise WorkflowTransitionCatalogError(
                f"malformed catalog: {self.malformed_reason}"
            )
        if not self.transitions:
            raise WorkflowTransitionCatalogError(
                "malformed catalog: it has no transitions"
            )

        by_source: dict[str, WorkflowMigrationMap] = {}
        destinations: set[str] = set()
        for transition in self.transitions:
            if not isinstance(transition.to_tag, str) or not transition.to_tag:
                raise WorkflowTransitionCatalogError(
                    "malformed catalog: an edge has no target tag"
                )
            sources = tuple(transition.forward)
            if not sources or any(
                not isinstance(source, str) or not source for source in sources
            ):
                raise WorkflowTransitionCatalogError(
                    "malformed catalog: an edge has no source tag"
                )
            for source in sources:
                if source in by_source:
                    raise WorkflowTransitionCatalogError(
                        f"duplicate source tag {source!r} makes the route ambiguous"
                    )
                by_source[source] = transition
            destinations.add(transition.to_tag)

        self._reject_cycle(by_source)
        terminals = destinations - set(by_source)
        if len(terminals) != 1:
            raise WorkflowTransitionCatalogError(
                f"the catalog has {len(terminals)} terminal tags, not exactly one terminal"
            )
        return by_source, next(iter(terminals))

    @staticmethod
    def _reject_cycle(by_source: dict[str, WorkflowMigrationMap]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(source: str) -> None:
            if source in visiting:
                raise WorkflowTransitionCatalogError("the catalog contains a cycle")
            if source in visited:
                return
            visiting.add(source)
            target = by_source[source].to_tag
            if target in by_source:
                visit(target)
            visiting.remove(source)
            visited.add(source)

        for source in by_source:
            visit(source)
