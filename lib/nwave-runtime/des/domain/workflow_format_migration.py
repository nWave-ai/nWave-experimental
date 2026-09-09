"""Layer 2: pure, many-to-one shape-tag migration for workflow-family artifacts.

Backlog: ADR-AUM-001 (two-layer auto-update migrations), Decision 2. Layer 1
(``artifact_versioning.py``) upcasts a REGISTERED type via an integer
``schema-version`` chain, one v(n) -> v(n+1) step at a time. That carrier
cannot express this repo's real legacy shift: several distinct legacy shape
tags (``"v4"``, ``"v4-revised"``) collapse onto ONE target tag (``"v5"``) --
a many-to-one map an integer chain has no way to represent. Layer 2 is this
second, symmetric, pure domain module: keyed by a named shape tag instead of
an integer, same discipline as ``ArtifactVersioningKernel`` otherwise (no
I/O, no module-level mutable registry, pure ``dict -> dict`` per map).

Observable law: for every registered ``(from_tag, to_tag)`` pair,
``apply_workflow_migration`` is a pure ``dict -> dict`` returning a doc whose
declared tag equals ``to_tag``. A tag with no registered forward map is
refused LOUD via ``WorkflowShapeUnmappable`` -- never silently left in the
old shape, never silently guessed into the new one (GDP-6).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


__all__ = [
    "WorkflowMigrationMap",
    "WorkflowMigrationOutcome",
    "WorkflowShapeUnmappable",
    "apply_workflow_migration",
]

#: A pure tag-shape transform. Never mutates its input.
_Transform = Callable[[dict[str, Any]], dict[str, Any]]


class WorkflowMigrationOutcome(str, Enum):
    """The three, and only three, outcomes Layer 2 classification can reach.

    No fourth "guessed" state is constructible (ADR-AUM-001 Decision 4 /
    obligation INVALID_STATE): a workflow artifact is either not yet
    inspected (``PENDING``), successfully reshaped onto the target tag
    (``MIGRATED``), or has no registered path and is refused rather than
    guessed (``INDETERMINATE``).
    """

    PENDING = "Pending"
    MIGRATED = "Migrated"
    INDETERMINATE = "Indeterminate"


class WorkflowShapeUnmappable(Exception):
    """A doc's declared shape tag has no registered forward map.

    Raised by ``apply_workflow_migration`` -- never silently swallowed into a
    returned sentinel, never a bare ``KeyError`` leaking out of an unguarded
    dict lookup (ADR-AUM-001 Four-layer failure laws table, Domain row).
    """

    def __init__(self, tag: object, to_tag: str, registered: tuple[str, ...]) -> None:
        self.tag = tag
        self.to_tag = to_tag
        super().__init__(
            f"WHAT: a workflow artifact declares shape tag {tag!r}, which has "
            f"no registered forward map toward {to_tag!r}. "
            "WHY: apply_workflow_migration only transforms tags a "
            f"WorkflowMigrationMap explicitly registers -- the known forward "
            f"tags for this map are {registered!r}. "
            "HOW: register a forward map for this tag in the owning "
            "WorkflowMigrationMap, or leave the artifact unmigrated and "
            "report it Indeterminate rather than guessing its shape."
        )

    def with_details(self, details: str) -> WorkflowShapeUnmappable:
        """Attach field evidence while retaining the WHAT/WHY/HOW diagnosis."""
        self.args = (f"{self.args[0]} DETAIL: {details}.",)
        return self


@dataclass(frozen=True)
class WorkflowMigrationMap:
    """A many-to-one shape-tag migration: several legacy tags collapse onto one target.

    ``to_tag`` is the single target shape tag. ``forward`` maps each
    registered source tag to the pure ``dict -> dict`` transform reshaping a
    doc from that tag's shape into ``to_tag``'s shape. Build one instance at
    the driven-adapter call site that owns a family's registrations --
    mirrors ``ArtifactVersioningKernel``, no I/O, no globals.
    """

    to_tag: str
    forward: Mapping[str, _Transform] = field(default_factory=dict)
    legacy_fields: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    required_fields: tuple[str, ...] = ()

    def can_migrate(self, tag: object) -> bool:
        """Whether ``tag`` has a registered forward transform toward ``to_tag``."""
        return isinstance(tag, str) and tag in self.forward


def apply_workflow_migration(
    doc: Mapping[str, Any], tag: object, migration_map: WorkflowMigrationMap
) -> dict[str, Any]:
    """Pure ``dict -> dict``: reshape ``doc`` (declared shape ``tag``) to ``migration_map.to_tag``.

    Never mutates ``doc``. Raises ``WorkflowShapeUnmappable`` for a tag with
    no registered forward transform.
    """
    if tag == migration_map.to_tag:
        return dict(doc)
    if not migration_map.can_migrate(tag):
        raise WorkflowShapeUnmappable(
            tag, migration_map.to_tag, tuple(migration_map.forward)
        )
    source_fields = set(doc)
    mapped_fields = set(migration_map.legacy_fields)
    invalid_names = [
        name for name in mapped_fields if not isinstance(name, str) or not name
    ]
    if invalid_names:
        raise WorkflowShapeUnmappable(
            tag, migration_map.to_tag, tuple(migration_map.forward)
        ).with_details(
            f"legacy-field map contains empty or invalid names {invalid_names!r}"
        )
    missing = sorted(set(migration_map.required_fields) - source_fields)
    unknown = sorted(source_fields - mapped_fields)
    if missing or unknown or not migration_map.legacy_fields:
        details = []
        if missing:
            details.append(f"missing required source fields {missing!r}")
        if unknown:
            details.append(f"unknown legacy fields {unknown!r}")
        if not migration_map.legacy_fields:
            details.append("the installed legacy-field map is empty")
        raise WorkflowShapeUnmappable(
            tag,
            migration_map.to_tag,
            tuple(migration_map.forward),
        ).with_details("; ".join(details))
    transform = migration_map.forward[tag]  # type: ignore[index]
    result = transform(dict(doc))
    for field_name, disposition in migration_map.legacy_fields.items():
        if field_name not in result:
            continue
        if not isinstance(disposition, Mapping):
            raise WorkflowShapeUnmappable(
                tag, migration_map.to_tag, tuple(migration_map.forward)
            ).with_details(f"field {field_name!r} has no valid disposition")
        kind = disposition.get("disposition")
        destination = disposition.get("destination")
        if kind == "transform" and not isinstance(disposition.get("rule"), str):
            raise WorkflowShapeUnmappable(
                tag, migration_map.to_tag, tuple(migration_map.forward)
            ).with_details(f"field {field_name!r} has no named transform rule")
        if kind in {"copy", "transform"}:
            if not isinstance(destination, str) or not destination:
                raise WorkflowShapeUnmappable(
                    tag, migration_map.to_tag, tuple(migration_map.forward)
                ).with_details(f"field {field_name!r} has no named destination")
            if destination != field_name:
                result[destination] = result[field_name]
        elif kind == "retire":
            if not isinstance(destination, str) or not destination:
                raise WorkflowShapeUnmappable(
                    tag, migration_map.to_tag, tuple(migration_map.forward)
                ).with_details(
                    f"retired field {field_name!r} has no preservation destination"
                )
            result[destination] = result[field_name]
            if destination != field_name:
                del result[field_name]
        else:
            raise WorkflowShapeUnmappable(
                tag, migration_map.to_tag, tuple(migration_map.forward)
            ).with_details(f"field {field_name!r} has unknown disposition {kind!r}")
    result["tag"] = migration_map.to_tag
    return result
