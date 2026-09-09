"""Application orchestration for ``des update`` (ADR-AUM-001, G2 slice 1).

Discovery + classification only (``--dry-run``, obligation 6): for every
artifact found under ``<root>/.nwave``, classify it without ever writing.
Layer 1 (``ArtifactVersioningKernel.upcast_to_current``, reused unmodified
per Decision 1) runs only for a REGISTERED integer-versioned type
(``global-config`` in this slice); Layer 2
(``workflow_format_migration.WorkflowMigrationMap``) is consulted only to
check whether a declared shape ``tag`` is a registered legacy tag -- this
slice never calls ``apply_workflow_migration`` itself, since dry-run never
transforms anything. Completed artifacts are never touched (Decision 6): the
artifact's own declared terminal-phase field short-circuits classification
before either layer is consulted, so an unmappable tag on a Completed
artifact can never raise.

Artifact content is read through the injected ``FileSystemPort`` (Decision
5, no new port) -- ``write_json`` is never called anywhere in this module,
which is the structural proof of the zero-writes law obligation 6 requires.
Directory discovery walks the filesystem directly: no port method exposes
listing, and Decision 5 forbids adding one for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from des.domain.artifact_versioning import ArtifactVersioningKernel, read_version
from des.domain.workflow_format_migration import (
    WorkflowShapeUnmappable,
    apply_workflow_migration,
)
from des.domain.workflow_transition_catalog import WorkflowTransitionCatalogError


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.workflow_transition_catalog import WorkflowTransitionCatalog
    from des.ports.driven_ports.filesystem_port import FileSystemPort


_MISSING = object()

# Mirrors the ALREADY-LANDED consumer (des_config.py:_GLOBAL_CONFIG_VERSIONING):
# one identity v0->v1 upcaster, current version 1. A second kernel instance
# here (rather than importing the private module-level one) keeps this
# service's own registrations self-contained, same discipline
# ArtifactVersioningKernel's docstring recommends (one instance per owning
# call site).
_GLOBAL_CONFIG_ARTIFACT_TYPE = "global-config"


def _global_config_v0_to_v1(doc: dict[str, Any]) -> dict[str, Any]:
    """v0 (no schema-version key) -> v1. Identity: v1 only introduces the key."""
    return dict(doc)


_GLOBAL_CONFIG_KERNEL = ArtifactVersioningKernel(
    upcasters={_GLOBAL_CONFIG_ARTIFACT_TYPE: (_global_config_v0_to_v1,)}
)


def _is_kernel_int(raw: Any) -> bool:
    """A well-typed, non-bool int -- the only shape the kernel reads as a version."""
    return isinstance(raw, int) and not isinstance(raw, bool)


def _is_global_config(path: Path) -> bool:
    return path.name == "config.json" and path.parent.name == ".nwave"


def _is_expectation_charter(path: Path) -> bool:
    return path.parent.name == "expectation-charters"


@dataclass(frozen=True)
class ArtifactClassification:
    """One discovered artifact's discovery+classification row (obligation 6)."""

    path: Path
    declared_version_display: str
    kernel_readable: bool
    status: str
    planned_action: str
    reason: str


@dataclass(frozen=True)
class DryRunPlan:
    """Zero-write plan: every discovered artifact, classified. Never mutates.

    The Plan-value pattern (dry_run/preview functions return a value, never
    a side effect) makes "preview wrote to disk" structurally impossible to
    observe from this type alone.
    """

    classifications: tuple[ArtifactClassification, ...]


@dataclass(frozen=True)
class ApplyPlan:
    """Validated replacements; constructing this value performs no writes."""

    replacements: tuple[tuple[Path, dict[str, Any]], ...]


