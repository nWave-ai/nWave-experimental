"""Explicit document ownership; scope cannot be inferred from a missing id."""

from dataclasses import dataclass
from typing import TypeAlias

from des.domain.feature_documents import require_feature_id


@dataclass(frozen=True)
class Project:
    pass


@dataclass(frozen=True)
class Epic:
    epic_id: str

    def __post_init__(self):
        require_feature_id(self.epic_id)


@dataclass(frozen=True)
class Feature:
    feature_id: str

    def __post_init__(self):
        require_feature_id(self.feature_id)


@dataclass(frozen=True)
class Slice:
    feature_id: str
    slice_id: str

    def __post_init__(self):
        require_feature_id(self.feature_id)
        require_feature_id(self.slice_id)


DocumentScope: TypeAlias = Project | Epic | Feature | Slice


def scope_json(scope: DocumentScope) -> dict:
    match scope:
        case Project():
            return {"kind": "project"}
        case Epic(epic_id):
            return {"kind": "epic", "epic_id": epic_id}
        case Feature(feature_id):
            return {"kind": "feature", "feature_id": feature_id}
        case Slice(feature_id, slice_id):
            return {"kind": "slice", "feature_id": feature_id, "slice_id": slice_id}
        case _:
            raise ValueError("an explicit document scope is required")


def parse_scope(value: object) -> DocumentScope:
    if not isinstance(value, dict):
        raise ValueError("scope must be an object")
    match value:
        case {"kind": "project"} if len(value) == 1:
            return Project()
        case {"kind": "epic", "epic_id": identity} if len(value) == 2:
            return Epic(identity)
        case {"kind": "feature", "feature_id": identity} if len(value) == 2:
            return Feature(identity)
        case {"kind": "slice", "feature_id": feature, "slice_id": identity} if (
            len(value) == 3
        ):
            return Slice(feature, identity)
    raise ValueError(
        "scope must be Project, Epic(id), Feature(id), or Slice(feature_id, slice_id)"
    )


def legacy_scope(value: DocumentScope | str | None) -> DocumentScope:
    """Adapter for historical internal feature-id carriers only."""
    if value is None:
        return Project()
    if isinstance(value, str):
        return Feature(value)
    scope_json(value)
    return value
