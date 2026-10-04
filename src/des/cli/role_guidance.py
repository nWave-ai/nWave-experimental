"""Advisory spellings for host-selected, separately recorded role observations."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

ROLE_IDS = {
    "reviewer": "nw-software-crafter-reviewer",
    "examiner": "nw-user-examiner",
    "acceptance-designer": "nw-acceptance-designer",
}

#: The host runtimes `des record-role-result --provider` accepts.  One tuple,
#: read by the parser and by the advisory spelling below, so the NEXT a host
#: copies already names the accepted words: an opaque `PROVIDER` placeholder
#: was answered `native` and `openai` and refused with argparse usage in both
#: codex retest cases (2026-10-01).
PROVIDERS = ("claude", "codex")


def role_id(role: str) -> str:
    return ROLE_IDS[role]


def prepare_next(root: Path, role: str, candidate: str) -> str:
    return shlex.join(
        (
            "des",
            "prepare-role",
            "--repo-root",
            str(root),
            "--role",
            role,
            "--candidate",
            candidate,
        )
    )


def record_next(
    root: Path,
    role: str,
    input_path: str,
    *,
    candidate: str | None = None,
    value: int | None = None,
) -> str:
    argv = [
        "des",
        "record-role-result",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--provider",
        "{" + ",".join(PROVIDERS) + "}",
        "--model",
        "MODEL",
        "--session-id",
        "SESSION",
        "--input",
        "-",
    ]
    if candidate is not None:
        argv.extend(("--candidate", candidate))
    argv.extend(("--prepared-input", input_path))
    if value is not None:
        argv.extend(("--task", "selected-revision-recovery", "--value", str(value)))
    return shlex.join(argv)


def successor_next(root: Path, role: str, candidate: str) -> str:
    if role == "reviewer":
        return prepare_next(root, "examiner", candidate)
    return shlex.join(
        ("des", "integrate", "--repo-root", str(root), "--candidate", candidate)
    )
