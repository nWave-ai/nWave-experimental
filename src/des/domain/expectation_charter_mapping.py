"""Resolve the expectation charter that arms one DELIVER EXAMINE slot.

The dispatcher must not guess whether a C_REVIEWER_AUDIT slot is an EXAMINE
or a legacy technical audit.  This small domain seam owns only the charter
``Spec rows:`` to ``slice-NN`` mapping; prompt wording remains in the CLI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


_SPEC_ROWS_PATTERN = re.compile(r"\bSpec rows:\s*([^\n·]+)", re.IGNORECASE)
_SLICE_ID_PATTERN = re.compile(r"slice-\d+\Z")


class CharterMappingState(str, Enum):
    """The three safe outcomes of resolving one middle-slot charter map."""

    UNARMED = "unarmed"
    UNMAPPED = "unmapped"
    ARMED = "armed"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class CharterMapping:
    """A resolved charter path, or an actionable refusal explanation."""

    state: CharterMappingState
    charter_path: Path | None = None
    detail: str | None = None


def resolve_slice_charter(
    repo_root: Path, feature_id: str, slice_id: str
) -> CharterMapping:
    """Resolve exactly one valid charter for ``slice_id`` without guessing.

    FOUR outcomes, because three of them were once one.  ``UNARMED`` (the
    feature has no charter directory at all -- the practice is not adopted
    here) and ``UNMAPPED`` (the directory EXISTS and other slices are mapped,
    but this one is not) were previously the same value, so the caller could
    not tell "nobody writes charters in this repo" from "charters are written
    here and THIS slice was forgotten".  Only the second is an omission worth
    refusing; collapsing them forces one policy onto both.  ``ARMED`` resolves
    exactly one charter; ``INDETERMINATE`` reports a malformed, unreadable or
    ambiguous mapping for the CLI to refuse LOUD.
    """
    charter_dir = repo_root / "docs" / "product" / "expectations" / feature_id
    if not charter_dir.is_dir():
        return CharterMapping(CharterMappingState.UNARMED)

    matching_paths: list[Path] = []
    # Whether ANY well-formed charter lives here -- the discriminator between
    # "this repo does not write charters" and "it does, and this slice is not
    # in one".  Named because an absence that was never looked for reads the
    # same as one that was.
    practice_adopted = False
    for charter_path in sorted(charter_dir.glob("*.md")):
        try:
            content = charter_path.read_text(encoding="utf-8")
        except OSError as exc:
            return CharterMapping(
                CharterMappingState.INDETERMINATE,
                detail=(
                    f"charter {charter_path} cannot be read ({exc.__class__.__name__})"
                ),
            )

        matches = tuple(_SPEC_ROWS_PATTERN.finditer(content))
        if not matches:
            return CharterMapping(
                CharterMappingState.INDETERMINATE,
                detail=f"charter {charter_path} has no `Spec rows:` mapping",
            )
        if len(matches) != 1:
            return CharterMapping(
                CharterMappingState.INDETERMINATE,
                detail=(
                    f"charter {charter_path} declares {len(matches)} `Spec rows:` "
                    "mappings"
                ),
            )
        match = matches[0]
        mapped_slices = [value.strip() for value in match.group(1).split(",")]
        if not mapped_slices or any(
            not _SLICE_ID_PATTERN.fullmatch(value) for value in mapped_slices
        ):
            return CharterMapping(
                CharterMappingState.INDETERMINATE,
                detail=(
                    f"charter {charter_path} maps `Spec rows:` to "
                    f"{match.group(1)!r}, not comma-separated `slice-NN` values"
                ),
            )
        if slice_id in mapped_slices:
            matching_paths.append(charter_path)
        else:
            practice_adopted = True

    if len(matching_paths) == 1:
        return CharterMapping(CharterMappingState.ARMED, matching_paths[0])
    if len(matching_paths) > 1:
        rendered_paths = ", ".join(str(path) for path in matching_paths)
        return CharterMapping(
            CharterMappingState.INDETERMINATE,
            detail=(
                f"slice {slice_id!r} is mapped by multiple charters: {rendered_paths}"
            ),
        )
    if practice_adopted:
        return CharterMapping(
            CharterMappingState.UNMAPPED,
            detail=(
                f"{charter_dir} carries charters, but none maps slice {slice_id!r}"
            ),
        )
    return CharterMapping(CharterMappingState.UNARMED)
