"""``des update`` -- discover + classify persisted artifacts (ADR-AUM-001, G2 slice 1).

``--dry-run`` reports, for every artifact discovered under
``<root>/.nwave``: path, declared version verbatim (un-coerced), whether the
versioning kernel can read that version, status (InFlight / Completed /
Indeterminate) and planned action (Upcast / PreserveHistory / Indeterminate)
with a reason. It writes nothing at all (obligation 6).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.adapters.driven.filesystem.real_filesystem import RealFileSystem
from des.application.auto_update_migration_service import (
    AutoUpdateMigrationService,
    DryRunPlan,
)
from des.domain.artifact_versioning import ArtifactFromFutureRuntime
from des.domain.workflow_format_migration import (
    WorkflowMigrationMap,
    WorkflowShapeUnmappable,
)
from des.domain.workflow_transition_catalog import (
    WorkflowTransitionCatalog,
    WorkflowTransitionCatalogError,
)
from des.runtime.packaged_asset import resolve_packaged_asset


_WORKFLOW_MIGRATION_ASSET = "nWave/data/workflow-format-migrations"


def _build_phase_transform(phase_map: dict[str, str]):
    def _transform(doc: dict) -> dict:
        result = dict(doc)
        phase = result.get("phase")
        if isinstance(phase, str) and phase in phase_map:
            result["phase"] = phase_map[phase]
        return result

    return _transform


def _load_workflow_transition_catalog() -> WorkflowTransitionCatalog | None:
    """Load immutable per-file transitions from the packaged catalog directory."""
    resolution = resolve_packaged_asset(_WORKFLOW_MIGRATION_ASSET)
    if not resolution.is_usable or resolution.path is None:
        return None
    if not resolution.path.is_dir():
        return WorkflowTransitionCatalog((), "the packaged asset is not a directory")
    transitions: list[WorkflowMigrationMap] = []
    try:
        entries = sorted(resolution.path.glob("*.json"))
        for entry in entries:
            raw = json.loads(entry.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return WorkflowTransitionCatalog(
                    (), f"malformed transition {entry.name!r}"
                )
            to_tag = raw.get("to-tag")
            from_tags = raw.get("from-tags")
            phase_map = raw.get("phase-map", {})
            legacy_fields = raw.get("legacy-field-map", raw.get("field-map"))
            required_fields = raw.get("required-fields", [])
            if not isinstance(phase_map, dict):
                return WorkflowTransitionCatalog(
                    (),
                    f"malformed transition {entry.name!r}: phase-map must be an object",
                )
            if not all(
                isinstance(source, str)
                and source
                and isinstance(target, str)
                and target
                for source, target in phase_map.items()
            ):
                return WorkflowTransitionCatalog(
                    (),
                    f"malformed transition {entry.name!r}: phase-map must map non-empty strings",
                )
            if (
                not isinstance(to_tag, str)
                or not isinstance(from_tags, list)
                or not from_tags
                or not all(isinstance(tag, str) and tag for tag in from_tags)
                or not isinstance(legacy_fields, dict)
                or not isinstance(required_fields, list)
                or not all(
                    isinstance(field, str) and field for field in required_fields
                )
            ):
                return WorkflowTransitionCatalog(
                    (), f"malformed transition {entry.name!r}"
                )
            # Preserve source multiplicity until it has been rejected.  A
            # dict comprehension would otherwise silently collapse duplicate
            # entries in one JSON transition before the catalog can enforce
            # its unique-source topology rule.
            if len(set(from_tags)) != len(from_tags):
                return WorkflowTransitionCatalog(
                    (), f"duplicate source tag in transition {entry.name!r}"
                )
            transform = _build_phase_transform(phase_map)
            transitions.append(
                WorkflowMigrationMap(
                    to_tag=to_tag,
                    forward={
                        tag: transform for tag in from_tags if isinstance(tag, str)
                    },
                    legacy_fields=legacy_fields,
                    required_fields=tuple(required_fields),
                )
            )
    except (OSError, json.JSONDecodeError, TypeError, AttributeError) as exc:
        return WorkflowTransitionCatalog((), f"malformed transition data: {exc}")
    return WorkflowTransitionCatalog(tuple(transitions))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des update",
        description=(
            "des update -- discover + classify persisted nWave artifacts "
            "before migration"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discovery + classification only; writes nothing (the default).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Validate and persist eligible migrations with a recoverable backup.",
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Repository/user root to scan for .nwave/ artifacts.",
    )
    return parser.parse_args(argv)


def _render(plan: DryRunPlan) -> None:
    print("path\tversion\tkernel-readable\tstatus\taction\treason")
    for row in plan.classifications:
        print(
            f"{row.path}\t"
            f"version={row.declared_version_display}\t"
            f"kernel-readable={'yes' if row.kernel_readable else 'no'}\t"
            f"status={row.status}\t"
            f"action={row.planned_action}\t"
            f"reason={row.reason}"
        )


def _render_apply(paths: tuple[Path, ...]) -> None:
    for path in paths:
        print(f"migrated\t{path}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = Path(args.root)
    filesystem = RealFileSystem()
    workflow_transition_catalog = _load_workflow_transition_catalog()
    service = AutoUpdateMigrationService(
        filesystem, workflow_transition_catalog=workflow_transition_catalog
    )
    try:
        if args.apply:
            _render_apply(service.apply(root))
            return 0
        plan = service.dry_run(root)
    except (
        ArtifactFromFutureRuntime,
        WorkflowShapeUnmappable,
        WorkflowTransitionCatalogError,
        OSError,
        ValueError,
        TypeError,
        AttributeError,
    ) as exc:
        if isinstance(exc, (ArtifactFromFutureRuntime, WorkflowShapeUnmappable)):
            message = str(exc)
        else:
            message = (
                f"WHAT: des update could not process the discovered artifact batch. "
                f"WHY: {exc}. "
                "HOW: repair the artifact or filesystem and retry; no guessed "
                "migration is reported as successful."
            )
        print(message, file=sys.stderr)
        return 1
    _render(plan)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