class AutoUpdateMigrationService:
    """Discovers persisted artifacts under a root and classifies them (dry-run only)."""

    def __init__(
        self,
        filesystem: FileSystemPort,
        *,
        workflow_transition_catalog: WorkflowTransitionCatalog | None = None,
    ) -> None:
        self._filesystem = filesystem
        self._workflow_transition_catalog = workflow_transition_catalog

    def dry_run(self, root: Path) -> DryRunPlan:
        """Discover + classify every artifact under ``root/.nwave``. Never writes.

        Propagates ``ArtifactFromFutureRuntime`` unchanged when a registered
        type's declared version exceeds this runtime's known current version
        (Decision 4c) -- never swallowed into a generic Indeterminate row.
        """
        classifications = tuple(self._classify(path) for path in self._discover(root))
        return DryRunPlan(classifications=classifications)

    def apply(self, root: Path) -> tuple[Path, ...]:
        """Validate the complete batch, then snapshot-and-replace its members."""
        plan = self._plan_apply(root)
        replaced: list[Path] = []
        for path, data in plan.replacements:
            self._filesystem.snapshot_and_replace(path, data)
            replaced.append(path)
        return tuple(replaced)

    def _plan_apply(self, root: Path) -> ApplyPlan:
        if not (root / ".nwave").is_dir():
            self._refuse(root, "the update root has no readable .nwave directory")
        replacements: list[tuple[Path, dict[str, Any]]] = []
        for path in self._discover(root):
            doc = self._filesystem.read_json(path)
            if _is_expectation_charter(path):
                if doc.get("phase") == "COMPLETED":
                    continue
                self._validate_workflow_version(path, doc)
                tag = doc.get("tag")
                if self._workflow_transition_catalog is None:
                    self._refuse(
                        path, "the installed workflow-transition catalog is unavailable"
                    )
                assert self._workflow_transition_catalog is not None
                try:
                    route = self._workflow_transition_catalog.route_from(tag)
                    migrated = dict(doc)
                    current_tag = tag
                    for transition in route:
                        migrated = apply_workflow_migration(
                            migrated, current_tag, transition
                        )
                        current_tag = transition.to_tag
                except WorkflowTransitionCatalogError:
                    raise
                except WorkflowShapeUnmappable as exc:
                    raise exc.with_details(f"path {path}") from exc
                if migrated != doc:
                    replacements.append((path, migrated))
                continue
            if _is_global_config(path):
                raw_version = doc.get("schema-version", _MISSING)
                if raw_version is not _MISSING and not _is_kernel_int(raw_version):
                    self._refuse(path, "schema-version is not a well-typed integer")
                migrated = _GLOBAL_CONFIG_KERNEL.upcast_to_current(
                    doc, _GLOBAL_CONFIG_ARTIFACT_TYPE
                )
                if migrated != doc:
                    replacements.append((path, migrated))
                continue
            self._refuse(path, "the artifact type has no registered migration path")
        return ApplyPlan(replacements=tuple(replacements))

    @staticmethod
    def _validate_workflow_version(path: Path, doc: dict[str, Any]) -> None:
        raw_version = doc.get("schema-version", _MISSING)
        if raw_version is _MISSING:
            AutoUpdateMigrationService._refuse(
                path, "the workflow artifact has no declared schema-version"
            )
        if not _is_kernel_int(raw_version):
            AutoUpdateMigrationService._refuse(
                path, "schema-version is not a well-typed integer"
            )

    @staticmethod
    def _refuse(path: Path, reason: str) -> None:
        raise WorkflowShapeUnmappable(path, "current", (reason,))

    def _discover(self, root: Path) -> list[Path]:
        nwave_dir = root / ".nwave"
        if not nwave_dir.is_dir():
            return []
        return sorted(path for path in nwave_dir.rglob("*.json") if path.is_file())

    def _classify(self, path: Path) -> ArtifactClassification:
        doc = self._filesystem.read_json(path)
        raw_version = doc.get("schema-version", _MISSING)
        kernel_readable = raw_version is _MISSING or _is_kernel_int(raw_version)
        declared_display = "<absent>" if raw_version is _MISSING else repr(raw_version)

        if _is_global_config(path):
            return self._classify_global_config(
                path, doc, kernel_readable, declared_display
            )
        if _is_expectation_charter(path):
            return self._classify_expectation_charter(
                path, doc, kernel_readable, declared_display
            )
        return ArtifactClassification(
            path=path,
            declared_version_display=declared_display,
            kernel_readable=kernel_readable,
            status="Indeterminate",
            planned_action="Indeterminate",
            reason=(
                "artifact type is not registered with any known versioning "
                "family; declared value is reported verbatim, never coerced"
            ),
        )

    def _classify_global_config(
        self,
        path: Path,
        doc: dict[str, Any],
        kernel_readable: bool,
        declared_display: str,
    ) -> ArtifactClassification:
        if not kernel_readable:
            return ArtifactClassification(
                path=path,
                declared_version_display=declared_display,
                kernel_readable=False,
                status="Indeterminate",
                planned_action="Indeterminate",
                reason=(
                    "declared schema-version is present but not a well-typed "
                    "integer; never silently coerced or defaulted"
                ),
            )
        # Propagates ArtifactFromFutureRuntime to the CLI boundary unchanged.
        _GLOBAL_CONFIG_KERNEL.upcast_to_current(doc, _GLOBAL_CONFIG_ARTIFACT_TYPE)
        current = _GLOBAL_CONFIG_KERNEL.current_version(_GLOBAL_CONFIG_ARTIFACT_TYPE)
        declared = read_version(doc)
        needs_upcast = declared < current
        return ArtifactClassification(
            path=path,
            declared_version_display=declared_display,
            kernel_readable=True,
            status="InFlight",
            planned_action="Upcast" if needs_upcast else "PreserveHistory",
            reason=(
                f"registered 'global-config' family, kernel current version "
                f"is {current}"
            ),
        )

    def _classify_expectation_charter(
        self,
        path: Path,
        doc: dict[str, Any],
        kernel_readable: bool,
        declared_display: str,
    ) -> ArtifactClassification:
        # Structural guard (Decision 6): a Completed artifact is classified
        # from its own declared terminal-phase field alone, before either
        # layer is consulted -- an unmappable tag on a Completed artifact
        # can therefore never raise.
        if doc.get("phase") == "COMPLETED":
            return ArtifactClassification(
                path=path,
                declared_version_display=declared_display,
                kernel_readable=kernel_readable,
                status="Completed",
                planned_action="PreserveHistory",
                reason=(
                    "declared terminal-phase is COMPLETED; never touched "
                    "regardless of shape tag (structural guard)"
                ),
            )
        tag = doc.get("tag")
        try:
            route = (
                self._workflow_transition_catalog.route_from(tag)
                if self._workflow_transition_catalog is not None
                else None
            )
        except WorkflowTransitionCatalogError:
            route = None
        if route:
            planned_action = "Upcast"
            reason = (
                f"in flight; shape tag {tag!r} is resolved by the packaged "
                "workflow-transition catalog"
            )
        elif route == ():
            planned_action = "PreserveHistory"
            reason = "in flight; shape tag already equals the catalog terminal"
        else:
            planned_action = "Indeterminate"
            reason = (
                "in flight; no registered migration path for this "
                "artifact's declared shape -- never guessed"
            )
        return ArtifactClassification(
            path=path,
            declared_version_display=declared_display,
            kernel_readable=kernel_readable,
            status="InFlight",
            planned_action=planned_action,
            reason=reason,
        )


__all__ = [
    "ApplyPlan",
    "ArtifactClassification",
    "AutoUpdateMigrationService",
    "DryRunPlan",
]
