"""des mikado-attest-node-closure -- slice-01 CLI (f-mikado-node-closure-record).

Design: docs/feature/f-mikado-node-closure-record/design/adrs/
adr-D70-mikado-node-closure-record.md (ADR-D70), sections D70-3/D70-5.
Feature-delta: docs/feature/f-mikado-node-closure-record/feature-delta.md.

WHO/WHEN (D70-3): invoked by whoever performs a Mikado node's closing (or
work-started) act, at the moment ``## STATO NODO PER NODO``'s prose cell is
edited -- writes exactly one PRIMARY ``LedgerFamily.MIKADO`` record via
``EventStorePort.append`` (never ``append_derived`` -- D70-2: DD-8 refuses
every ``append_derived`` call for a null ``agent_id``, and this writer's
population is 100% null-``agent_id`` by construction).

The writer performs ZERO git verification, by design (D70-5): it validates
only its own three required non-empty strings (``--attesting-act``,
``--cited-sha``, ``--cited-artifact-path``) and the closed ``--transition``
vocabulary (``closed``|``work_started``), wires + probes
``UnifiedEventStoreAdapter`` (Earned Trust, DD-14) BEFORE ever attempting
``append()``, then writes the claim verbatim. The record's own claim is a
DESIGNATION; the PROPERTY is re-derived independently, only at READ time, by
the slice-02 gate -- never by this writer re-checking its own claim. This
module therefore NEVER imports ``scripts.validation.git_commit_reachability``/
``git_commit_contents`` (F-D-09 would refuse it even if it tried).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.adapters.driven.output.stdout_output import StdoutOutput
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.telemetry_paths import LedgerFamily
from des.ports.driven_ports.event_store_port import (
    EventRecord,
    InvalidScope,
    PartitionKeyRequired,
)
from des.ports.driven_ports.probeable_port import StoreProbeFailed


if TYPE_CHECKING:
    from des.ports.driven_ports.output_port import OutputPort

#: The closed --transition vocabulary (D70-3) mapped to its EventRecord.event
#: name -- ``sorted(...)`` of this dict's keys is argparse's own ``choices=``.
TRANSITION_EVENTS: dict[str, str] = {
    "closed": "NodeClosureAttested",
    "work_started": "NodeWorkStartedAttested",
}

#: The re-runnable invocation named by every blank-required-field refusal's
#: HOW clause (GDP-4) -- every flag filled with a placeholder, ``<a|b>``
#: form for the closed ``--transition`` vocabulary so `invocations_in`/
#: `rejections` (des.application.how_executability) resolve it to a real
#: accepted choice rather than a bare, argparse-refused ``PLACEHOLDER``.
_HOW_INVOCATION = (
    "des mikado-attest-node-closure --repo-root <repo> --node-id <node-id> "
    "--transition <closed|work_started> --cited-sha <sha> "
    "--cited-artifact-path <path> --attesting-act <act>"
)

#: The three required non-empty strings (D70-3), paired (flag spelling,
#: argparse dest) -- validated BEFORE any EventStorePort call.
_REQUIRED_STRING_FLAGS: tuple[tuple[str, str], ...] = (
    ("--attesting-act", "attesting_act"),
    ("--cited-sha", "cited_sha"),
    ("--cited-artifact-path", "cited_artifact_path"),
)


class _BlankRequiredFieldError(Exception):
    """A required string flag is empty/whitespace-only.

    Refused BEFORE any ``EventStorePort`` call is attempted -- a blank value
    would write the "closed because I said so" record ADR-D70 (D70-3) exists
    to make structurally impossible.
    """

    def __init__(self, flag_name: str, value: str) -> None:
        self.flag_name = flag_name
        super().__init__(
            f"WHAT: {flag_name} is blank ({value!r} after stripping "
            "whitespace). "
            "WHY: a blank attesting-act/citation would write a 'closed "
            "because I said so' record -- the exact unfalsifiable-by-"
            "construction failure this node-closure contract exists to "
            "remove (ADR-D70 D70-3). "
            f"HOW: re-run `{_HOW_INVOCATION}` with every flag filled in, "
            f"including a non-empty {flag_name}."
        )


def _validate_required_strings(args: argparse.Namespace) -> None:
    for flag_name, dest_name in _REQUIRED_STRING_FLAGS:
        value = getattr(args, dest_name)
        if not value.strip():
            raise _BlankRequiredFieldError(flag_name, value)


def _emit(payload: dict[str, object], output: OutputPort) -> None:
    """Emit exactly one single-line JSON object through the injected sink."""
    output.emit_line(json.dumps(payload))


def _encapsulate_store_refusal(*, what: str, why: str, store_exc: Exception) -> str:
    """Wrap a store-side refusal in THIS writer's OWN WHAT/WHY/HOW envelope
    (R17). The store's own message is already WHAT/WHY/HOW-shaped, but its
    HOW names a D80-level remediation ('pass partition_key=...', 'create the
    directory...'), never a re-runnable `des mikado-attest-node-closure`
    invocation -- so the writer adds its own HOW naming `_HOW_INVOCATION` on
    top, while keeping the original store exception text verbatim and
    recoverable inside the envelope (R10/R11 demand the store text survive
    as a substring, unmodified)."""
    return (
        f"WHAT: {what} "
        f"WHY: {why} "
        f"HOW: resolve the underlying fault described below, then re-run "
        f"`{_HOW_INVOCATION}`. "
        f"Original store-side error: {store_exc}"
    )


def _attest(args: argparse.Namespace, output: OutputPort) -> int:
    """Validate -> probe -> append, in that order (D70-3, DD-14).

    Never independently verifies ``--cited-sha``/``--cited-artifact-path``
    against ``.git/`` (D70-5) -- the record's claim is a designation,
    re-derived independently only at READ time by the slice-02 gate.
    """
    try:
        _validate_required_strings(args)
    except _BlankRequiredFieldError as exc:
        _emit(
            {
                "event": "MikadoNodeClosureAttestRefused",
                "reason": "blank_required_field",
                "flag": exc.flag_name,
                "message": str(exc),
            },
            output,
        )
        return 1

    adapter = UnifiedEventStoreAdapter(project_root=args.repo_root)
    try:
        adapter.probe()
    except StoreProbeFailed as exc:
        _emit(
            {
                "event": "MikadoNodeClosureAttestProbeRefused",
                "fault": exc.fault,
                "path": str(exc.path),
                "message": _encapsulate_store_refusal(
                    what=(
                        "the UnifiedEventStoreAdapter.probe() call failed "
                        "before any append() was attempted."
                    ),
                    why=(
                        "the writer refuses to attest a node closure "
                        "against a telemetry substrate it cannot prove is "
                        "usable (Earned Trust, DD-14) -- writing anyway "
                        "risks a silently lost or corrupted record."
                    ),
                    store_exc=exc,
                ),
            },
            output,
        )
        return 1

    record = EventRecord(
        family=LedgerFamily.MIKADO,
        event=TRANSITION_EVENTS[args.transition],
        scope="node",
        feature_id=None,
        partition_key=args.node_id,
        agent_id=None,
        fields={
            "node_id": args.node_id,
            "transition": args.transition,
            "cited_artifact": {
                "sha": args.cited_sha,
                "path": args.cited_artifact_path,
            },
            "attesting_act": args.attesting_act,
        },
    )
    try:
        appended = adapter.append(record)
    except (InvalidScope, PartitionKeyRequired) as exc:
        _emit(
            {
                "event": "MikadoNodeClosureAttestRejected",
                "message": _encapsulate_store_refusal(
                    what=(
                        "the unified event store refused this record before writing it."
                    ),
                    why=(
                        "the store's own DD-5 validation caught a case "
                        "(an out-of-vocabulary scope or an empty "
                        "partition_key) the writer's own three-string "
                        "pre-check does not independently cover."
                    ),
                    store_exc=exc,
                ),
            },
            output,
        )
        return 1

    _emit(
        {
            "event": TRANSITION_EVENTS[args.transition],
            "node_id": args.node_id,
            "transition": args.transition,
            "seq": appended.seq,
        },
        output,
    )
    return 0


def main(argv: list[str] | None = None, output: OutputPort | None = None) -> int:
    """CLI entry point -- attest one Mikado node state transition.

    ``output`` mirrors the sibling ``forward_context_admission.main``/
    ``event_store_probe.main`` convention: an in-process acceptance test
    injects ``CapturingOutput`` instead of the real terminal sink (Mandate 13
    L2 default -- no interpreter fork needed to observe emitted output).
    """
    parser = argparse.ArgumentParser(
        prog="des mikado-attest-node-closure",
        description=(
            "Attest a Mikado node's state transition (closed|work_started) "
            "as a re-verifiable LedgerFamily.MIKADO record via "
            "EventStorePort.append. Performs ZERO git verification (D70-5) "
            "-- the record's claim is a designation, re-derived "
            "independently only at read time by the tree-coherence gate."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        required=True,
        type=Path,
        help=(
            "The target repository root whose .nwave/telemetry/mikado/ "
            "ledger is written."
        ),
    )
    parser.add_argument(
        "--node-id",
        required=True,
        help="The Mikado node identity (EventRecord.partition_key).",
    )
    parser.add_argument(
        "--transition",
        required=True,
        choices=sorted(TRANSITION_EVENTS),
        help="The node's state transition being attested.",
    )
    parser.add_argument(
        "--cited-sha",
        required=True,
        help="The commit SHA cited as evidence (never independently verified).",
    )
    parser.add_argument(
        "--cited-artifact-path",
        required=True,
        help="The repo-relative path cited as evidence (never independently verified).",
    )
    parser.add_argument(
        "--attesting-act",
        required=True,
        help="Who/what performed the attestation, e.g. human:<name>.",
    )
    args = parser.parse_args(argv)
    sink = output if output is not None else StdoutOutput()
    return _attest(args, sink)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
