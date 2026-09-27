from __future__ import annotations

import argparse
import json
from pathlib import Path

from des.cli.role_artifacts import record
from des.cli.role_guidance import successor_next
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)


def main(argv=None):
    p = argparse.ArgumentParser(prog="des record-role-result")
    p.add_argument("--repo-root", type=Path, required=True)
    p.add_argument("--role", choices=("reviewer", "examiner"), required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--provider", choices=("claude", "codex"), required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--input", choices=("-",), required=True)
    p.add_argument(
        "--prepared-input",
        type=Path,
        help="exact examiner INPUT returned by des prepare-role; selects one revision",
    )
    a = p.parse_args(argv)
    r = resolved_root(a.repo_root)
    if isinstance(r, StepRefusal):
        return refuse(r, NOTHING_OWED)
    read = read_request()
    if isinstance(read, StepRefusal):
        return refuse(read, NOTHING_OWED)
    try:
        outcome, path, digest = record(
            r,
            a.role,
            a.candidate,
            a.provider,
            a.model,
            a.session_id,
            read.encode("utf-8"),
            prepared_input=a.prepared_input,
        )
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        return refuse(
            StepRefusal(
                "RoleResultMalformed", str(e), "supply one structured role result"
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
