"""Canonical, typed projection of one architecture closure.

The closure is deliberately data-only: parsing command arguments and publishing
authority bytes are adapters; this module owns the deterministic semantic value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from des.domain.architecture_brief_resolver import (
    is_repository_relative_whole_file_locator,
)


if TYPE_CHECKING:
    from collections.abc import Mapping


FORMAT = "DesignClosureV1"
_DIGEST_PREFIX = b"nwave-design-projection/v1\0"
START_MARKER = "<!-- GENERATED:design-closure START -->\n"
END_MARKER = "<!-- GENERATED:design-closure END -->\n"
PARADIGMS = frozenset({"functional", "object_oriented"})


@dataclass(frozen=True)
class DesignClosureRegion:
    """One complete, line-delimited DesignClosureV1 carrier in an authority.

    Marker-looking text inside the compact JSON body is semantic data.  Only
    the exact marker tokens on their own lines delimit a generated region.
    """

    start: int
    end: int
    text: str


def _line_marker_offsets(text: str, marker: str) -> tuple[int, ...]:
    """Return exact marker lines, never marker-looking JSON string data."""
    offsets: list[int] = []
    offset = text.find(marker)
    while offset >= 0:
        if offset == 0 or text[offset - 1] == "\n":
            offsets.append(offset)
        offset = text.find(marker, offset + 1)
    return tuple(offsets)


def design_closure_marker_count(text: str) -> int:
    """Count structural DesignClosureV1 markers, excluding semantic payload."""
    return len(_line_marker_offsets(text, START_MARKER)) + len(
        _line_marker_offsets(text, END_MARKER)
    )


def sole_design_closure_region(text: str) -> DesignClosureRegion | None:
    """Return the one complete carrier, or ``None`` for zero/ambiguous state."""
    starts = _line_marker_offsets(text, START_MARKER)
    ends = _line_marker_offsets(text, END_MARKER)
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        return None
    return DesignClosureRegion(
        start=starts[0],
        end=ends[0] + len(END_MARKER),
        text=text[starts[0] : ends[0] + len(END_MARKER)],
    )


def compact_json(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
    )


def design_projection_digest(payload: Mapping[str, Any]) -> str:
    body = compact_json(payload)
    material = _DIGEST_PREFIX + len(body).to_bytes(8, "big") + body
    return "sha256:" + sha256(material).hexdigest()


def is_nonempty_design_closure_payload(value: object) -> bool:
    """The wire carrier admits one nonempty named semantic projection."""
    return isinstance(value, dict) and bool(value)


def is_canonical_repository_path(value: str) -> bool:
    """The repositoryRelativePath schema, not merely a normalised spelling."""
    return isinstance(value, str) and is_repository_relative_whole_file_locator(value)


def _is_authority_locator(value: object) -> bool:
    if not isinstance(value, str):
        return False
    document, separator, anchor = value.partition("#")
    return bool(separator and anchor and is_canonical_repository_path(document))


def _is_nonempty_string_list(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(member, str) and member for member in value
    )


def is_structurally_valid_design_closure_payload(value: object) -> bool:
    """Whether a digest-bound payload inhabits the closed DesignClosureV1 shape.

    A digest proves only byte identity.  Before replacing an already-published
    region, the producer must also reject a digest-valid value that cannot be
    consumed as a DesignClosureV1 semantic projection.
    """
    if not isinstance(value, dict) or set(value) != {
        "authority",
        "obligations",
        "oracle",
        "paradigm",
        "skills",
        "targets",
        "test_dependencies",
        "verification",
    }:
        return False
    if (
        not _is_authority_locator(value["authority"])
        or value["paradigm"] not in PARADIGMS
    ):
        return False
    if not all(
        _is_nonempty_string_list(value[name]) for name in ("obligations", "skills")
    ):
        return False
    dependencies = value["test_dependencies"]
    if not isinstance(dependencies, list) or not all(
        is_canonical_repository_path(dependency) for dependency in dependencies
    ):
        return False
    oracle = value["oracle"]
    if (
        not isinstance(oracle, dict)
        or set(oracle) != {"kind", "locator"}
        or oracle["kind"] not in {"new", "existing"}
        or not is_canonical_repository_path(oracle["locator"])
    ):
        return False
    verification = value["verification"]
    if not isinstance(verification, dict) or verification.get("kind") not in {
        "commands",
        "delegated",
    }:
        return False
    if verification["kind"] == "commands":
        if set(verification) == {"kind", "argvs"}:
            argvs = verification["argvs"]
        elif set(verification) == {"kind", "argv"}:
            # DesignClosureV1 originally carried one command directly.  The
            # reader remains able to validate that already-published shape;
            # new construction always emits the plural, ordered carrier.
            argvs = [verification["argv"]]
        else:
            return False
        if not isinstance(argvs, list) or not argvs:
            return False
        for argv in argvs:
            if not _is_nonempty_string_list(argv) or not is_canonical_repository_path(
                argv[0]
            ):
                return False
    else:
        if set(verification) != {"kind", "literal-script-block"}:
            return False
        block = verification["literal-script-block"]
        if (
            not isinstance(block, dict)
            or set(block) != {"locator", "content-digest", "lines"}
            or not _is_authority_locator(block["locator"])
            or not isinstance(block["content-digest"], str)
            or not block["content-digest"]
            or not _is_nonempty_string_list(block["lines"])
        ):
            return False
    targets = value["targets"]
    if not isinstance(targets, dict) or not targets:
        return False
    for path, target in targets.items():
        if not is_canonical_repository_path(path) or not isinstance(target, dict):
            return False
        if set(target) != {
            "purpose",
            "shape",
            "declared_imports",
            "boundary",
            "decision",
        }:
            return False
        if (
            not isinstance(target["purpose"], str)
            or not target["purpose"]
            or target["shape"]
            not in {"pure-function", "bounded-change", "unbounded-preservation"}
            or not isinstance(target["declared_imports"], list)
            or not all(
                isinstance(imported, str) for imported in target["declared_imports"]
            )
        ):
            return False
        boundary = target["boundary"]
        if (
            not isinstance(boundary, dict)
            or set(boundary)
            != {
                "failure-behavior",
                "substrate-lie",
                "substrate-probe",
                "double-blind-spot",
            }
            or not all(isinstance(text, str) and text for text in boundary.values())
        ):
            return False
        decision = target["decision"]
        if (
            not isinstance(decision, dict)
            or set(decision) != {"variant", "evidence"}
            or decision["variant"] not in {"EXTEND", "CREATE_NEW"}
            or not isinstance(decision["evidence"], list)
            or not decision["evidence"]
        ):
            return False
        if decision["variant"] == "EXTEND":
            if not all(isinstance(item, str) and item for item in decision["evidence"]):
                return False
        elif not all(
            isinstance(item, list)
            and len(item) == 3
            and all(isinstance(member, str) and member for member in item)
            for item in decision["evidence"]
        ):
            return False
    return True


@dataclass(frozen=True)
class DesignClosureV1:
    payload: Mapping[str, Any]

    def envelope(self) -> dict[str, Any]:
        return {
            "design-projection-digest": design_projection_digest(self.payload),
            "format": FORMAT,
            "payload": self.payload,
        }

    def render(self) -> bytes:
        return (
            START_MARKER.encode("utf-8")
            + b"```json\n"
            + compact_json(self.envelope())
            + b"```\n"
            + END_MARKER.encode("utf-8")
        )


def canonical_payload(
    *,
    authority: str,
    paradigm: str,
    oracle: Mapping[str, str],
    verification: Mapping[str, Any],
    targets: Mapping[str, Mapping[str, Any]],
    obligations: list[str],
    skills: list[str],
    test_dependencies: list[str],
) -> dict[str, Any]:
    """Build the unique wire value after boundary validation has succeeded."""
    return {
        "authority": authority,
        "obligations": sorted(obligations),
        "oracle": dict(oracle),
        "paradigm": paradigm,
        "skills": sorted(skills),
        "targets": {path: targets[path] for path in sorted(targets)},
        "test_dependencies": sorted(test_dependencies),
        "verification": dict(verification),
    }
