from __future__ import annotations

import argparse
from pathlib import Path

from des.adapters.driven.config.des_config import DESConfig
from des.cli.role_artifacts import (
    LocatorBearingCriterionId,
    RecoveryInputAlreadyPrepared,
    RoleInputAlreadyPrepared,
    SelectedRevisionUnavailable,
    prepare,
    prepare_selected_revision_recovery,
)
from des.cli.role_guidance import invoke_next, recovery_invoke_next, role_id
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)
from des.domain.public_observations import ObservationPacketRefused
from des.runtime.packaged_asset import installed_package_root


def main(argv=None):
    p = argparse.ArgumentParser(prog="des prepare-role")
    p.add_argument("--repo-root", type=Path, required=True)
    p.add_argument(
        "--role",
        choices=("reviewer", "examiner", "acceptance-designer"),
        required=True,
        help="reviewer/examiner require --candidate; acceptance-designer requires the recovery task",
    )
    p.add_argument("--candidate", help="verified candidate; reviewer/examiner only")
    p.add_argument("--observations", type=Path, help="examiner only")
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
            if a.candidate is not None or a.observations is not None:
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
            path, digest = prepare(r, a.role, a.candidate, a.observations)
        runtime = DESConfig(cwd=r).role_runtime(
            role_id(a.role), framework_root=installed_package_root()
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
        name = str(a.observations) if a.observations is not None else "observations"
        return refuse(
            StepRefusal(
                "ObservationPacketRefused",
                f"{len(e.defects)} defect(s) in {name}: {defects}{suffix}",
                "regenerate the packet with tests/evals/atomic-selected-acceptance/public_observation_capture.py on candidate SHA, fix each numbered defect, stay within 65536 bytes by selecting fewer events (seq gaps are allowed), then rerun des prepare-role --role examiner --candidate SHA --observations PATH; no role input was written",
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
    facts = [f"ROLE: {a.role}", f"INPUT: {path}", f"INPUT-SHA256: {digest}"]
    if recovery:
        facts.extend(("TASK: selected-revision-recovery", f"VALUE: {a.value}"))
        next_step = recovery_invoke_next(r, runtime.provider.value, path)
    else:
        facts.insert(1, f"CANDIDATE: {a.candidate}")
        next_step = invoke_next(r, a.role, a.candidate, runtime.provider.value, path)
    return succeed(facts, next_step)
