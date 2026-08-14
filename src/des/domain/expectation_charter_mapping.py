"""Resolve the expectation charter that arms one DELIVER EXAMINE slot.

The dispatcher must not guess whether a C_REVIEWER_AUDIT slot is an EXAMINE
or a legacy technical audit.  This small domain seam owns only the charter
``Spec rows:`` to ``slice-NN`` mapping; prompt wording remains in the CLI.

It also owns the OTHER half of the same question -- not "which charter arms
this slot" but "does this work OWE a charter at all".  That is the
``CharterObligation`` vocabulary plus the pure builder for the
``CharterObligationDeclared`` record ``des dispatch`` appends to the examine
ledger.  The two live together because they are one subject read from two
ends, and because a second module would be a second place to look.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


_SPEC_ROWS_PATTERN = re.compile(r"\bSpec rows:\s*([^\n·]+)", re.IGNORECASE)
_SLICE_ID_PATTERN = re.compile(r"slice-\d+\Z")

#: fix-charter-scaffold-placeholder-scope O3 (feature-delta amendment,
#: 2026-07-30, human-granted forward-only decision): the three `Spec rows:`
#: tokens meaning "deliberately not slice-scoped, feature-level" -- the SAME
#: three producer-owned seed-mode identifiers `charter_scaffold` stamps (O2).
#: A first-class, closed set -- every other non-slice-NN value (`n/a`, `human
#: directive`, ...) keeps refusing `indeterminate` unchanged.
_FEATURE_LEVEL_SCOPE_TOKENS: frozenset[str] = frozenset(
    {"bug-observable", "brownfield-discovery", "direct-value"}
)


def _classify_spec_rows_value(raw_value: str) -> tuple[str, tuple[str, ...]] | None:
    """Classify one charter's raw `Spec rows:` value. Pure.

    Returns `("feature-level", (token,))` when the value is EXACTLY one of
    the two first-class feature-level tokens; `("slice", (id, ...))` when it
    is one or more comma-separated `slice-NN` values; `None` when it is
    neither -- a malformed/unrecognized claim the caller must refuse LOUD.
    """
    stripped = raw_value.strip()
    if stripped in _FEATURE_LEVEL_SCOPE_TOKENS:
        return "feature-level", (stripped,)
    mapped_slices = [value.strip() for value in stripped.split(",")]
    if mapped_slices and all(
        _SLICE_ID_PATTERN.fullmatch(value) for value in mapped_slices
    ):
        return "slice", tuple(mapped_slices)
    return None


class CharterMappingState(str, Enum):
    """The three safe outcomes of resolving one middle-slot charter map."""

    UNARMED = "unarmed"
    UNMAPPED = "unmapped"
    ARMED = "armed"
    INDETERMINATE = "indeterminate"


class CharterObligation(str, Enum):
    """Whether a piece of work OWES an expectation charter -- THREE values.

    The arity is the point.  ``_examine_gate_armed`` (``commit_slice.py``)
    answers this with a two-valued ``bool``, which collapses "this work was
    DECLARED exempt" and "nobody ever declared anything" into one ``False``.
    That collapse is the silent-wrong: an absence reads as a negative
    declaration.  ``INDETERMINATE`` exists so the third state can be minted at
    declaration time and REACH the aggregate, instead of vanishing into
    pass/empty (GDP-8 arity corollary).

    Never-declared is NOT a member here.  It is the ABSENCE of a record on the
    ledger, and it must never be coerced into a value of this enum.
    """

    REQUIRED = "REQUIRED"
    EXEMPT = "EXEMPT"
    INDETERMINATE = "INDETERMINATE"


#: The record ``des dispatch`` appends to the EXISTING examine ledger, keyed
#: ``(feature_id, slice_id)`` -- the SAME key ``_latest_examine_verdict``
#: already indexes on, so the two records join without a new store, a new
#: reader or a new key.  Named consumers: the ``des commit-slice`` arming
#: resolution and the end-of-feature aggregate.
CHARTER_OBLIGATION_DECLARED_EVENT = "CharterObligationDeclared"

#: The LOUD stderr event when that append fails.  The dispatch's exit code and
#: envelope are UNCHANGED: a telemetry write must never take down the dispatch
#: that is the operator's only way forward (GDP-6 -- degrade LOUD, not
#: degrade-refuse-everything).
CHARTER_OBLIGATION_UNWRITABLE_EVENT = "CharterObligationRecordUnwritable"

#: Mirrors the sibling ``ExamineVerdictRecorded`` record on the same ledger, so
#: a reader can tell which shape it is parsing rather than guessing from keys.
CHARTER_OBLIGATION_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class CharterMapping:
    """A resolved charter path, or an actionable refusal explanation."""

    state: CharterMappingState
    charter_path: Path | None = None
    detail: str | None = None


def charter_obligation_record(
    *,
    feature_id: str,
    slice_id: str,
    obligation: CharterObligation,
    lane: str | None,
    reason: str | None,
    timestamp: str,
) -> dict[str, object]:
    """Build one ``CharterObligationDeclared`` record.  Pure -- no I/O.

    ``lane`` is the ANTECEDENT the obligation was read off, carried because a
    state named without what it was derived FROM hands the reader an
    investigation the producer had already finished (GDP-3 omission
    corollary): an ``EXEMPT`` with no antecedent is a label, not a reason.
    ``reason`` carries an operator's explicit ``--charter-exemption`` text, the
    only case where the lane alone does not explain the value.
    """
    return {
        "event": CHARTER_OBLIGATION_DECLARED_EVENT,
        "schema_version": CHARTER_OBLIGATION_SCHEMA_VERSION,
        "feature_id": feature_id,
        "slice_id": slice_id,
        "obligation": obligation.value,
        "lane": lane,
        "reason": reason,
        "timestamp": timestamp,
    }


def latest_declared_obligation(ledger: Path, slice_id: str) -> dict[str, object] | None:
    """The LATEST ``CharterObligationDeclared`` record for ``slice_id`` on
    ``ledger``, or ``None`` when the slice was NEVER DECLARED.

    Mirrors ``commit_slice._latest_examine_verdict``'s malformed-line
    tolerance (a truncated line from a concurrent writer is skipped, never
    raised) and latest-record-wins semantics, on the SAME
    ``(feature_id, slice_id)``-keyed examine ledger -- a sibling reader of an
    existing record family sharing that ledger and that key, not a new store.

    ``None`` IS the discriminator: it is not a value of ``CharterObligation``
    and must never be coerced into one -- "never declared" is the ABSENCE of
    a record, distinct from any declared value including ``INDETERMINATE``.
    """
    if not ledger.is_file():
        return None
    latest: dict[str, object] | None = None
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("event") != CHARTER_OBLIGATION_DECLARED_EVENT:
            continue
        if record.get("slice_id") != slice_id:
            continue
        latest = record
    return latest


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

    # Two independent match lists, because a feature-level charter (bug-
    # observable / brownfield-discovery) must never OUTRANK a slice-scoped
    # charter that specifically names the queried slice (bugfix fix-at-
    # review-verdict-charter-form, round 2 precedence guard) -- `specific`
    # is checked FIRST and, if non-empty, `feature_level` is never consulted.
    specific_matches: list[Path] = []
    feature_level_matches: list[Path] = []
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
        classification = _classify_spec_rows_value(match.group(1))
        if classification is None:
            return CharterMapping(
                CharterMappingState.INDETERMINATE,
                detail=(
                    f"charter {charter_path} maps `Spec rows:` to "
                    f"{match.group(1)!r}, not comma-separated `slice-NN` values "
                    "nor a first-class feature-level scope token "
                    f"({sorted(_FEATURE_LEVEL_SCOPE_TOKENS)})"
                ),
            )
        kind, mapped_tokens = classification
        practice_adopted = True
        if kind == "slice":
            if slice_id in mapped_tokens:
                specific_matches.append(charter_path)
            continue
        # kind == "feature-level": a charter whose `Spec rows:` is one of
        # the two first-class tokens (`bug-observable` /
        # `brownfield-discovery`, stamped by `charter_scaffold`'s
        # feature-level seed-modes) by construction maps no specific slice.
        # `dispatch.py` (the production caller) queries it BY that same
        # token verbatim (exact-token equality is then the right rule); a
        # real `--slice-id` (e.g. `slice-01`) never equals a feature-level
        # token, so in that case ANY feature-level charter arms it --
        # UNLESS a more specific slice-scoped charter also claims it, which
        # `specific_matches`, checked first below, already guards.
        if slice_id in _FEATURE_LEVEL_SCOPE_TOKENS:
            if slice_id == mapped_tokens[0]:
                feature_level_matches.append(charter_path)
        else:
            feature_level_matches.append(charter_path)

    if len(specific_matches) == 1:
        return CharterMapping(CharterMappingState.ARMED, specific_matches[0])
    if len(specific_matches) > 1:
        rendered_paths = ", ".join(str(path) for path in specific_matches)
        return CharterMapping(
            CharterMappingState.INDETERMINATE,
            detail=(
                f"slice {slice_id!r} is mapped by multiple charters: {rendered_paths}"
            ),
        )
    if len(feature_level_matches) == 1:
        return CharterMapping(CharterMappingState.ARMED, feature_level_matches[0])
    if len(feature_level_matches) > 1:
        rendered_paths = ", ".join(str(path) for path in feature_level_matches)
        return CharterMapping(
            CharterMappingState.INDETERMINATE,
            detail=(
                f"{slice_id!r} is mapped by multiple feature-level charters: "
                f"{rendered_paths}"
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
