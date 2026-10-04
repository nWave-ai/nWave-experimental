"""Persist a host-supplied specialist result against its prepared evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from des.adapters.driven.task_invocation.model_envelope import decode_model_run
from des.cli.role_artifacts import (
    HostRoleResult,
    RecordedRoleTurn,
    record,
    record_selected_revision_recovery,
)
from des.cli.role_guidance import PROVIDERS, successor_next
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)
from des.ports.driven_ports.task_invocation_port import MalformedModelEnvelope


def main(argv=None):
    p = argparse.ArgumentParser(prog="des record-role-result")
    p.add_argument("--repo-root", type=Path, required=True)
    p.add_argument(
        "--role", choices=("reviewer", "examiner", "acceptance-designer"), required=True
    )
    p.add_argument("--candidate", help="reviewer/examiner candidate SHA")
    p.add_argument("--task", choices=("selected-revision-recovery",))
    p.add_argument("--value", type=int, help="recovery value position")
    p.add_argument("--provider", choices=PROVIDERS, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--input", choices=("-",), required=True)
    p.add_argument(
        "--prepared-input",
        type=Path,
        help="exact INPUT revision returned by des prepare-role",
    )
    a = p.parse_args(argv)
    r = resolved_root(a.repo_root)
    if isinstance(r, StepRefusal):
        return refuse(r, NOTHING_OWED)
    raw = read_request()
    if isinstance(raw, StepRefusal):
        return refuse(raw, NOTHING_OWED)
    try:
        if a.role == "acceptance-designer":
            if (
                a.task != "selected-revision-recovery"
                or a.value is None
                or a.prepared_input is None
                or a.candidate is not None
            ):
                raise ValueError(
                    "recovery requires --task selected-revision-recovery --value N --prepared-input INPUT, without --candidate"
                )
            run = decode_model_run(
                json.loads(raw)["structured_output"],
                role_id="nw-acceptance-designer",
                semantic_task=a.task,
            )
            outcome, path, digest, document, document_digest = (
                record_selected_revision_recovery(
                    r,
                    a.value,
                    HostRoleResult(a.provider, a.model, a.session_id, run),
                    a.prepared_input,
                )
            )
            facts = [
                f"ROLE: {a.role}",
                f"TASK: {a.task}",
                f"VALUE: {a.value}",
                f"OUTCOME: {outcome}",
                f"RESULT: {path}",
                f"RESULT-SHA256: {digest}",
            ]
            if document is not None:
                facts.extend(
                    (
                        f"DISTILL-DOCUMENT: {document}",
                        f"DISTILL-DOCUMENT-SHA256: {document_digest}",
                    )
                )
            next_action = (
                f"des distill --repo-root {r} --replace-current --input -"
                if document is not None
                else f"des state --repo-root {r}"
            )
            return succeed(facts, next_action)
        if a.candidate is None or a.task is not None or a.value is not None:
            raise ValueError(
                "reviewer/examiner require --candidate and accept no --task or --value"
            )
        if a.prepared_input is None:
            raise ValueError(
                f"{a.role} requires the exact --prepared-input INPUT revision"
            )
        outcome, path, digest = record(
            r,
            RecordedRoleTurn(
                role=a.role,
                candidate=a.candidate,
                provider=a.provider,
                model=a.model,
                session=a.session_id,
            ),
            raw.encode("utf-8"),
            prepared_input=a.prepared_input,
        )
    except (
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        MalformedModelEnvelope,
    ) as error:
        return refuse(
            StepRefusal(
                "RoleResultMalformed",
                str(error),
                "supply one structured host result bound to its prepared input",
            ),
            NOTHING_OWED,
        )
    return succeed(
        [
            f"ROLE: {a.role}",
            f"CANDIDATE: {a.candidate}",
            f"OUTCOME: {outcome}",
            f"RESULT: {path}",
            f"RESULT-SHA256: {digest}",
        ],
        successor_next(r, a.role, a.candidate),
    )
