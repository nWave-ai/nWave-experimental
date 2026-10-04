from __future__ import annotations

import argparse
import json
from pathlib import Path

from des.adapters.driven.task_invocation.model_envelope import _schema_for
from des.cli.role_artifacts import (
    LocatorBearingCriterionId,
    RecoveryInputAlreadyPrepared,
    RoleInputAlreadyPrepared,
    SelectedRevisionUnavailable,
    prepare,
    prepare_selected_revision_recovery,
)
from des.cli.role_guidance import record_next, role_id
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)
from des.domain.public_observations import ObservationPacketRefused, input_description


def _from_root(root: Path, path: Path | None) -> Path | None:
    """Every caller-supplied input path is read relative to the repository root."""
    return path if path is None or path.is_absolute() else root / path


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="des prepare-role",
        epilog=input_description(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--repo-root", type=Path, required=True)
    p.add_argument(
        "--role",
        choices=("reviewer", "examiner", "acceptance-designer"),
        required=True,
        help="reviewer/examiner require --candidate; acceptance-designer requires the recovery task",
    )
    p.add_argument("--candidate", help="verified candidate; reviewer/examiner only")
    p.add_argument(
        "--observations",
        type=Path,
        help="examiner only; a relative path resolves against --repo-root",
    )
    p.add_argument(
        "--context",
        type=Path,
        help="caller-owned JSON: request_sha256, naming text array, scope_amendments [{change, authority, evidence}]; reviewer receives context, examiner only redacted public amendments; DES does not verify authorization; a relative path resolves against --repo-root",
    )
    p.add_argument(
        "--task",
        choices=("selected-revision-recovery",),
        help="acceptance-designer only; requires --value and --finding -",
    )
    p.add_argument(
        "--value", type=int, help="stale selected revision position; recovery only"
    )
    p.add_argument(
        "--finding",
        help="- reads the complete recovery finding from stdin; recovery only",
    )
    a = p.parse_args(argv)
    r = resolved_root(a.repo_root)
    if isinstance(r, StepRefusal):
        return refuse(r, NOTHING_OWED)
    try:
        recovery = a.role == "acceptance-designer"
        if recovery:
            if a.task != "selected-revision-recovery" or a.value is None:
                raise ValueError(
                    "acceptance-designer requires --task selected-revision-recovery and --value"
                )
            if (
                a.candidate is not None
                or a.observations is not None
                or a.context is not None
            ):
                raise ValueError(
                    "selected-revision-recovery does not accept --candidate or --observations"
                )
            if a.finding != "-":
                raise ValueError("selected-revision-recovery requires --finding -")
            finding = read_request()
            if isinstance(finding, StepRefusal):
                return refuse(finding, NOTHING_OWED)
            path, digest = prepare_selected_revision_recovery(r, a.value, finding)
        else:
            if a.candidate is None:
                raise ValueError("reviewer and examiner require --candidate")
            if a.task is not None or a.value is not None or a.finding is not None:
                raise ValueError(
                    "--task, --value, and --finding belong only to acceptance-designer recovery"
                )
            path, digest = prepare(
                r,
                a.role,
                a.candidate,
                _from_root(r, a.observations),
                _from_root(r, a.context),
            )
    except SelectedRevisionUnavailable as e:
        failure = e.outcome.failure
        return refuse(
            StepRefusal(failure.what, failure.why, failure.how, e.outcome.disposition),
            NOTHING_OWED,
        )
    except LocatorBearingCriterionId as e:
        return refuse(
            StepRefusal(
                "LocatorBearingCriterionId",
                (
                    f"selected acceptance criterion id {e.criterion_id!r} contains "
                    "a known repository locator; an id is the join key and cannot "
                    "be redacted or exposed to the source-blind examiner"
                ),
                (
                    "correct the selected criterion id through des distill "
                    "--replace-current --input - so it no longer carries a "
                    "repository locator, then rerun des prepare-role"
                ),
            ),
            NOTHING_OWED,
        )
    except ObservationPacketRefused as e:
        defects = "; ".join(
            f"{index}. {item.code} at {item.pointer}: {item.detail}"
            for index, item in enumerate(e.defects, 1)
        )
        suffix = (
            "; not run: shape, candidate_identity, known_path_strings"
            if e.stopped
            else ""
        )
        name = (
            str(_from_root(r, a.observations))
            if a.observations is not None
            else "observations"
        )
        return refuse(
            StepRefusal(
                "ObservationPacketRefused",
                f"{len(e.defects)} defect(s) in {name}: {defects}{suffix}",
                "capture real public events for the verified candidate using the project's native tools, construct the packet with des.domain.public_observations.encode_packet (grammar: des prepare-role --help), correct each numbered defect and stay within 65536 bytes by selecting fewer events, then rerun des prepare-role --role examiner --candidate SHA --observations PATH; no role input was written",
            ),
            NOTHING_OWED,
        )
    except RoleInputAlreadyPrepared as e:
        return refuse(
            StepRefusal(
                "RoleInputAlreadyPrepared",
                f"{e.path} already exists with sha256 {e.digest}; role inputs are write-once and the existing bytes are unchanged",
                "reuse the existing input, or start from a new candidate SHA to prepare different evidence",
            ),
            NOTHING_OWED,
        )
    except RecoveryInputAlreadyPrepared as e:
        return refuse(
            StepRefusal(
                "RoleInputAlreadyPrepared",
                f"{e.path} already exists with sha256 {e.digest}; recovery inputs are write-once",
                "reuse the exact INPUT, or correct the selected revision before preparing another recovery",
            ),
            NOTHING_OWED,
        )
    except ValueError as e:
        how = (
            "use des prepare-role --role acceptance-designer "
            "--task selected-revision-recovery --value N --finding -"
            if recovery
            else "inspect candidate-bound evidence"
        )
        return refuse(
            StepRefusal("RolePreparationUnavailable", str(e), how),
            NOTHING_OWED,
        )
    packet = json.loads((r / path).read_text(encoding="utf-8"))
    result_schema = _schema_for(
        role_id(a.role),
        defect_values=tuple(value["observation"] for value in packet.get("values", [])),
        semantic_task="selected-revision-recovery" if recovery else None,
    )
    facts = [
        f"ROLE: {a.role}",
        f"ROLE-ID: {role_id(a.role)}",
        f"INPUT: {path}",
        f"INPUT-SHA256: {digest}",
        f"RESULT-SCHEMA: {result_schema}",
        "HOST-ACTION: invoke the exact installed role with the permitted INPUT bytes; then record its result",
    ]
    if not recovery:
        views = r / (path + ".views") / "manifest.json"
        facts.extend(
            (
                f"INPUT-VIEWS: {views.relative_to(r)}",
                "INPUT-VIEWS-USE: read field parts in manifest order; concatenate string values without separators; authenticate with des.cli.role_packet_views.read_views(manifest, expected_input_sha256=the independently retained INPUT-SHA256); record against the original INPUT, not views",
            )
        )
    if recovery:
        facts.extend(("TASK: selected-revision-recovery", f"VALUE: {a.value}"))
        next_step = record_next(r, a.role, path, value=a.value)
    else:
        facts.insert(1, f"CANDIDATE: {a.candidate}")
        next_step = record_next(r, a.role, path, candidate=a.candidate)
    return succeed(facts, next_step)
