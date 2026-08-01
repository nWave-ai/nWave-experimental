"""des event-store-query -- merge one telemetry ledger family's legacy and new-envelope records into one honestly could-not-verify-counted view.

Charter: docs/product/expectations/unified-event-store/
         as-a-cross-cutting-query-caller-i-get-one-merged-view-across-legacy-and-unified-records-with-an.md
Feature-delta: docs/feature/unified-event-store/feature-delta.md

`--family` single-family mode (this slice): the caller names a `LedgerFamily`
and a `partition_key`; the command reads that one ledger, normalizes any
pre-cutover (legacy) rows via `LegacyEnvelopeNormalizer` (DD-10), dedupes any
new-envelope derived rows via `ReductionKeyDeduper` (DD-7/DD-8), and emits
ONE merged, provenance-tagged result whose `measured_count` and
`could_not_verify_count` travel together (DD-9) -- never a bare total. An
unreadable ledger file raises `could_not_verify_count` and names a reason,
never silently drops the total. A partition key with no ledger file at all
is distinguishable in the output from a partition key whose ledger
genuinely holds zero records. The command never mutates the store it reads.

Default no-`--family` mode (unified-event-store slice-04, Owns-row
correction in feature-delta.md [REF] Staging Plan): the caller omits
`--family` and names only `--partition-key` (a feature id); the command
merges the THREE timeline-bearing families (`atdd-pure`/`examine`/`review`
-- never `context`/`mikado`, the D71-lane families out of this feature's
scope) via `CrossDomainReader.read_across` (DD-13), one chronologically-
ordered, provenance-tagged view. This wiring is itself a thin RED scaffold:
`read_across` raises `AssertionError` uncaught (DISTILL slice-04 scope,
`src/des/adapters/driven/logging/cross_domain_reader.py`) until DELIVER
implements the real merge -- this module adds only the argparse/dispatch
wiring, no business logic, mirroring how the `--family` branch itself
called the (then-scaffold) `UnifiedEventStoreAdapter.read()` uncaught
before slice-03's DELIVER pass implemented it for real.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.logging.cross_domain_reader import CrossDomainReader
from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.adapters.driven.output.stdout_output import StdoutOutput
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.telemetry_paths import LedgerFamily


if TYPE_CHECKING:
    from des.ports.driven_ports.output_port import OutputPort


#: The three timeline-bearing families the default cross-domain mode merges
#: (DD-13's own consumer #4 scope) -- `context`/`mikado` are the D71 lane's
#: families and are deliberately excluded here.
_TIMELINE_FAMILIES = (
    LedgerFamily.ATDD_PURE,
    LedgerFamily.EXAMINE,
    LedgerFamily.REVIEW,
)


def _emit(payload: dict[str, object], output: OutputPort) -> None:
    """Emit exactly one single-line JSON object through the injected sink."""
    output.emit_line(json.dumps(payload))


def main(argv: list[str] | None = None, output: OutputPort | None = None) -> int:
    """CLI entry point -- run the single-family read, emit one JSON answer.

    ``output`` mirrors the sibling ``event_store_probe.main`` convention: an
    in-process acceptance test injects ``CapturingOutput`` instead of the
    real terminal sink (Mandate 13 L2 default -- no interpreter fork needed
    to observe emitted output).
    """
    parser = argparse.ArgumentParser(
        prog="des event-store-query",
        description=(
            "Query one telemetry ledger family for a partition key, merging "
            "legacy (pre-cutover) and new-envelope records into one "
            "provenance-tagged view with an honest measured/"
            "could-not-verify split (DD-7/DD-8/DD-9/DD-10). Never a bare "
            "total."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        required=True,
        type=Path,
        help="The target repository root whose .nwave/telemetry/ ledgers are queried.",
    )
    parser.add_argument(
        "--family",
        required=False,
        default=None,
        choices=[member.value for member in LedgerFamily],
        help=(
            "The single telemetry ledger family to query (slice-03 "
            "single-family mode). Omit for the default cross-domain "
            "timeline mode (slice-04) -- merges atdd-pure/examine/review."
        ),
    )
    parser.add_argument(
        "--partition-key",
        required=True,
        help=(
            "The partition key identifying one ledger within --family, or "
            "the feature id whose timeline is merged in default mode."
        ),
    )
    args = parser.parse_args(argv)
    sink = output if output is not None else StdoutOutput()

    if args.family is None:
        reader = CrossDomainReader(args.repo_root)
        cross_result = reader.read_across(list(_TIMELINE_FAMILIES), args.partition_key)
        _emit(
            {
                "event": "EventStoreCrossDomainQueryResult",
                "families": [member.value for member in _TIMELINE_FAMILIES],
                "partition_key": args.partition_key,
                "records": cross_result.records,
                "measured_count": cross_result.measured_count,
                "could_not_verify_count": cross_result.could_not_verify_count,
                "could_not_verify_reasons": cross_result.could_not_verify_reasons,
            },
            sink,
        )
        return 0

    adapter = UnifiedEventStoreAdapter(project_root=args.repo_root)
    result = adapter.read(LedgerFamily(args.family), args.partition_key)

    _emit(
        {
            "event": "EventStoreQueryResult",
            "family": args.family,
            "partition_key": args.partition_key,
            "records": result.records,
            "measured_count": result.measured_count,
            "could_not_verify_count": result.could_not_verify_count,
            "could_not_verify_reasons": result.could_not_verify_reasons,
        },
        sink,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
