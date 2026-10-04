"""Discover, classify, and plan supported ``des update`` migrations.

Dry-run classifies without writing. Apply validates the complete discovered
batch before persistence and preserves completed workflow history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from des.domain.artifact_versioning import (
    ArtifactFromFutureRuntime,
    ArtifactVersioningKernel,
    read_version,
)
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
    """A non-negative, non-bool int suitable for the kernel's chain index."""
    return isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0


def _is_global_config(root: Path, path: Path) -> bool:
    return path == root / ".nwave" / "config.json"


def _is_expectation_charter(root: Path, path: Path) -> bool:
    return path.parent == root / ".nwave" / "expectation-charters"


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
    """Owns discovery, validation, and persistence for registered families."""

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

        A registered type from a future runtime refuses with its path.
        """
        classifications = tuple(
            self._classify(root, path) for path in self._discover(root)
        )
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
            doc = self._read_document(path)
            if _is_expectation_charter(root, path):
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
                except WorkflowTransitionCatalogError as exc:
                    raise WorkflowTransitionCatalogError(
                        f"artifact {path}: {exc}"
                    ) from exc
                except WorkflowShapeUnmappable as exc:
                    raise exc.with_details(f"path {path}") from exc
                if migrated != doc:
                    replacements.append((path, migrated))
                continue
            if _is_global_config(root, path):
                raw_version = doc.get("schema-version", _MISSING)
                if raw_version is not _MISSING and not _is_kernel_int(raw_version):
                    self._refuse(path, "schema-version is not a non-negative integer")
                migrated = self._upcast_global_config(path, doc)
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
                path, "schema-version is not a non-negative integer"
            )

    def _read_document(self, path: Path) -> dict[str, Any]:
        try:
            doc = self._filesystem.read_json(path)
        except (json.JSONDecodeError, UnicodeError, OSError) as exc:
            self._refuse(path, f"JSON input cannot be read or parsed: {exc}")
        if not isinstance(doc, dict):
            self._refuse(
                path,
                f"JSON input must be an object; found {type(doc).__name__}",
            )
        return doc

    @staticmethod
    def _upcast_global_config(path: Path, doc: dict[str, Any]) -> dict[str, Any]:
        try:
            return _GLOBAL_CONFIG_KERNEL.upcast_to_current(
                doc, _GLOBAL_CONFIG_ARTIFACT_TYPE
            )
        except ArtifactFromFutureRuntime as exc:
            raise ValueError(f"artifact {path}: {exc}") from exc

    @staticmethod
    def _refuse(path: Path, reason: str) -> None:
        raise WorkflowShapeUnmappable(path, "current", (reason,))

    def _discover(self, root: Path) -> list[Path]:
        nwave_dir = root / ".nwave"
        if not nwave_dir.is_dir():
            return []
        return sorted(path for path in nwave_dir.rglob("*.json") if path.is_file())

    def _classify(self, root: Path, path: Path) -> ArtifactClassification:
        doc = self._read_document(path)
        raw_version = doc.get("schema-version", _MISSING)
        kernel_readable = raw_version is _MISSING or _is_kernel_int(raw_version)
        declared_display = "<absent>" if raw_version is _MISSING else repr(raw_version)

        if _is_global_config(root, path):
            return self._classify_global_config(
                path, doc, kernel_readable, declared_display
            )
        if _is_expectation_charter(root, path):
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
        raw_version = doc.get("schema-version", _MISSING)
        if (
            isinstance(raw_version, int)
            and not isinstance(raw_version, bool)
            and raw_version < 0
        ):
            self._refuse(
                path, "schema-version is negative; a non-negative integer is required"
            )
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
        # Keep a future-version refusal attached to the artifact path.
        self._upcast_global_config(path, doc)
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
        route_error: str | None = None
        try:
            route = (
                self._workflow_transition_catalog.route_from(tag)
                if self._workflow_transition_catalog is not None
                else None
            )
        except WorkflowTransitionCatalogError as exc:
            route = None
            route_error = str(exc)
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
            reason = route_error or (
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
