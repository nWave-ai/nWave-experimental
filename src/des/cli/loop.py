"""Public ``des loop`` command over the canonical standing-loop facade."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

from des.application.loop_runner import IdempotencyConflict, LoopControlService
from des.application.standing_loop_facade import LoopRefusal, StandingLoopFacade


if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class _ContinuedWork:
    project_root: Path
    outcome: str
    context_mode: str
    max_tokens_per_tick: int
    max_wall_seconds: int
    max_agent_concurrency: int
    max_box_concurrency: int
    continuity_proof_id: str | None = None


@dataclass(frozen=True)
class _ManualOccurrence:
    loop_id: str
    idempotency_key: str


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="des loop")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("probe", "inspect", "list", "arm", "tick", "recover", "stop"):
        command = commands.add_parser(name)
        command.add_argument("--project", required=True, type=Path)
        command.add_argument("--format", choices=("human", "json"), default="human")
        if name in {"inspect", "arm"}:
            command.add_argument("--loop")
        if name in {"inspect", "list", "tick", "recover", "stop"}:
            command.add_argument("--handle")
        # Scope selectors exist only when they have executable semantics.  The
        # standing core currently selects exactly one project-bound handle and
        # one idempotency-keyed occurrence, so inert ``--occurrence`` / ``--all``
        # flags are deliberately absent and argparse rejects them before dispatch.
        if name == "recover":
            command.add_argument("--apply", action="store_true")
        if name in {"arm", "tick", "stop"}:
            command.add_argument("--idempotency-key", required=True)
        if name == "recover":
            command.add_argument("--idempotency-key")
        if name in {"probe", "arm"}:
            command.add_argument("--context", choices=("reconstructed", "native_chat"))
        if name == "arm":
            command.add_argument("--continuity-proof")
            command.add_argument("--max-tokens", type=int, default=1200)
            command.add_argument("--max-wall-seconds", type=int, default=30)
            command.add_argument("--max-replays", type=int, default=1)
            command.add_argument("--cooldown-seconds", type=int, default=0)
            command.add_argument("--dry-run", action="store_true")
    return parser


def _project(path: Path) -> tuple[Path, str]:
    root = path.resolve()
    return root, sha256(str(root).encode()).hexdigest()


def _work(args: argparse.Namespace) -> _ContinuedWork:
    return _ContinuedWork(
        project_root=args.project.resolve(),
        outcome="produce one bounded, inspectable continued-work result",
        context_mode=args.context or "reconstructed",
        max_tokens_per_tick=args.max_tokens,
        max_wall_seconds=args.max_wall_seconds,
        max_agent_concurrency=1,
        max_box_concurrency=1,
        continuity_proof_id=args.continuity_proof,
    )


def _base(command: str, project: Path, event_type: str) -> dict[str, Any]:
    root, project_id = _project(project)
    return {
        "schema_version": "des.loop.command-result.v1",
        "event_type": event_type,
        "command": command,
        "status": "ok",
        "replayed": False,
        "project": {"id": project_id, "canonical_path": str(root)},
        "selection": {},
        "state": {},
        "context": {"requested": "reconstructed", "effective": "reconstructed"},
        "resources": {"authorised": {}},
        "isolation": {"kind": "project-read-only"},
    }


def _refusal(
    command: str, project: Path, result: LoopRefusal, *, context_mode: str
) -> dict[str, Any]:
    event = _base(command, project, "LOOP_COMMAND_REFUSED")
    event.pop("selection")
    diagnostic = asdict(result.diagnostic)
    event.update(
        {
            "status": "refused",
            "diagnostic": diagnostic,
            "context": {
                "requested": context_mode,
                "effective": context_mode,
                "continuity": (
                    "unproved"
                    if context_mode == "native_chat"
                    else "durable-state-reconstruction"
                ),
            },
        }
    )
    return event


def _handle_refusal(
    command: str,
    project: Path,
    *,
    code: str,
    what: str,
    why: str,
    how: str,
) -> dict[str, Any]:
    """Project a pre-execution public refusal without selecting a handle."""
    event = _base(command, project, "LOOP_COMMAND_REFUSED")
    event.pop("selection")
    event.update(
        {
            "status": "refused",
            "diagnostic": {
                "code": code,
                "what": what,
                "why": why,
                "how": how,
            },
        }
    )
    return event


def _refusal_exit_code(code: str) -> int:
    return {
        "INVALID_LIMIT": 2,
        "PROJECT_MISMATCH": 3,
        "IDEMPOTENCY_CONFLICT": 4,
        "HANDLE_STOPPED": 5,
        "CONTEXT_CONTINUITY_UNPROVED": 5,
    }.get(code, 5)


def _dispatch(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    facade = StandingLoopFacade()
    event_types = {
        "probe": "LOOP_PROBED",
        "inspect": "LOOP_INSPECTED",
        "list": "LOOP_LISTED",
        "arm": "LOOP_ARMED",
        "tick": "LOOP_TICKED",
        "recover": "LOOP_RECOVERY_PLANNED",
        "stop": "LOOP_STOPPED",
    }
    event = _base(args.command, args.project, event_types[args.command])
    if args.command == "probe":
        requested = args.context or "reconstructed"
        event["context"] = {
            "requested": requested,
            "effective": requested,
            "continuity": (
                "durable-state-reconstruction"
                if requested == "reconstructed"
                else "unproved"
            ),
        }
        return 0, event
    if args.command == "inspect":
        event["context"]["continuity"] = "durable-state-reconstruction"
        return 0, event
    if args.command == "arm":
        if args.loop != "standing":
            raise ValueError("loop must be standing")
        work = _work(args)
        inspection = facade.inspect(work)
        event["context"] = {
            "requested": work.context_mode,
            "effective": work.context_mode,
            "continuity": "durable-state-reconstruction",
        }
        event["resources"]["authorised"] = inspection.limits
        if args.dry_run:
            event["event_type"] = "LOOP_ARM_PLANNED"
            return 0, event
        result = facade.arm(work, idempotency_key=args.idempotency_key)
        if hasattr(result, "diagnostic"):
            return _refusal_exit_code(result.diagnostic.code), _refusal(
                args.command, args.project, result, context_mode=work.context_mode
            )
        event["selection"] = {
            "loop_id": result.loop_id,
            "handle_id": result.loop_id,
        }
        event["state"] = {"desired": "ARMED", "observed": "SCHEDULED"}
        return 0, event
    if args.handle is not None:
        project_root = args.project.resolve()
        expected_handle = (
            f"standing-{sha256(str(project_root).encode()).hexdigest()[:16]}"
        )
        if args.handle != expected_handle:
            return 3, _handle_refusal(
                args.command,
                args.project,
                code="PROJECT_MISMATCH",
                what="The supplied standing-loop handle belongs to another project.",
                why="Opaque authority must be project-bound before any state lookup.",
                how="Use the handle returned when this project was armed.",
            )
    records = facade.list(args.project)
    record = records[0] if records else None
    handle = LoopControlService().handle(args.project) if record is not None else None
    if args.handle is not None and handle is not None and args.handle != handle.loop_id:
        return 3, _handle_refusal(
            args.command,
            args.project,
            code="PROJECT_MISMATCH",
            what="The supplied standing-loop handle belongs to another project.",
            why="A project may not inspect, recover, stop, or tick another project's loop.",
            how="Use the opaque handle returned when this project was armed.",
        )
    if args.command == "list":
        if record is not None:
            event["selection"]["handle_id"] = handle.loop_id
            event["state"] = {
                "desired": record.desired_state,
                "observed": record.observed_state,
            }
        return 0, event
    if record is None:
        raise ValueError("no loop is armed for project")
    assert handle is not None
    loop_id = handle.loop_id
    if args.command == "tick":
        if record.desired_state == "STOPPED":
            return 5, _handle_refusal(
                args.command,
                args.project,
                code="HANDLE_STOPPED",
                what="The supplied standing-loop handle is stopped.",
                why=(
                    "A stopped loop has no authority to claim or execute another "
                    "occurrence."
                ),
                how=(
                    "Arm a new loop only after explicitly authorising a new continued-"
                    "work scope."
                ),
            )
        event["selection"]["handle_id"] = args.handle or loop_id
        attestation = facade.manual_tick(
            args.project,
            _ManualOccurrence(loop_id=loop_id, idempotency_key=args.idempotency_key),
        )
        if attestation.outcome == "REFUSED_STOPPED":
            return 5, _handle_refusal(
                args.command,
                args.project,
                code="HANDLE_STOPPED",
                what="The supplied standing-loop handle is stopped.",
                why=(
                    "A stopped loop has no authority to claim or execute another "
                    "occurrence."
                ),
                how=(
                    "Arm a new loop only after explicitly authorising a new continued-"
                    "work scope."
                ),
            )
        event["selection"]["occurrence_id"] = attestation.occurrence_key
        event["attestation"] = {
            "id": attestation.id,
            "outcome": attestation.outcome.lower(),
            "requested_digest": attestation.requested_digest,
        }
        if attestation.observed_digest is not None:
            event["attestation"]["observed_digest"] = attestation.observed_digest
        if attestation.execution_receipt is not None:
            event["attestation"]["execution_receipt"] = attestation.execution_receipt
        event["replayed"] = attestation.replayed
        event["resources"] = dict(attestation.resources)
        if attestation.execution_receipt is not None:
            event["resources"]["measurement_receipt"] = {
                "receipt_id": attestation.execution_receipt["resource_receipt_id"],
                "measured_at": attestation.execution_receipt["observed_at"],
                "source": attestation.execution_receipt["executor_id"],
                "consumed": attestation.resources["consumed"],
                "measurement_id": attestation.execution_receipt["resource_measurement"][
                    "measurement_id"
                ],
            }
        event["isolation"] = attestation.isolation
        return 0, event
    event["selection"]["handle_id"] = args.handle or loop_id
    if args.command == "recover":
        recovery = facade.recover(
            args.project,
            apply=args.apply,
            idempotency_key=args.idempotency_key or "recover-plan",
        )
        if args.apply:
            event["event_type"] = "LOOP_RECOVERED"
        attestation = recovery.attestation
        event["reconciliation_digest"] = recovery.reconciliation_digest
        if attestation is not None:
            event["attestation"] = {
                "id": attestation.id,
                "outcome": attestation.outcome.lower(),
                "requested_digest": attestation.requested_digest,
            }
            if attestation.observed_digest is not None:
                event["attestation"]["observed_digest"] = attestation.observed_digest
        return 0, event
    stopped = facade.stop(args.project, handle, idempotency_key=args.idempotency_key)
    event["state"] = {"desired": "STOPPED", "observed": stopped.observed_state}
    event["changed"] = stopped.changed
    return 0, event


def _emit(event: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(event, sort_keys=True))
        return
    print(f"{event['event_type']}: {event['status']}")
    print(json.dumps(event, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        exit_code, event = _dispatch(args)
    except IdempotencyConflict as error:
        event = _handle_refusal(
            args.command,
            args.project,
            code="IDEMPOTENCY_CONFLICT",
            what="This idempotency key was already used for a different request.",
            why=str(error),
            how="Reuse the original normalized request or choose a new key.",
        )
        exit_code = 4
    except (OSError, ValueError) as error:
        event = _base(args.command, args.project, "LOOP_COMMAND_REFUSED")
        event.update(
            {
                "status": "refused",
                "diagnostic": {
                    "code": "INVALID_ARGUMENT",
                    "what": "The standing-loop request could not be completed.",
                    "why": str(error),
                    "how": "Correct the project, selector, limits, or prior arm state.",
                },
            }
        )
        exit_code = 2
    _emit(event, args.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
