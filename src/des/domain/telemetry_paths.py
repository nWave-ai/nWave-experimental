"""The one place that decides where a telemetry ledger lives.

Six resolvers used to answer this question independently -- one per CLI that
happened to need it -- and the `atdd-pure` family alone was spelled out at
fifteen call sites. Nothing was wrong at any single site; what was missing was
somewhere that answered for the shape of the whole. Move the root, rename a
family, or change the per-feature file convention, and you had to find every
copy: the change was cheap and finding it was not.

This module is pure: it computes paths and touches no filesystem, so it may sit
in the domain layer and be imported by application, ports and adapters alike
without inverting the declared dependency direction.

The families are an ENUM rather than free strings on purpose. A caller that
passes an unknown family gets a refusal naming what exists, instead of silently
constructing a path under a directory nobody writes -- which reads, downstream,
as "this feature has no evidence".
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "TELEMETRY_ROOT_PARTS",
    "LedgerFamily",
    "TelemetrySubtree",
    "ledger_dir",
    "ledger_path",
    "subtree_dir",
    "telemetry_root",
]

#: Repo-relative parts of the telemetry root. Kept as parts, not a string, so a
#: caller never has to know the separator, and so `telemetry_root` is the only
#: place that joins them.
TELEMETRY_ROOT_PARTS: tuple[str, ...] = (".nwave", "telemetry")


class LedgerFamily(str, Enum):
    """The append-only JSONL ledger families.

    `str` mixin so an existing call site that formats the value keeps working
    byte-identically during the migration -- the point of a prefactoring is that
    behaviour does not move while the shape does.

    `RED_GREEN` and `FEATURE_END` used to sit here and were removed, because
    they were worse than unused. Measured: zero attribute reads and zero
    value-lookups anywhere in the tree, and the directories they named do not
    hold ledgers at all -- `red-green/` is a last-write-wins cache of JSON
    files and `feature-end/` is raw third-party JUnit XML. A member routing to
    `red-green/{key}.jsonl` therefore promised an append-only ledger over a
    substrate of a different category, and the empty result read downstream as
    "this feature produced no evidence" rather than "you asked the wrong
    question". Do not re-add a family for a directory whose contents are not
    append-only JSONL records.

    `CONTEXT` and `MIKADO` have no writer in this module's own commit; the
    nodes that write them follow immediately. They are declared here, and not
    alongside their writers, so those nodes extend a base whose dead members
    are already gone -- which is the whole point of doing the removal first.
    The distinction from the two removed members is the substrate, not the
    write count: these two name directories that will hold append-only JSONL
    and nothing else, so an empty read is honestly "no records yet".
    """

    ATDD_PURE = "atdd-pure"
    EXAMINE = "examine"
    REVIEW = "review"
    CONTEXT = "context"
    MIKADO = "mikado"


class TelemetrySubtree(str, Enum):
    """Non-ledger directories under the telemetry root.

    These are NOT `LedgerFamily` members on purpose -- see that enum's own
    docstring for why `RED_GREEN` and `FEATURE_END` were removed from it. The
    telemetry ROOT decision (one place decides `.nwave/telemetry/...`) still
    applies to both of these directories; only the ledger-filename convention
    (`<family>/{key}.jsonl`) does not, because neither substrate is an
    append-only JSONL ledger: `red-green/` is a last-write-wins cache of JSON
    seal files, `feature-end/` holds raw third-party JUnit XML. A caller that
    needs one of these directories asks for it directly, rather than reaching
    for `LedgerFamily` and getting a `.jsonl`-shaped promise the substrate
    does not keep.
    """

    RED_GREEN = "red-green"
    FEATURE_END = "feature-end"


def telemetry_root(repo: Path) -> Path:
    """The telemetry root under ``repo``. The ONLY place these parts are joined."""
    return repo.joinpath(*TELEMETRY_ROOT_PARTS)


def ledger_dir(repo: Path, family: LedgerFamily) -> Path:
    """The family DIRECTORY under the telemetry root, with no filename.

    Serves the callers that hold a directory rather than one partition's
    ledger file -- listing a family's ledgers, or building a filename the
    caller does not source from ``partition_key`` directly.

    Raises TypeError on a family that is not a `LedgerFamily`, naming the
    accepted set -- the same contract `ledger_path` raises, because the two
    functions share the same failure mode (an unrecognised family would
    resolve to a directory nothing writes).
    """
    if not isinstance(family, LedgerFamily):
        accepted = ", ".join(sorted(member.value for member in LedgerFamily))
        raise TypeError(
            f"WHAT: ledger_dir was given family {family!r}, which is not a "
            "LedgerFamily. "
            "WHY: an unrecognised family would build a path under a directory "
            "nothing writes, and an empty ledger reads downstream as 'this "
            "feature produced no evidence' rather than as a caller mistake. "
            f"HOW: pass one of LedgerFamily -- accepted values: {accepted}."
        )
    return telemetry_root(repo) / family.value


def subtree_dir(repo: Path, subtree: TelemetrySubtree) -> Path:
    """The non-ledger telemetry subtree directory, with no filename appended.

    Raises TypeError on a value that is not a `TelemetrySubtree`, naming the
    accepted set -- the same fail-loud contract `ledger_dir` and `ledger_path`
    raise for `LedgerFamily`.
    """
    if not isinstance(subtree, TelemetrySubtree):
        accepted = ", ".join(sorted(member.value for member in TelemetrySubtree))
        raise TypeError(
            f"WHAT: subtree_dir was given subtree {subtree!r}, which is not a "
            "TelemetrySubtree. "
            "WHY: an unrecognised subtree would build a path under a "
            "directory nothing writes. "
            f"HOW: pass one of TelemetrySubtree -- accepted values: {accepted}."
        )
    return telemetry_root(repo) / subtree.value


def ledger_path(repo: Path, family: LedgerFamily, partition_key: str) -> Path:
    """The per-partition ledger file for ``family``.

    ``partition_key`` is whatever identifies one ledger within the family. For
    every family that exists today that is a feature id, which is why the
    parameter used to be called ``feature_id``; it is named for the role and
    not for one family's current filler because families are coming whose
    ledgers are scoped to a session rather than a feature, and a session id
    passed to a parameter called ``feature_id`` would assert an ownership that
    is not true. Behaviour is unchanged: the rename is safe because all three
    call sites in the tree pass this argument positionally.

    Composed from `ledger_dir` so there is one join, not two -- raises the
    same TypeError `ledger_dir` raises on an unrecognised family.
    """
    return ledger_dir(repo, family) / f"{partition_key}.jsonl"
