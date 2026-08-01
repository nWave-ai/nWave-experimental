"""Domain types for the evidence-locus-and-absence-detection slice-01 ATs.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed dataclass/enum/NewType. Step bodies and the composition service
consume these typed parameters -- no raw ``str`` where a domain type exists.

Bounded context: the ``des verify-examine-attestation`` detector's slice-01
walking-skeleton scope -- DESIGN Decisions Table Revision 1's
``UNATTESTED``-with-``join_confidence:heuristic`` branch, the non-vacuity
control (every committed slice's bare id present somewhere in the ledger), and
the WD-2 directory-write-blindness guard. slice-02's COULD_NOT_VERIFY /
INDETERMINATE / EmptyLedgerAmbiguous branches are OUT of this slice's scope
(feature-delta.md ``Design -> Slice Mapping``) and are deliberately absent here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType


#: A kebab-case slice identifier as carried by a ``Slice-Id:`` commit trailer
#: (e.g. ``"slice-07"``). Bare -- never feature-qualified (slice-03 adds the
#: sibling ``Feature-Id:`` trailer; out of this slice's scope).
SliceId = NewType("SliceId", str)

#: A kebab-case feature identifier as carried in an examine-ledger record.
FeatureId = NewType("FeatureId", str)

#: A git commit SHA (full hex, as ``git log --format=%H`` emits it).
CommitSha = NewType("CommitSha", str)

#: A strict ISO-8601 authored-date string, the exact ``%aI`` git format the
#: NEW ``CommitDateReadPort`` (DESIGN D-1) reads back.
IsoDate = NewType("IsoDate", str)


@dataclass(frozen=True)
class UnattestedCommit:
    """One committed slice the detector must NAME as evidence-unreachable.

    Carries the ``Slice-Id:`` trailer this commit stamps and the authored date
    the classifier compares against ``mechanism_active_since`` (DESIGN D-2
    Revision 1). The commit's own ``sha`` is filled in by the composition once
    the synthetic commit is made (unknown at Given-time).
    """

    slice_id: SliceId
    authored_date: IsoDate
    sha: CommitSha | None = None


@dataclass(frozen=True)
class LedgerFillerRecord:
    """A well-formed examine-ledger record seeded into the fixture ledger.

    Used either as UNRELATED filler (so the ledger scan never reads zero
    records -- avoiding the slice-02-scoped ``EmptyLedgerAmbiguous`` refusal,
    DESIGN Revision 1 answer 3) or as a MATCHING record for the non-vacuity
    control (its bare ``slice_id`` matches a test commit's, proving the
    detector does not scream on genuinely-reachable evidence).
    """

    feature_id: FeatureId
    slice_id: SliceId
    timestamp: IsoDate


@dataclass(frozen=True)
class EvidenceLocusObservable:
    """The user-observable surface of one ``des verify-examine-attestation`` run.

    Parsed from the CLI's captured stdout/stderr + exit code -- never from an
    internal struct. ``unattested_slice_ids`` / ``unattested_count`` /
    ``oldest_unattested_date`` are ``None`` when no parseable report line named
    them (the RED-at-HEAD case: the CLI does not exist yet, so nothing is
    parseable and every Then fails with a semantic ``AssertionError``).
    """

    exit_code: int
    stdout: str
    stderr: str
    unattested_slice_ids: tuple[str, ...]
    unattested_shas: tuple[str, ...]
    unattested_count: int | None
    oldest_unattested_date: str | None


#: The examine-ledger family directory-relative glob the detector scans
#: (DESIGN D-4 / ``telemetry_paths.py``). Used by the WD-2 negative scenario to
#: touch an unrelated file that is NOT a valid ``*.jsonl`` ledger record.
EXAMINE_LEDGER_RELATIVE_DIR = (".nwave", "telemetry", "examine")
