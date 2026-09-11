from __future__ import annotations

import argparse
from pathlib import Path

from des.cli.role_artifacts import prepare
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    refuse,
    resolved_root,
    succeed,
)


def main(argv=None):
    p = argparse.ArgumentParser(prog="des prepare-role")
    p.add_argument("--repo-root", type=Path, required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--candidate", required=True)
    a = p.parse_args(argv)
    r = resolved_root(a.repo_root)
    if isinstance(r, StepRefusal):
        return refuse(r, NOTHING_OWED)
    try:
        path, digest = prepare(r, a.role, a.candidate)
    except ValueError as e:
        return refuse(
            StepRefusal(
                "RolePreparationUnavailable", str(e), "inspect candidate-bound evidence"
            ),
            NOTHING_OWED,
        )
    return succeed(
        [
            f"ROLE: {a.role}",
            f"CANDIDATE: {a.candidate}",
            f"INPUT: {path}",
            f"INPUT-SHA256: {digest}",
        ],
        NOTHING_OWED,
    )
