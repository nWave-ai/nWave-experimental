"""seal_provenance.py -- did a sealed slice's AT file(s) exist at the sha it
attests?

`lane-seal-refuses-premature`, part B of the two-lane
`fix-slice-seal-carries-commit-sha` chain. Part A threaded `commit_sha` into
the `SliceCommitVerified` ledger record -- the join key a later check needs
to answer "did this seal fire before or after its own AT existed?" now
EXISTS. This module IS that later check: the pure application-layer logic,
git-free (AD-21) except through the injected `CommitTreePathPort`.

The historical defect this closes: a `SliceCommitVerified` record for
slice-03 carries timestamp `2026-06-02T07:35:49Z`, while the `.feature` AT
that slice's own naming convention/tag ties it to was authored by a LATER
commit (`08:30` the same day) -- the seal fired 55 minutes before its own
acceptance test existed, and stayed invisible for two months because the
record carried no `commit_sha` to join against.

Three-state contract (GDP-8 -- decide on the PROPERTY, never the
DESIGNATION; the third state reaches the aggregate, never silently drops):

- ``VERIFIED``    -- every AT file `feature_files_for_slice` resolves for
  this slice existed as a blob in `commit_sha`'s tree. An honest seal.
- ``PREMATURE``   -- at least one owned AT file did NOT exist in
  `commit_sha`'s tree -- a proven premature attestation.
- ``INDETERMINATE`` -- the record predates `commit_sha` (no join key at
  all), or no AT file is discoverable for the slice, or git itself could not
  resolve the fact. NEVER collapsed into VERIFIED (a silent pass) or
  PREMATURE (a retroactive fail on missing evidence) -- "I could not tell"
  is its own outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application.slice_at_completeness import feature_files_for_slice
from des.ports.driven_ports.commit_tree_path_port import (
    CommitTreePathPort,
    Indeterminate,
)


if TYPE_CHECKING:
    from pathlib import Path


class SealVerdict(str, Enum):
    """The per-record verdict this audit reaches. See module docstring."""

    VERIFIED = "VERIFIED"
    PREMATURE = "PREMATURE"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class SealProvenanceFinding:
    """One `SliceCommitVerified` record's provenance verdict."""

    slice_id: str
    seq: int
    verdict: SealVerdict
    reason: str
    commit_sha: str | None = None
    checked_paths: tuple[str, ...] = field(default_factory=tuple)


def audit_seal_provenance(
    repo: Path,
    feature_id: str,
    *,
    path_port: CommitTreePathPort,
) -> list[SealProvenanceFinding]:
    """Audit every `SliceCommitVerified` record for `feature_id`.

    Reads the feature's ledger under `AtCompletionLedger`'s fail-closed
    integrity contract (a corrupt ledger raises `LedgerIntegrityViolation`
    rather than silently under-auditing) and returns one finding per record,
    in ledger order (`seq` ascending). An absent ledger yields an empty list
    -- nothing to audit, not an error.
    """
    # Legacy per-feature construction is DELIBERATE, not overlooked debt: the
    # AtCompletionLedger singleton-shape migration (slice-02c-N1..N11,
    # tests/des/unit/test_caller_migration_cascade_detector.py) is in flight,
    # and every REAL `SliceCommitVerified` record recorded so far -- the very
    # data this audit exists to check -- lives in the legacy per-feature
    # ledger (`.nwave/telemetry/atdd-pure/{feature_id}.jsonl`), not yet in
    # the singleton `.nwave/audit/atdd-pure-events.jsonl`. Reading via the
    # singleton shape here would silently audit an empty/wrong file -- the
    # one outcome this whole feature exists to prevent. This call correctly
    # joins the cascade detector's in-flight xfail set; it graduates
    # alongside the other 11 callers once the data itself has migrated.
    ledger = AtCompletionLedger(feature_id, repo)
    records = ledger.read_records(event_type="SliceCommitVerified")
    return [_audit_one(repo, feature_id, record, path_port) for record in records]


def _audit_one(
    repo: Path,
    feature_id: str,
    record: dict[str, object],
    path_port: CommitTreePathPort,
) -> SealProvenanceFinding:
    slice_id = str(record["slice_id"])
    raw_seq = record["seq"]
    assert isinstance(raw_seq, int)
    seq = raw_seq
    commit_sha = record.get("commit_sha")

    if commit_sha is None:
        return SealProvenanceFinding(
            slice_id=slice_id,
            seq=seq,
            verdict=SealVerdict.INDETERMINATE,
            reason=(
                f"the SliceCommitVerified record for {slice_id!r} (seq={seq}) "
                "carries no commit_sha -- it was written before "
                "fix-slice-seal-carries-commit-sha, so no commit can be "
                "joined to this seal. Not silently trusted, not "
                "retroactively failed."
            ),
        )
    assert isinstance(commit_sha, str)

    at_paths = feature_files_for_slice(repo, slice_id, feature_id)
    if not at_paths:
        return SealProvenanceFinding(
            slice_id=slice_id,
            seq=seq,
            verdict=SealVerdict.INDETERMINATE,
            reason=(
                f"no AT file is discoverable for {slice_id!r} on this "
                f"working tree (gherkin @{slice_id} tag or pytest "
                f"@feature-{feature_id}/@{slice_id} tag) -- cannot determine "
                "which file this seal attests"
            ),
            commit_sha=commit_sha,
        )

    for rel_path in at_paths:
        outcome = path_port.path_exists_at_commit(repo, commit_sha, rel_path)
        if isinstance(outcome, Indeterminate):
            return SealProvenanceFinding(
                slice_id=slice_id,
                seq=seq,
                verdict=SealVerdict.INDETERMINATE,
                reason=(
                    f"git could not establish whether {rel_path!r} existed "
                    f"at commit_sha={commit_sha!r}: {outcome.reason}"
                ),
                commit_sha=commit_sha,
                checked_paths=tuple(at_paths),
            )
        if outcome is False:
            return SealProvenanceFinding(
                slice_id=slice_id,
                seq=seq,
                verdict=SealVerdict.PREMATURE,
                reason=(
                    f"{rel_path!r} does NOT exist in commit_sha={commit_sha!r}"
                    f"'s tree, yet the SliceCommitVerified seal for "
                    f"{slice_id!r} (seq={seq}) attests that commit -- the AT "
                    "was authored AFTER the seal fired: a premature "
                    "attestation."
                ),
                commit_sha=commit_sha,
                checked_paths=tuple(at_paths),
            )

    return SealProvenanceFinding(
        slice_id=slice_id,
        seq=seq,
        verdict=SealVerdict.VERIFIED,
        reason=(
            f"every AT file owned by {slice_id!r} "
            f"({', '.join(at_paths)}) existed in commit_sha={commit_sha!r}'s "
            "tree"
        ),
        commit_sha=commit_sha,
        checked_paths=tuple(at_paths),
    )


__all__ = [
    "SealProvenanceFinding",
    "SealVerdict",
    "audit_seal_provenance",
]
