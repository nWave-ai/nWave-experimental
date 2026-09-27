"""Pure public spellings for the host-selected role observation sequence."""

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


def role_id(role: str) -> str:
    """Return the configured DES role id for one closed public role."""
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


def invoke_next(
    root: Path, role: str, candidate: str, provider: str, input_path: str
) -> str:
    return shlex.join(
        (
            "des",
            "invoke-role",
            "--repo-root",
            str(root),
            "--role",
            role,
            "--candidate",
            candidate,
            "--provider",
            provider,
            "--input",
            input_path,
        )
    )


def recovery_invoke_next(root: Path, provider: str, input_path: str) -> str:
    """Advisory spelling after a caller-selected recovery preparation."""
    return shlex.join(
        (
            "des",
            "invoke-role",
            "--repo-root",
            str(root),
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--provider",
            provider,
            "--input",
            input_path,
        )
    )


def successor_next(root: Path, role: str, candidate: str) -> str:
    """The advisory continuation after a recorded role observation."""
    if role == "reviewer":
        return prepare_next(root, "examiner", candidate)
    return shlex.join(
        ("des", "integrate", "--repo-root", str(root), "--candidate", candidate)
    )
