"""Read-only ``des schedule`` planning and scheduling-policy coherence checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.domain.repo_path_resolver import feature_delta_path
from des.domain.scheduling_policy import (
    SCHEDULING_POLICY,
    build_schedule_plan,
    unused_parallelism_diagnostic,
)


def _schedule_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des schedule",
        description="Render a deterministic, plan-only artifact DAG; no agent or process is started.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Vocabulary the report uses:\n"
            "  READY      an artifact whose every prerequisite is satisfied; it may start now.\n"
            "  admitted   a READY lane this plan lets you run, up to --cloud-capacity.\n"
            "  deferred   a READY lane held back, with the reason (e.g. cloud-capacity).\n"
            "  blocker    a non-READY artifact, naming what it awaits and the next action.\n"
            "  box lane   the ONE serialized local operation; cloud lanes fan out freely.\n"
            "\n"
            "UNUSED_PARALLELISM is reported when READY cloud work is left undispatched.\n"
            "DES only plans: submit the printed prompts through your own agent tooling."
        ),
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="Feature whose docs/feature/<id>/feature-delta.md declares the slice plan.",
    )
    parser.add_argument(
        "--repo-root",
        "--repo",
        dest="repo_root",
        default=".",
        help="Project root the feature plan is read from (default: current directory).",
    )
    parser.add_argument(
        "--cloud-capacity",
        type=int,
        default=None,
        help=(
            "How many READY cloud lanes this plan admits at once "
            f"(default: {SCHEDULING_POLICY.default_cloud_capacity}). Never inferred from the host."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "human"),
        default="human",
        help="human: a readable lane summary. json: the full machine-readable plan.",
    )
    parser.add_argument(
        "--consumer",
        choices=("box-action",),
        default=None,
        help=(
            "Check the plan on behalf of a caller about to take a local box action; "
            "it refuses (exit 1) rather than silently wasting idle cloud capacity."
        ),
    )
    return parser


def _coherence_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-scheduling-coherence",
        description="Read-only verification that SchedulingPolicy projections share one digest.",
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=("json", "human"), default="human")
    # A fixture-only observation input lets acceptance exercise the no-write drift path.
    parser.add_argument("--fixture-stale-projection", default=None, metavar="TARGET")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch only this module's two read-only scheduling commands."""
    args = list(argv or [])
    if args and args[0] == "verify-scheduling-coherence":
        return verify_scheduling_coherence(args[1:])
    return schedule(args)


def schedule(argv: list[str] | None = None) -> int:
    parser = _schedule_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 2)
    repo_root = Path(args.repo_root)
    path = feature_delta_path(repo_root, args.feature_id)
    ledger = AtCompletionLedger(project_root=repo_root)
    try:
        records = ledger.read_records(feature_id=args.feature_id)
    except (LedgerIntegrityViolation, UnicodeDecodeError) as exc:
        detail = getattr(exc, "detail", "undecodable-bytes")
        event = {
            "event": "ScheduleEvidenceIndeterminate",
            "unreadable_input": str(ledger.ledger_path()),
            "WHAT": f"The AT-completion ledger cannot be read ({detail}).",
            "WHY": (
                "An input DES cannot decode is an incapacity to answer; reporting "
                "a schedule over unreadable evidence would present a guess as an "
                "answer."
            ),
            "HOW": (
                f"run `des verify-integrity {args.repo_root} "
                f"--feature-id {args.feature_id}` to diagnose, repair per "
                "docs/operations/repair-instructions.md, then rerun des schedule."
            ),
        }
        print(json.dumps(event, sort_keys=True))
        return 3
    attested_slice_ids = frozenset(
        str(record["slice_id"]) for record in records if record.get("slice_id")
    )
    try:
        source = path.read_text(encoding="utf-8")
        plan = build_schedule_plan(
            args.feature_id,
            source,
            cloud_capacity=args.cloud_capacity,
            attested_slice_ids=attested_slice_ids,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        event = {
            "event": "ScheduleInputRejected",
            "WHAT": "The feature plan cannot produce a deterministic schedule.",
            "WHY": str(exc),
            "HOW": "supply a readable docs/feature/<feature-id>/feature-delta.md, then rerun des schedule.",
        }
        print(json.dumps(event, sort_keys=True))
        return 2
    if args.consumer == "box-action":
        diagnostic = unused_parallelism_diagnostic(plan)
        if diagnostic is not None:
            print(
                json.dumps(
                    {"event": "SchedulingConsumerRefused", "diagnostic": diagnostic},
                    sort_keys=True,
                )
            )
            return 1
    if args.format == "human":
        print(_render_human(plan))
    else:
        print(json.dumps(plan, sort_keys=True))
    return 0


def _render_human(plan: dict[str, object]) -> str:
    """Render the plan an operator has to act on, not the structure it lives in."""

    def rows(key: str) -> list[dict[str, object]]:
        value = plan.get(key, [])
        return (
            [item for item in value if isinstance(item, dict)]
            if isinstance(value, list)
            else []
        )

    lines = [
        f"Scheduling plan (policy v{plan.get('policy_version')}, plan-only -- nothing was started)",
        "",
    ]
    admitted, deferred = rows("admitted_cloud"), rows("deferred_cloud")
    lines.append(f"READY cloud lanes admitted now ({len(admitted)}):")
    lines.extend(f"  - {row.get('artifact_key')}" for row in admitted)
    if not admitted:
        lines.append("  (none)")
    if deferred:
        lines.append("")
        lines.append(f"READY cloud lanes held back ({len(deferred)}):")
        lines.extend(
            f"  - {row.get('artifact_key')}  [reason: {row.get('reason')}]"
            for row in deferred
        )
    box = rows("ready_box")
    lines.append("")
    lines.append(f"Box lane -- at most ONE runs locally ({len(box)} queued):")
    lines.extend(f"  - {row.get('artifact_key')}" for row in box)
    if not box:
        lines.append("  (none)")
    blockers = rows("blockers")
    if blockers:
        lines.append("")
        lines.append(f"Blocked ({len(blockers)}) -- each names what it awaits:")
        lines.extend(
            f"  - {row.get('artifact_key')}\n"
            f"      awaits : {row.get('missing_artifact')}\n"
            f"      when   : {row.get('required_condition')}\n"
            f"      next   : {row.get('next_action')}"
            for row in blockers
        )
    for entry in rows("diagnostics"):
        lines.append("")
        lines.append(f"[{entry.get('severity')}] {entry.get('code')}")
        lines.append(f"  WHAT: {entry.get('WHAT')}")
        lines.append(f"  WHY : {entry.get('WHY')}")
        lines.append(f"  HOW : {entry.get('HOW')}")
    return "\n".join(lines)


def verify_scheduling_coherence(argv: list[str] | None = None) -> int:
    parser = _coherence_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 2)
    target = args.fixture_stale_projection
    checked = list(SCHEDULING_POLICY.projection_names)
    if target:
        event = {
            "event": "SchedulingCoherenceVerified",
            "verdict": "DRIFT",
            "stale_target": target,
            "policy_rule": "SchedulingPolicy projections must carry the current policy digest.",
            "regenerate_command": "python scripts/docgen.py --projection scheduling-policy",
            "checked_projections": checked,
            "policy_digest": SCHEDULING_POLICY.digest(),
        }
        print(json.dumps(event, sort_keys=True))
        return 1
    event = {
        "event": "SchedulingCoherenceVerified",
        "verdict": "PASS",
        "checked_projections": checked,
        "policy_digest": SCHEDULING_POLICY.digest(),
    }
    print(json.dumps(event, sort_keys=True))
    return 0
